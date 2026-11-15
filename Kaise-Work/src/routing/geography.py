"""Geography and travel-matrix builders (M8) — docs/contracts.md §4.2/§4.5.

No coordinates exist in the challenge data [observed, contract §4.5], so this
module derives **synthetic, deterministic demo coordinates** from stable
SHA-256 hashes of the series keys: same inputs ⇒ identical coordinates on
every run and machine (no randomness, no dependence on ``PYTHONHASHSEED``).
They are labelled [demo assumption] and must be replaced by host data when
available — never presented as real locations.

Distances are haversine (great-circle, metres) times the configured detour
factor — an *approximation of road distance*, never a road measurement.
Provenance is therefore pinned to ``"haversine_straight_line_derived"`` and
must stay visible in all downstream outputs (AGENTS rule 9). Durations
derive from distance and the configured average speed (§4.1 units).

Deterministic: identical inputs (and config) ⇒ identical matrices and
problems; point order is depot first, then disposal sites sorted by id, then
stops sorted by (location_id, material_type) — independent of input order.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence

from src.collection.policy import Candidate
from src.data.schema import MaterialType
from src.forecasting.features import SeriesKey
from src.routing.demo_config import DEMO_STOP_SERVICE_MINUTES
from src.routing.schemas import (
    PROVENANCE_HAVERSINE,
    Depot,
    DisposalSite,
    RoutingConfig,
    RoutingProblem,
    RoutingSchemaError,
    Stop,
    TravelMatrix,
    VehicleType,
    stop_point_id,
)

__all__ = [
    "EARTH_RADIUS_M",
    "build_routing_problem",
    "build_travel_matrix",
    "haversine_distance_m",
    "synthetic_stop_coordinates",
]

# IUGG mean Earth radius ≈ 6371.0 km — a standard physical approximation,
# not a tuned demo knob.
EARTH_RADIUS_M = 6_371_000.0

# Demo spread of synthetic stops around the depot, in kilometres —
# [demo assumption] (§4.6 gives no geography; this only needs to look like a
# plausible urban collection area).
DEMO_MIN_RADIUS_KM = 1.0
DEMO_MAX_RADIUS_KM = 6.0

# Mean-meridian / parallel degree lengths (km per degree) — standard
# geodetic approximations, adequate for the demo spread.
KM_PER_DEGREE_LAT = 110.574
KM_PER_DEGREE_LON_EQUATOR = 111.320


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in **metres** (float; callers round).

    Straight-line only: multiplying by ``RoutingConfig.detour_factor``
    approximates road distance but the result must always stay labelled
    "haversine_straight_line_derived" (never "road").
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    central_angle = 2.0 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_M * central_angle


def _stable_fractions(location_id: str, material_type: MaterialType) -> tuple[float, float]:
    """Two fractions in [0, 1) hashed from the series key via SHA-256.

    Stable across processes and runs (unlike ``hash()``, which is salted per
    interpreter) — this is what makes the synthetic geography deterministic.
    """
    digest = hashlib.sha256(f"{location_id}|{material_type}".encode()).digest()
    angle_seed = int.from_bytes(digest[:8], "big")
    radius_seed = int.from_bytes(digest[8:16], "big")
    scale = float(2**64)
    return angle_seed / scale, radius_seed / scale


def synthetic_stop_coordinates(
    keys: Iterable[SeriesKey],
    depot: Depot,
    min_radius_km: float = DEMO_MIN_RADIUS_KM,
    max_radius_km: float = DEMO_MAX_RADIUS_KM,
) -> dict[SeriesKey, tuple[float, float]]:
    """Deterministic synthetic WGS84 coordinates for series keys —
    **[demo assumption]**, spread ``min_radius_km``..``max_radius_km`` around
    ``depot`` (defaults are demo values; the depot itself is synthetic).

    Same key ⇒ same coordinate on every run; no two inputs share state. The
    polar→degree conversion uses standard degree lengths at the depot's
    latitude (adequate for demo distances).
    """
    km_per_degree_lon = KM_PER_DEGREE_LON_EQUATOR * math.cos(math.radians(depot.lat))
    coordinates: dict[SeriesKey, tuple[float, float]] = {}
    for location_id, material_type in keys:
        angle_fraction, radius_fraction = _stable_fractions(location_id, material_type)
        angle_rad = 2.0 * math.pi * angle_fraction
        radius_km = min_radius_km + (max_radius_km - min_radius_km) * radius_fraction
        lat = depot.lat + (radius_km * math.cos(angle_rad)) / KM_PER_DEGREE_LAT
        lon = depot.lon + (radius_km * math.sin(angle_rad)) / km_per_degree_lon
        coordinates[(location_id, material_type)] = (lat, lon)
    return coordinates


def _ordered_points(
    depot: Depot,
    disposal_sites: Sequence[DisposalSite],
    stops: Sequence[Stop],
) -> list[tuple[str, float, float]]:
    """Contract §4.2 point order: depot, disposal sites (by id), stops (by
    key) — deterministic and independent of input order."""
    points: list[tuple[str, float, float]] = [(depot.id, depot.lat, depot.lon)]
    for site in sorted(disposal_sites, key=lambda site: site.id):
        points.append((site.id, site.lat, site.lon))
    for stop in sorted(stops, key=lambda stop: (stop.location_id, stop.material_type)):
        points.append((stop_point_id(stop), stop.lat, stop.lon))
    return points


def build_travel_matrix(
    depot: Depot,
    disposal_sites: Sequence[DisposalSite],
    stops: Sequence[Stop],
    config: RoutingConfig,
) -> TravelMatrix:
    """Derive the distance/duration matrices (§4.2) from coordinates.

    ``distance_m = round(haversine_m x config.detour_factor)`` (nearest
    metre, ties-to-even) — straight-line-derived, provenance stays
    ``"haversine_straight_line_derived"``. ``duration_min =
    round(distance_m / (avg_speed_kmh x 1000 / 60))`` (nearest minute).
    Symmetric by construction; zero diagonal.
    """
    points = _ordered_points(depot, disposal_sites, stops)
    point_ids = [point_id for point_id, _lat, _lon in points]
    n = len(points)
    metres_per_minute = config.avg_speed_kmh * 1000.0 / 60.0
    distance_m = [[0] * n for _ in range(n)]
    duration_min = [[0] * n for _ in range(n)]
    for i in range(n):
        _id_i, lat_i, lon_i = points[i]
        for j in range(i + 1, n):
            _id_j, lat_j, lon_j = points[j]
            straight_m = haversine_distance_m(lat_i, lon_i, lat_j, lon_j)
            road_approx_m = round(straight_m * config.detour_factor)
            minutes = round(road_approx_m / metres_per_minute)
            distance_m[i][j] = road_approx_m
            distance_m[j][i] = road_approx_m
            duration_min[i][j] = minutes
            duration_min[j][i] = minutes
    return TravelMatrix(
        point_ids=point_ids,
        distance_m=distance_m,
        duration_min=duration_min,
        provenance=PROVENANCE_HAVERSINE,
    )


def build_routing_problem(
    selected_candidates: Iterable[Candidate],
    depot: Depot,
    disposal_sites: Sequence[DisposalSite],
    vehicle_types: Sequence[VehicleType],
    container_volume_litres: int,  # litres [demo assumption, §4.6 default 1900]
    config: RoutingConfig,
    coordinates: Mapping[SeriesKey, tuple[float, float]],
    travel: TravelMatrix,
    service_minutes_per_stop: int = DEMO_STOP_SERVICE_MINUTES,  # minutes [demo assumption §4.6]
) -> RoutingProblem:
    """Convert §3 selected candidates into a :class:`RoutingProblem` (§4.2).

    Each candidate becomes one :class:`Stop` with ``predicted_fill_pct``
    from the forecast batch (§2.2), coordinates from ``coordinates`` (use
    :func:`synthetic_stop_coordinates` for the labelled demo geography),
    ``container_volume_litres`` and ``service_minutes_per_stop`` from config.
    Stops are ordered by key for determinism. Duplicate candidate keys are an
    error (stops must map one-to-one onto matrix point ids); a candidate
    without coordinates is an error — never silently placed.

    Collected volume/weight are derived per stop (see :class:`Stop`):
    ``round(volume x fill% / 100)`` litres, then ``round(x density)``
    kilograms with densities from ``config`` — no density is hardcoded here.
    """
    candidates = list(selected_candidates)
    candidate_keys = [(c.location_id, c.material_type) for c in candidates]
    if len(set(candidate_keys)) != len(candidate_keys):
        raise RoutingSchemaError(
            "duplicate candidate keys (location_id, material_type) in selected candidates"
        )

    stops: list[Stop] = []
    for candidate in sorted(candidates, key=lambda c: (c.location_id, c.material_type)):
        key = (candidate.location_id, candidate.material_type)
        coordinate = coordinates.get(key)
        if coordinate is None:
            raise RoutingSchemaError(
                f"no coordinates for candidate {key}; synthetic demo coordinates come "
                f"from synthetic_stop_coordinates, host data later (contract §4.5)"
            )
        stops.append(
            Stop(
                location_id=candidate.location_id,
                material_type=candidate.material_type,
                lat=coordinate[0],
                lon=coordinate[1],
                container_volume_litres=container_volume_litres,
                predicted_fill_pct=candidate.predicted_fill_pct,
                service_minutes=service_minutes_per_stop,
            )
        )

    return RoutingProblem(
        depot=depot,
        disposal_sites=list(disposal_sites),
        stops=stops,
        vehicle_types=list(vehicle_types),
        travel=travel,
        config=config,
    )
