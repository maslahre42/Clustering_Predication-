import os
import json
import time
import hashlib
import urllib.request
import urllib.error
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional, Union

class ModularDistanceProvider:
    """
    Modular Distance and Travel Duration Provider for Heilbronn Smart Waste Optimization.
    
    Supports two distinct operational modes:
      1. 'synthetic': Parametric Heilbronn grid generation with calibrated inter-point distance,
                      road winding factor, and parametric depot/disposal site distances.
      2. 'osrm' (or 'osm'): High-fidelity OpenStreetMap road-network routing via the OSRM Table API.
                      Computes real turn-by-turn driving distances (km) and travel durations (min),
                      preserving one-way street asymmetry (D_ij != D_ji), and includes persistent local
                      caching and graceful Haversine fallback.

    Network Node Indexing:
      - Node 0:     Central Yard / Depot (Heilbronn City Center: 49.1427, 9.2109)
      - Nodes 1..N: Physical Glass Recycling Containers (in order of location_ids)
      - Node N+1:   Recycling Disposal Site / Entsorgungszentrum (Böllinger Höfe: 49.1650, 9.2450)
      
    Routing Profile Note:
      The public OSRM demo server uses the 'driving' (passenger car) profile. For production municipal
      fleet operations, an on-premise OSRM or Valhalla/GraphHopper instance with a dedicated 'truck' /
      'heavy_goods_vehicle' profile should be deployed to account for vehicle height/weight limits,
      axle loads, turning radiuses, and municipal waste access rights.
    """

    def __init__(
        self,
        location_ids: Optional[List[Any]] = None,
        real_coords_df: Optional[pd.DataFrame] = None,
        mode: Optional[str] = None,
        depot_coord: Tuple[float, float] = (49.1427, 9.2109),
        disposal_coord: Tuple[float, float] = (49.1650, 9.2450),
        road_winding_factor: float = 1.35,
        avg_speed_kmh: float = 28.0,
        avg_inter_point_km: float = 1.4,
        depot_to_zone_km: float = 4.5,
        disposal_proximity_km: float = 5.5,
        seed: int = 42,
        cache_path: str = "data/osrm_matrix_cache.json",
        osrm_url: str = "http://router.project-osrm.org/table/v1/driving",
        timeout: float = 10.0,
    ):
        self.depot_coord = tuple(depot_coord)
        self.disposal_coord = tuple(disposal_coord)
        self.road_winding_factor = float(road_winding_factor)
        self.avg_speed_kmh = float(avg_speed_kmh)
        self.cache_path = cache_path
        self.osrm_url = osrm_url
        self.timeout = float(timeout)
        self.seed = seed

        # Resolve mode: default to synthetic unless requested or real coordinates provided
        if mode is not None:
            norm_mode = mode.strip().lower()
            if norm_mode in ("osrm", "osm"):
                selected_mode = "osrm"
            elif norm_mode in ("synthetic", "synthetic_parametric"):
                selected_mode = "synthetic"
            else:
                selected_mode = norm_mode
        else:
            selected_mode = "osrm" if real_coords_df is not None else "synthetic"

        # Resolve containers and coordinates
        if selected_mode == "osrm":
            self._init_osrm_mode(location_ids, real_coords_df)
        else:
            self._init_synthetic_mode(
                location_ids,
                real_coords_df,
                avg_inter_point_km,
                depot_to_zone_km,
                disposal_proximity_km
            )

    # -------------------------------------------------------------------------
    # SYNTHETIC MODE INITIALIZATION
    # -------------------------------------------------------------------------
    def _init_synthetic_mode(
        self,
        location_ids: Optional[List[Any]],
        real_coords_df: Optional[pd.DataFrame],
        avg_inter_point_km: float,
        depot_to_zone_km: float,
        disposal_proximity_km: float
    ):
        self.mode = "SYNTHETIC_PARAMETRIC"
        if location_ids is not None:
            self.location_ids = [str(x) for x in location_ids]
        elif real_coords_df is not None and len(real_coords_df) > 0:
            id_col = self._detect_column(real_coords_df, ['poi_id', 'Location_id', 'location_id', 'id'])
            self.location_ids = [str(x) for x in real_coords_df[id_col].tolist()]
        else:
            self.location_ids = [f"BIN_{i+1:03d}" for i in range(24)]

        self.n_bins = len(self.location_ids)

        if real_coords_df is not None and self._has_coordinate_columns(real_coords_df):
            self.coords = self._extract_coords_from_df(real_coords_df, self.location_ids)
        else:
            rng = np.random.default_rng(self.seed)
            lats = self.depot_coord[0] + rng.normal(0, 0.018, self.n_bins).clip(-0.035, 0.035)
            lons = self.depot_coord[1] + rng.normal(0, 0.022, self.n_bins).clip(-0.040, 0.040)
            self.coords = np.column_stack([lats, lons])

        # (N+2) coordinates: [Depot, Bin_1, ..., Bin_N, Disposal]
        self.all_coords = np.vstack([[self.depot_coord], self.coords, [self.disposal_coord]])
        self.all_node_ids = ["DEPOT"] + self.location_ids + ["DISPOSAL"]

        # Inter-bin distance matrix
        if self.n_bins > 0:
            self.inter_bin_matrix = self._compute_haversine_matrix(self.coords) * self.road_winding_factor
            if self.n_bins > 1:
                off_diag = self.inter_bin_matrix[np.triu_indices(self.n_bins, k=1)].mean()
                if off_diag > 0:
                    self.inter_bin_matrix *= (avg_inter_point_km / off_diag)
        else:
            self.inter_bin_matrix = np.zeros((0, 0))

        # Backward compatibility properties
        self.depot_dist = np.full(self.n_bins, depot_to_zone_km)
        self.disposal_dist = np.full(self.n_bins, disposal_proximity_km)
        self.disposal_to_depot_km = 3.2

        # Build full (N+2) x (N+2) distance matrix
        M = self.n_bins + 2
        D = np.zeros((M, M))
        if self.n_bins > 0:
            D[0, 1:self.n_bins+1] = self.depot_dist
            D[1:self.n_bins+1, 0] = self.depot_dist
            D[1:self.n_bins+1, 1:self.n_bins+1] = self.inter_bin_matrix
            D[1:self.n_bins+1, self.n_bins+1] = self.disposal_dist
            D[self.n_bins+1, 1:self.n_bins+1] = self.disposal_dist
        D[self.n_bins+1, 0] = self.disposal_to_depot_km
        D[0, self.n_bins+1] = self.disposal_to_depot_km
        np.fill_diagonal(D, 0.0)
        self.dist_matrix_km = D

        # Build duration matrix (minutes)
        T = (D / max(self.avg_speed_kmh, 1e-3)) * 60.0
        np.fill_diagonal(T, 0.0)
        self.duration_matrix_min = T

        self.depot_duration_min = self.duration_matrix_min[0, 1:self.n_bins+1]
        self.inter_bin_duration_min = self.duration_matrix_min[1:self.n_bins+1, 1:self.n_bins+1]
        self.disposal_duration_min = self.duration_matrix_min[1:self.n_bins+1, self.n_bins+1]
        self.disposal_to_depot_duration_min = float(self.duration_matrix_min[self.n_bins+1, 0])

    # -------------------------------------------------------------------------
    # OSRM REAL ROAD NETWORK MODE INITIALIZATION
    # -------------------------------------------------------------------------
    def _init_osrm_mode(
        self,
        location_ids: Optional[List[Any]],
        real_coords_df: Optional[pd.DataFrame]
    ):
        # Auto-load actual Heilbronn containers CSV if no dataframe was provided
        if real_coords_df is None:
            default_csv = "data/heilbronn_actual_glass_containers.csv"
            if os.path.exists(default_csv):
                real_coords_df = pd.read_csv(default_csv)
            else:
                raise FileNotFoundError(
                    f"OSRM mode requested, but real_coords_df is None and {default_csv} was not found."
                )

        # Detect columns in real_coords_df
        id_col = self._detect_column(real_coords_df, ['poi_id', 'Location_id', 'location_id', 'id', 'POI_ID'])
        lat_col = self._detect_column(real_coords_df, ['latitude', 'lat', 'Latitude', 'LAT', 'y'])
        lon_col = self._detect_column(real_coords_df, ['longitude', 'lon', 'lng', 'Longitude', 'LON', 'x'])

        # Resolve location_ids list
        if location_ids is not None and len(location_ids) > 0:
            self.location_ids = [str(x) for x in location_ids]
        else:
            self.location_ids = [str(x) for x in real_coords_df[id_col].tolist()]

        self.n_bins = len(self.location_ids)

        # Map location_ids to coordinates
        coords_dict = {
            str(row[id_col]): (float(row[lat_col]), float(row[lon_col]))
            for _, row in real_coords_df.iterrows()
        }

        container_coords_list = []
        for loc_id in self.location_ids:
            if loc_id in coords_dict:
                container_coords_list.append(coords_dict[loc_id])
            else:
                # Fallback: find by integer conversion if numeric, else warn and approximate
                matched = False
                for k, v in coords_dict.items():
                    try:
                        if int(float(k)) == int(float(loc_id)):
                            container_coords_list.append(v)
                            matched = True
                            break
                    except ValueError:
                        pass
                if not matched:
                    print(f"[Warning] Location ID '{loc_id}' not found in coordinates DataFrame. Approximating near Depot.")
                    container_coords_list.append(self.depot_coord)

        self.coords = np.array(container_coords_list, dtype=float)
        self.all_coords = np.vstack([[self.depot_coord], self.coords, [self.disposal_coord]])
        self.all_node_ids = ["DEPOT"] + self.location_ids + ["DISPOSAL"]
        M = len(self.all_coords)

        # Compute coordinate hash for caching (rounded to 6 decimals ~ 0.11m precision)
        rounded_coords = [[round(float(lat), 6), round(float(lon), 6)] for lat, lon in self.all_coords]
        coord_hash = hashlib.sha256(json.dumps(rounded_coords).encode('utf-8')).hexdigest()[:16]

        # 1. Attempt retrieval from cache
        dist_mat, dur_mat, cache_hit = self._load_from_cache(coord_hash, rounded_coords, M)
        
        if cache_hit:
            self.mode = "OSRM_CACHED"
        else:
            # 2. Query OSRM API with chunking support
            try:
                dist_mat, dur_mat = self._query_osrm_table(self.all_coords)
                self.mode = "OSRM_ROAD_NETWORK"
                self._save_to_cache(coord_hash, self.all_node_ids, rounded_coords, dist_mat, dur_mat)
            except Exception as e:
                # 3. Defensive fallback to Haversine * road_winding_factor
                print(f"[Warning] OSRM service query failed ({type(e).__name__}: {e}). Gracefully falling back to Haversine * {self.road_winding_factor} road winding factor.")
                dist_mat = self._compute_haversine_matrix(self.all_coords) * self.road_winding_factor
                dur_mat = (dist_mat / max(self.avg_speed_kmh, 1e-3)) * 60.0
                np.fill_diagonal(dist_mat, 0.0)
                np.fill_diagonal(dur_mat, 0.0)
                self.mode = "OSRM_FALLBACK_HAVERSINE"

        # Assign core matrices
        self.dist_matrix_km = dist_mat
        self.duration_matrix_min = dur_mat

        # Slice convenience properties
        self.depot_dist = self.dist_matrix_km[0, 1:self.n_bins+1]
        self.inter_bin_matrix = self.dist_matrix_km[1:self.n_bins+1, 1:self.n_bins+1]
        self.disposal_dist = self.dist_matrix_km[1:self.n_bins+1, self.n_bins+1]
        self.disposal_to_depot_km = float(self.dist_matrix_km[self.n_bins+1, 0])

        self.depot_duration_min = self.duration_matrix_min[0, 1:self.n_bins+1]
        self.inter_bin_duration_min = self.duration_matrix_min[1:self.n_bins+1, 1:self.n_bins+1]
        self.disposal_duration_min = self.duration_matrix_min[1:self.n_bins+1, self.n_bins+1]
        self.disposal_to_depot_duration_min = float(self.duration_matrix_min[self.n_bins+1, 0])

    # -------------------------------------------------------------------------
    # OSRM API QUERY ENGINE WITH CHUNKING
    # -------------------------------------------------------------------------
    def _query_osrm_table(self, coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Queries the OSRM Table API. If total points M > 100, dynamically chunks the
        query into square blocks of size <= 60 to respect public API limits.
        """
        M = len(coords)
        dist_m = np.zeros((M, M))
        dur_s = np.zeros((M, M))

        chunk_size = 60
        if M <= 100:
            chunks = [list(range(M))]
        else:
            chunks = [list(range(i, min(i + chunk_size, M))) for i in range(0, M, chunk_size)]

        for ci, src_indices in enumerate(chunks):
            for cj, dst_indices in enumerate(chunks):
                if len(chunks) == 1:
                    coords_str = ';'.join(f"{coords[i][1]:.6f},{coords[i][0]:.6f}" for i in range(M))
                    url = f"{self.osrm_url}/{coords_str}?annotations=distance,duration"
                else:
                    combined_indices = sorted(list(set(src_indices + dst_indices)))
                    index_map = {orig_idx: path_idx for path_idx, orig_idx in enumerate(combined_indices)}
                    src_path_str = ';'.join(str(index_map[i]) for i in src_indices)
                    dst_path_str = ';'.join(str(index_map[j]) for j in dst_indices)
                    coords_str = ';'.join(f"{coords[idx][1]:.6f},{coords[idx][0]:.6f}" for idx in combined_indices)
                    url = f"{self.osrm_url}/{coords_str}?sources={src_path_str}&destinations={dst_path_str}&annotations=distance,duration"

                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'FutureCityHackathon/1.0 (GIS-Routing; Heilbronn-Smart-Waste)'}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if data.get('code') != 'Ok':
                        raise RuntimeError(f"OSRM returned non-Ok code: {data.get('code')}")

                    sub_d = data['distances']
                    sub_t = data['durations']

                    if len(chunks) == 1:
                        dist_m = np.array(sub_d, dtype=float)
                        dur_s = np.array(sub_t, dtype=float)
                    else:
                        for row_i, s_idx in enumerate(src_indices):
                            for col_j, d_idx in enumerate(dst_indices):
                                dist_m[s_idx, d_idx] = sub_d[row_i][col_j]
                                dur_s[s_idx, d_idx] = sub_t[row_i][col_j]

                # Slight courtesy delay between multi-block chunks
                if len(chunks) > 1 and (ci < len(chunks) - 1 or cj < len(chunks) - 1):
                    time.sleep(0.2)

        # Convert meters -> km, seconds -> minutes
        dist_km = dist_m / 1000.0
        dur_min = dur_s / 60.0
        np.fill_diagonal(dist_km, 0.0)
        np.fill_diagonal(dur_min, 0.0)

        return dist_km, dur_min

    # -------------------------------------------------------------------------
    # PERSISTENT LOCAL MATRIX CACHING
    # -------------------------------------------------------------------------
    def _load_from_cache(
        self,
        coord_hash: str,
        rounded_coords: List[List[float]],
        num_nodes: int
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], bool]:
        if not os.path.exists(self.cache_path):
            return None, None, False

        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)

            # Strategy A: Direct hash match
            matrices = cache.get("matrices", {})
            if coord_hash in matrices:
                entry = matrices[coord_hash]
                dist_km = np.array(entry["distances_km"], dtype=float)
                dur_min = np.array(entry["durations_min"], dtype=float)
                if dist_km.shape == (num_nodes, num_nodes) and dur_min.shape == (num_nodes, num_nodes):
                    return dist_km, dur_min, True

            # Strategy B: Submatrix slice from master nodes if available
            master = cache.get("master_nodes")
            if master and "coordinates" in master:
                master_coords = [tuple(c) for c in master["coordinates"]]
                master_coord_map = {c: i for i, c in enumerate(master_coords)}
                
                req_tuples = [tuple(c) for c in rounded_coords]
                if all(c in master_coord_map for c in req_tuples):
                    indices = [master_coord_map[c] for c in req_tuples]
                    master_d = np.array(master["distances_km"], dtype=float)
                    master_t = np.array(master["durations_min"], dtype=float)
                    
                    sub_d = master_d[np.ix_(indices, indices)]
                    sub_t = master_t[np.ix_(indices, indices)]
                    np.fill_diagonal(sub_d, 0.0)
                    np.fill_diagonal(sub_t, 0.0)
                    
                    # Store sliced submatrix in cache under its own hash
                    self._save_to_cache(coord_hash, self.all_node_ids, rounded_coords, sub_d, sub_t)
                    return sub_d, sub_t, True

        except Exception as e:
            print(f"[Warning] Failed to read OSRM cache at {self.cache_path}: {e}")

        return None, None, False

    def _save_to_cache(
        self,
        coord_hash: str,
        node_ids: List[str],
        rounded_coords: List[List[float]],
        dist_km: np.ndarray,
        dur_min: np.ndarray
    ):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.cache_path)), exist_ok=True)
            cache = {}
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:
                    cache = {}

            if "matrices" not in cache:
                cache["matrices"] = {}

            cache["cache_version"] = "1.0"
            cache["routing_profile"] = "driving"
            cache["matrices"][coord_hash] = {
                "num_nodes": len(node_ids),
                "node_ids": node_ids,
                "coordinates": rounded_coords,
                "distances_km": dist_km.tolist(),
                "durations_min": dur_min.tolist(),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)

        except Exception as e:
            print(f"[Warning] Failed to write OSRM cache at {self.cache_path}: {e}")

    # -------------------------------------------------------------------------
    # UTILITIES AND METRICS
    # -------------------------------------------------------------------------
    @staticmethod
    def _compute_haversine_matrix(coords: np.ndarray) -> np.ndarray:
        """
        Computes great-circle pairwise distance matrix in kilometers.
        """
        if len(coords) == 0:
            return np.zeros((0, 0))
        lat = np.radians(coords[:, 0])[:, None]
        lon = np.radians(coords[:, 1])[:, None]
        dlat = lat - lat.T
        dlon = lon - lon.T
        a = np.sin(dlat / 2.0) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlon / 2.0) ** 2
        return 6371.0 * (2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))

    @staticmethod
    def _detect_column(df: pd.DataFrame, candidates: List[str]) -> str:
        for c in candidates:
            if c in df.columns:
                return c
        raise KeyError(f"None of candidate columns {candidates} were found in DataFrame columns: {df.columns.tolist()}")

    @classmethod
    def _has_coordinate_columns(cls, df: pd.DataFrame) -> bool:
        has_lat = any(c in df.columns for c in ['latitude', 'lat', 'Latitude', 'LAT', 'y'])
        has_lon = any(c in df.columns for c in ['longitude', 'lon', 'lng', 'Longitude', 'LON', 'x'])
        return has_lat and has_lon

    def _extract_coords_from_df(self, df: pd.DataFrame, location_ids: List[str]) -> np.ndarray:
        id_col = self._detect_column(df, ['poi_id', 'Location_id', 'location_id', 'id'])
        lat_col = self._detect_column(df, ['latitude', 'lat', 'Latitude', 'LAT', 'y'])
        lon_col = self._detect_column(df, ['longitude', 'lon', 'lng', 'Longitude', 'LON', 'x'])

        coords_dict = {
            str(row[id_col]): (float(row[lat_col]), float(row[lon_col]))
            for _, row in df.iterrows()
        }
        res = []
        for lid in location_ids:
            if lid in coords_dict:
                res.append(coords_dict[lid])
            else:
                res.append(self.depot_coord)
        return np.array(res, dtype=float)

    def get_asymmetry_stats(self) -> Dict[str, float]:
        """
        Quantifies matrix asymmetry (D_ij != D_ji) across the road network.
        Returns max asymmetry (km), mean asymmetry (km), and count of asymmetric pairs (> 50m).
        """
        diff = np.abs(self.dist_matrix_km - self.dist_matrix_km.T)
        M = len(self.dist_matrix_km)
        total_pairs = M * (M - 1)
        asym_pairs = int(np.sum(diff > 0.05)) if total_pairs > 0 else 0
        return {
            "max_asymmetry_km": float(np.max(diff)) if M > 0 else 0.0,
            "mean_asymmetry_km": float(np.mean(diff)) if M > 0 else 0.0,
            "asymmetric_pairs_count": asym_pairs,
            "total_directed_pairs": total_pairs,
            "asymmetric_ratio": float(asym_pairs / max(total_pairs, 1))
        }

    def get_trip_metrics(self, node_indices: List[int]) -> Dict[str, float]:
        """
        Calculates total driving distance (km) and travel duration (min) for a sequence of node indices.
        Example: [0, 4, 12, 18, N+1, 0] (Depot -> Stops -> Disposal -> Depot)
        """
        total_dist_km = 0.0
        total_dur_min = 0.0
        for i in range(len(node_indices) - 1):
            u, v = node_indices[i], node_indices[i + 1]
            total_dist_km += self.dist_matrix_km[u, v]
            total_dur_min += self.duration_matrix_min[u, v]
        return {
            "total_distance_km": float(total_dist_km),
            "total_duration_min": float(total_dur_min)
        }
