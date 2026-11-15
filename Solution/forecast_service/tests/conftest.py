"""Worker unit tests use an explicit deterministic street-service double, never the internet."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor'))

import numpy as np
import pytest


class TestRoadNetwork:
    max_snap_m = 1000

    def matrix(self, lat, lon):
        lat, lon = np.asarray(lat), np.asarray(lon)
        # An asymmetric toy road network, intentionally different from aerial travel.
        distances = (np.abs(lat[:, None] - lat[None, :]) * 111 + np.abs(lon[:, None] - lon[None, :]) * 73) * 1.7
        distances += np.where(distances > 0, (lat[:, None] < lat[None, :]) * .2, 0)
        return distances, distances / 30 * 3600, [(float(a),float(b),0) for a,b in zip(lat,lon)]

    def route(self, points):
        result=[]
        for a,b in zip(points,points[1:]):
            km, seconds, _=self.matrix([a[0],b[0]],[a[1],b[1]])
            result.append(dict(points=[list(a),list(b)],distanceKm=float(km[0,1]),drivingSeconds=float(seconds[0,1])))
        return result

    def describe(self):
        return dict(provider='test street provider',profile='driving',distanceSource='street-network',objective='driving-distance',assignment='compact-sectors',note='Unit test double')

    def access(self, lat, lon):
        return {} if lat is None or lon is None else dict(roadLatitude=lat,roadLongitude=lon,snapDistanceM=0)


@pytest.fixture(autouse=True)
def isolate_worker_roads(monkeypatch):
    from test_worker import worker
    monkeypatch.setattr(worker, 'make_road_network', TestRoadNetwork)
