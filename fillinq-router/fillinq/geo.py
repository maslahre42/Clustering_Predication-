"""Site locations and travel times.

The Fillinq export is anonymised and has NO coordinates. Until real
locations are available the app uses *synthetic* positions spread over
Heilbronn districts. They are clearly labelled as illustrative in the UI:
stop counts, fill levels and overflow results do not depend on them, but
kilometres and driving hours do.

To use real locations, put a CSV with columns  site, lat, lon  into
data/site_locations.csv (or upload it in the app). `site` must match
Location_id in the readings file.
"""
from __future__ import annotations
from __future__ import annotations

import os
import numpy as np
import pandas as pd

from .config import OpsConfig

# approximate district centres (lat, lon, sd_km, weight) - illustrative only
DISTRICTS = [
    ("Innenstadt", 49.1427, 9.2109, 0.9, 0.28),
    ("Boeckingen", 49.1228, 9.1758, 1.1, 0.20),
    ("Sontheim", 49.1157, 9.2217, 1.0, 0.14),
    ("Neckargartach", 49.1745, 9.2002, 0.9, 0.12),
    ("Frankenbach", 49.1338, 9.1578, 0.8, 0.10),
    ("Nordstadt/Kirchhausen", 49.1560, 9.1600, 1.2, 0.16),
]


def load_locations(path: str | None) -> pd.DataFrame | None:
    if path and os.path.exists(path):
        loc = pd.read_csv(path)
        loc.columns = [c.strip().lower() for c in loc.columns]
        if {"site", "lat", "lon"} <= set(loc.columns):
            loc["site"] = loc["site"].astype(str)
            return loc[["site", "lat", "lon"]]
    return None


def synthetic_locations(sites, seed: int = 42) -> pd.DataFrame:
    sites = sorted(map(str, sites))
    rng = np.random.default_rng(seed)
    w = np.array([d[4] for d in DISTRICTS])
    pick = rng.choice(len(DISTRICTS), size=len(sites), p=w / w.sum())
    lat, lon, dist = [], [], []
    for p in pick:
        name, la, lo, sd, _ = DISTRICTS[p]
        dy, dx = rng.normal(0, sd, 2)  # km
        lat.append(la + dy / 111.0)
        lon.append(lo + dx / (111.0 * np.cos(np.radians(la))))
        dist.append(name)
    return pd.DataFrame({"site": sites, "lat": lat, "lon": lon, "district": dist})


def get_locations(sites, path: str | None = None):
    """Return (locations_df, is_synthetic)."""
    real = load_locations(path)
    if real is not None:
        have = set(real["site"])
        if set(map(str, sites)) <= have:
            return real[real["site"].isin(set(map(str, sites)))].reset_index(drop=True), False
    return synthetic_locations(sites), True


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def road_km_matrix(lat: np.ndarray, lon: np.ndarray, cfg: OpsConfig) -> np.ndarray:
    """Straight-line distance times a detour factor (replace by OSRM/OpenRouteService later)."""
    la, lo = np.asarray(lat), np.asarray(lon)
    d = haversine_km(la[:, None], lo[:, None], la[None, :], lo[None, :])
    return d * cfg.detour_factor
