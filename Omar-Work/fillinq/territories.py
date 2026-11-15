"""Contiguous angular service sectors with balanced estimated working time.

Stops in a sector belong to one truck across every unloading load. Different
rotations of the sweep are compared using the road matrix; this prevents each
truck being sent to every side of the city. It is a heuristic, not an optimality proof.
"""
import math
import numpy as np


def compact_sectors(stops, vehicles, cfg, road_seconds, road_km):
    n = len(stops)
    if n == 0:
        return np.array([], dtype=int)
    k = min(vehicles, n)
    lat = stops['lat'].to_numpy()
    lon = stops['lon'].to_numpy()
    # Polar order creates noninterleaving districts around the common unloading site.
    angle = np.arctan2(lat - cfg.disposal_lat, (lon - cfg.disposal_lon) * math.cos(math.radians(cfg.disposal_lat)))
    order = np.lexsort((stops['site'].astype(str).to_numpy(), angle))
    neighbors = np.asarray(road_seconds[1:1+n, 1:1+n], dtype=float).copy()
    np.fill_diagonal(neighbors, np.inf)
    nearby = np.partition(neighbors, min(1, n - 1), axis=1)[:, :min(2, n - 1)]
    drive = np.mean(nearby, axis=1) if n > 1 else np.zeros(n)
    service = (cfg.service_min_per_stop + stops['n_bins'].to_numpy() * cfg.service_min_per_bin) * 60
    loads = np.maximum(stops['kg'].to_numpy() / cfg.truck_payload_kg, stops['vol_l'].to_numpy() / cfg.truck_volume_l)
    work = np.maximum(1, service + drive + loads * cfg.unload_min * 60)
    work *= np.where(stops['must'].to_numpy(dtype=bool), 1.0, .1)
    best, best_score = None, None
    for rotation in np.unique(np.linspace(0, n - 1, min(n, 16), dtype=int)):
        sequence = np.roll(order, -int(rotation))
        labels = np.zeros(n, dtype=int)
        target, accumulated, zone = work.sum() / k, 0.0, 0
        for position, index in enumerate(sequence):
            remaining, zones_left = n - position, k - zone
            if zone < k - 1 and accumulated > 0 and (accumulated + work[index] / 2 > target or remaining == zones_left - 1):
                zone += 1
                accumulated = 0.0
            labels[index] = zone
            accumulated += work[index]
        groups = [np.flatnonzero(labels == v) for v in range(k)]
        # Balanced load first, then road compactness; no south/north interleaving.
        totals = np.array([work[group].sum() for group in groups])
        spread = sum(float(np.mean(road_km[np.ix_(group + 1, group + 1)])) for group in groups if len(group) > 1)
        score = (float(totals.max()), float(totals.std()), spread)
        if best_score is None or score < best_score:
            best, best_score = labels, score
    return best
