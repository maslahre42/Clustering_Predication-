"""Stable site geography; the map and optimization share the same coordinates."""
import hashlib
import numpy as np
import pandas as pd


class ModularDistanceProvider:
    def __init__(self, location_ids, real_coords_df=None, *, road_winding_factor=1.30,
                 seed=42, depot_coord=(49.1427, 9.2109), disposal_coord=(49.1577, 9.2459),
                 fixed_travel_min=0.0, coordinates_are_synthetic=True):
        self.location_ids = [str(x) for x in location_ids]
        if len(set(self.location_ids)) != len(self.location_ids):
            raise ValueError('Supply one unique ID per physical site.')
        if not np.isfinite(road_winding_factor) or road_winding_factor < 1:
            raise ValueError('road_winding_factor must be finite and at least one.')
        if not np.isfinite(fixed_travel_min) or fixed_travel_min < 0:
            raise ValueError('fixed_travel_min must be nonnegative and finite.')
        self.n_bins = len(self.location_ids)
        self.road_winding_factor = float(road_winding_factor)
        self.fixed_travel_min = float(fixed_travel_min)
        self.depot_coord = tuple(depot_coord)
        self.disposal_coord = tuple(disposal_coord)
        if real_coords_df is not None:
            if not {'Location_id', 'lat', 'lon'}.issubset(real_coords_df.columns):
                raise ValueError('Coordinate table needs Location_id, lat, lon.')
            if real_coords_df['Location_id'].duplicated().any():
                raise ValueError('Duplicate coordinate IDs.')
            table = real_coords_df.set_index('Location_id').reindex(self.location_ids)
            self.coords = table[['lat', 'lon']].to_numpy(dtype=float)
            self.is_synthetic = bool(coordinates_are_synthetic)
            self.mode = 'PROVIDED_COORDINATES'
        else:
            self.is_synthetic = True
            self.mode = 'SYNTHETIC_STABLE_SITES'
            points = []
            for location in self.location_ids:
                digest = hashlib.sha256(f'{seed}:{location}'.encode()).digest()
                a, b = [int.from_bytes(digest[i:i+8], 'big') / 2**64 for i in (0, 8)]
                radius_km, angle = 1 + 5 * np.sqrt(a), 2 * np.pi * b
                points.append((depot_coord[0] + radius_km * np.sin(angle) / 111.0,
                               depot_coord[1] + radius_km * np.cos(angle) / (111.0 * np.cos(np.radians(depot_coord[0])))))
            self.coords = np.asarray(points, dtype=float).reshape(-1, 2)
        all_coords = np.vstack([self.depot_coord, self.coords, self.disposal_coord])
        if (all_coords.shape[1] != 2 or not np.isfinite(all_coords).all()
                or (np.abs(all_coords[:, 0]) > 90).any() or (np.abs(all_coords[:, 1]) > 180).any()):
            raise ValueError('Missing, non-finite or out-of-range coordinates.')
        matrix = self._compute_haversine_matrix(all_coords) * self.road_winding_factor
        self.inter_bin_matrix = matrix[1:-1, 1:-1]
        self.depot_dist = matrix[0, 1:-1]
        self.disposal_dist = matrix[1:-1, -1]
        self.disposal_to_depot_km = float(matrix[-1, 0])
        self.distance_provenance = ('synthetic_' if self.is_synthetic else '') + 'haversine_detour_derived'

    @staticmethod
    def _compute_haversine_matrix(coords):
        coords = np.asarray(coords, dtype=float)
        lat, lon = np.radians(coords[:, 0])[:, None], np.radians(coords[:, 1])[:, None]
        a = np.sin((lat-lat.T)/2)**2 + np.cos(lat)*np.cos(lat.T)*np.sin((lon-lon.T)/2)**2
        return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    def travel_minutes(self, distance_km, avg_speed_kmh):
        distances = np.asarray(distance_km, dtype=float)
        # Zero-distance duplicate places cost no travel. Services are separate.
        return np.where(distances > 1e-10, self.fixed_travel_min, 0.0) if self.fixed_travel_min else distances / avg_speed_kmh * 60
