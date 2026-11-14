import numpy as np
import pandas as pd
from typing import List, Optional

class ModularDistanceProvider:
    """
    Provides the distance matrix D_ij, Depot distances, and Disposal site distances
    to the optimizer. Seamlessly switches from synthetic parametric distances to real GPS
    coordinates when the municipality provides the master location table.
    """
    def __init__(
        self,
        location_ids: List[str],
        real_coords_df: Optional[pd.DataFrame] = None,
        avg_inter_point_km: float = 1.4,
        depot_to_zone_km: float = 4.5,
        disposal_proximity_km: float = 5.5,
        road_winding_factor: float = 1.30,
        seed: int = 42
    ):
        self.location_ids = list(location_ids)
        self.n_bins = len(self.location_ids)
        self.road_winding_factor = road_winding_factor
        self.depot_coord = (49.1427, 9.2109) # Heilbronn City Center / Central Depot

        if real_coords_df is not None and {'Location_id', 'lat', 'lon'}.issubset(real_coords_df.columns):
            # REAL GPS MODE
            self.mode = "REAL_GPS"
            merged = pd.DataFrame({'Location_id': self.location_ids}).merge(real_coords_df, on='Location_id', how='left')
            self.coords = merged[['lat', 'lon']].values
        else:
            # SYNTHETIC PARAMETRIC HEILBRONN GRID
            self.mode = "SYNTHETIC_PARAMETRIC"
            rng = np.random.default_rng(seed)
            # Centered on Heilbronn bounding box
            lats = self.depot_coord[0] + rng.normal(0, 0.018, self.n_bins).clip(-0.035, 0.035)
            lons = self.depot_coord[1] + rng.normal(0, 0.022, self.n_bins).clip(-0.040, 0.040)
            self.coords = np.column_stack([lats, lons])

        # Compute inter-bin distance matrix
        self.inter_bin_matrix = self._compute_haversine_matrix(self.coords) * self.road_winding_factor

        # In synthetic mode, normalize to target avg_inter_point_km
        if self.mode == "SYNTHETIC_PARAMETRIC" and self.n_bins > 1:
            off_diag = self.inter_bin_matrix[np.triu_indices(self.n_bins, k=1)].mean()
            if off_diag > 0:
                self.inter_bin_matrix *= (avg_inter_point_km / off_diag)

        # Configurable Depot & Disposal distances (Section 3 variables)
        self.depot_dist = np.full(self.n_bins, depot_to_zone_km)
        self.disposal_dist = np.full(self.n_bins, disposal_proximity_km)
        self.disposal_to_depot_km = 3.2

    @staticmethod
    def _compute_haversine_matrix(coords: np.ndarray) -> np.ndarray:
        lat = np.radians(coords[:, 0])[:, None]
        lon = np.radians(coords[:, 1])[:, None]
        dlat = lat - lat.T
        dlon = lon - lon.T
        a = np.sin(dlat / 2.0) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2.0) ** 2
        return 6371.0 * (2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))
