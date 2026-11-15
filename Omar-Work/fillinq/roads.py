"""OSRM driving costs and street geometry. No aerial-distance fallback.

The disposable cache is separate from the application's read-only source database.
Coordinates, profile and provider form each key. Requests are serialized/rate limited
across worker processes so changing a setting does not hammer the public service.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import numpy as np


class RoadRoutingError(ValueError):
    pass


def coordinate(lat, lon):
    if lat is None or lon is None or not math.isfinite(float(lat)) or not math.isfinite(float(lon)) or abs(float(lat)) > 90 or abs(float(lon)) > 180:
        raise RoadRoutingError('Road routing needs valid latitude/longitude for every location.')
    return f'{float(lon):.6f},{float(lat):.6f}'


class RoadNetwork:
    def __init__(self, base_url=None, cache_path=None, opener=None, clock=time.time, sleep=time.sleep):
        self.base = (base_url or os.environ.get('OSRM_BASE_URL', 'https://router.project-osrm.org')).rstrip('/')
        parsed = urlparse(self.base)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise RoadRoutingError('OSRM_BASE_URL must be an HTTP(S) server URL without credentials or query parameters.')
        self.provider = self.base + '/driving'
        self.cache_path = Path(cache_path or os.environ.get('ROAD_ROUTING_CACHE', str(Path(tempfile.gettempdir()) / 'garbage-collector-roads-v1.sqlite')))
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.open = opener or urlopen
        self.clock, self.sleep = clock, sleep
        self.ttl = 7 * 86400
        self.max_snap_m = 1000
        with self._db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS pairs(provider TEXT,src TEXT,dst TEXT,meters REAL,seconds REAL,stored REAL,PRIMARY KEY(provider,src,dst));
                CREATE TABLE IF NOT EXISTS points(provider TEXT,point TEXT,lat REAL,lon REAL,snap REAL,stored REAL,PRIMARY KEY(provider,point));
                CREATE TABLE IF NOT EXISTS responses(url TEXT PRIMARY KEY,body TEXT,stored REAL);
                CREATE TABLE IF NOT EXISTS rate(provider TEXT PRIMARY KEY,requested REAL);''')

    def _db(self):
        return sqlite3.connect(self.cache_path, timeout=90)

    def _get(self, service, points, options):
        url = f'{self.base}/{service}/v1/driving/{";".join(points)}?{urlencode(options)}'
        # Cache hits do not require a network request. Holding this independent cache lock
        # while requesting enforces a maximum of one request/second across processes.
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            cached = db.execute('SELECT body,stored FROM responses WHERE url=?', (url,)).fetchone()
            if cached and cached[1] >= self.clock() - self.ttl:
                return json.loads(cached[0])
            previous = db.execute('SELECT requested FROM rate WHERE provider=?', (self.provider,)).fetchone()
            if previous:
                self.sleep(max(0, previous[0] + 1.05 - self.clock()))
            try:
                req = Request(url, headers={'User-Agent': 'GarbageCollector-Hackathon/1.0 (OSRM road-route prototype)', 'Accept': 'application/json'})
                with self.open(req, timeout=30) as response:
                    data = json.load(response)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
                raise RoadRoutingError('Street routing is unavailable. Check the configured OSRM server and retry; no straight-line routes were substituted.') from error
            if data.get('code') != 'Ok':
                raise RoadRoutingError(f'Street routing failed ({data.get("code", "invalid response")}). No aerial-distance fallback is used.')
            db.execute('INSERT OR REPLACE INTO responses VALUES(?,?,?)', (url, json.dumps(data, separators=(',', ':')), self.clock()))
            db.execute('INSERT OR REPLACE INTO rate VALUES(?,?)', (self.provider, self.clock()))
            return data

    def matrix(self, lat, lon):
        keys = [coordinate(la, lo) for la, lo in zip(lat, lon)]
        unique = list(dict.fromkeys(keys))
        pairs, snapped = {}, {}
        with self._db() as db:
            # Endpoint-specific immutable travel facts are safe to share, never workspace settings.
            for src, dst, meters, seconds in db.execute('SELECT src,dst,meters,seconds FROM pairs WHERE provider=? AND stored>=?', (self.provider, self.clock() - self.ttl)):
                pairs[(src, dst)] = (meters, seconds)
            for key, la, lo, distance in db.execute('SELECT point,lat,lon,snap FROM points WHERE provider=? AND stored>=?', (self.provider, self.clock() - self.ttl)):
                snapped[key] = (la, lo, distance)
        for i in range(0, len(unique), 50):
            sources = unique[i:i + 50]
            for j in range(0, len(unique), 50):
                destinations = unique[j:j + 50]
                if all((a, b) in pairs for a in sources for b in destinations):
                    continue
                batch = list(dict.fromkeys(sources + destinations))
                indices = {key: k for k, key in enumerate(batch)}
                data = self._get('table', batch, dict(annotations='distance,duration',
                    sources=';'.join(str(indices[key]) for key in sources),
                    destinations=';'.join(str(indices[key]) for key in destinations), generate_hints='false'))
                distances, durations = data.get('distances'), data.get('durations')
                if not isinstance(distances, list) or not isinstance(durations, list) or len(distances) != len(sources) or len(durations) != len(sources):
                    raise RoadRoutingError('The road provider returned an invalid driving matrix.')
                with self._db() as db:
                    for a, src in enumerate(sources):
                        if len(distances[a]) != len(destinations) or len(durations[a]) != len(destinations):
                            raise RoadRoutingError('The road provider returned incomplete driving costs.')
                        for b, dst in enumerate(destinations):
                            meters, seconds = distances[a][b], durations[a][b]
                            if meters is not None and (not math.isfinite(meters) or meters < 0) or seconds is not None and (not math.isfinite(seconds) or seconds < 0):
                                raise RoadRoutingError('The road provider returned invalid driving costs.')
                            pairs[(src, dst)] = (meters, seconds)
                            db.execute('INSERT OR REPLACE INTO pairs VALUES(?,?,?,?,?,?)', (self.provider, src, dst, meters, seconds, self.clock()))
                    for field, points in [('sources', sources), ('destinations', destinations)]:
                        waypoints = data.get(field, [])
                        if len(waypoints) != len(points):
                            raise RoadRoutingError('The road provider omitted snapped location provenance.')
                        for key, waypoint in zip(points, waypoints):
                            lo, la = waypoint['location']
                            coordinate(la, lo)
                            snap = float(waypoint['distance'])
                            if not math.isfinite(snap) or snap < 0:
                                raise RoadRoutingError('The road provider returned invalid snapped access distances.')
                            snapped[key] = (la, lo, snap)
                            db.execute('INSERT OR REPLACE INTO points VALUES(?,?,?,?,?,?)', (self.provider, key, la, lo, snap, self.clock()))
        km = np.array([[np.inf if pairs[(a, b)][0] is None else pairs[(a, b)][0] / 1000 for b in keys] for a in keys])
        seconds = np.array([[np.inf if pairs[(a, b)][1] is None else pairs[(a, b)][1] for b in keys] for a in keys])
        access = [snapped[key] for key in keys]
        return km, seconds, access

    def route(self, points):
        """Return one street shape per leg, preserving pickup/unloading waypoint order."""
        if len(points) > 100:
            return [leg for start in range(0, len(points) - 1, 99) for leg in self.route(points[start:start + 100])]
        keys = [coordinate(lat, lon) for lat, lon in points]
        if len(keys) < 2:
            return []
        data = self._get('route', keys, dict(steps='true', overview='false', geometries='geojson',
                                            continue_straight='false', generate_hints='false'))
        routes = data.get('routes', [])
        if not routes or len(routes[0].get('legs', [])) != len(keys) - 1:
            raise RoadRoutingError('The road provider returned an incomplete street route.')
        legs = []
        for index, leg in enumerate(routes[0]['legs']):
            if any(not isinstance(leg.get(field), (int, float)) or not math.isfinite(leg[field]) or leg[field] < 0 for field in ('distance', 'duration')):
                raise RoadRoutingError('The road provider returned invalid street-route metrics.')
            shape = []
            for step in leg.get('steps', []):
                for lo, la in step.get('geometry', {}).get('coordinates', []):
                    coordinate(la, lo)
                    if not shape or shape[-1] != [la, lo]:
                        shape.append([la, lo])
            if len(shape) < 2 and leg['distance'] == 0 and leg['duration'] == 0:
                waypoints = data.get('waypoints', [])
                if len(waypoints) == len(keys):
                    lo, la = waypoints[index]['location']
                    coordinate(la, lo)
                    shape = [[la, lo], [la, lo]]
                elif keys[index] == keys[index + 1]:
                    shape = [list(points[index]), list(points[index])]
            if len(shape) < 2:
                raise RoadRoutingError('Street geometry is missing; no straight connection was substituted.')
            legs.append(dict(points=shape, distanceKm=leg['distance'] / 1000, drivingSeconds=leg['duration']))
        return legs

    def describe(self):
        return dict(provider='OSRM / OpenStreetMap', profile='driving', distanceSource='street-network',
                    objective='driving-distance', assignment='compact-sectors',
                    note='Car-accessible street routes; truck-specific height, weight and access restrictions are not modeled. Site assignments retain their original provenance.')

    def access(self, lat, lon):
        if lat is None or lon is None:
            return {}
        with self._db() as db:
            row = db.execute('SELECT lat,lon,snap FROM points WHERE provider=? AND point=? AND stored>=?',
                             (self.provider, coordinate(lat, lon), self.clock() - self.ttl)).fetchone()
        return {} if not row else dict(roadLatitude=row[0],roadLongitude=row[1],snapDistanceM=row[2])
