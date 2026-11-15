"""Demo defaults for routing inputs — docs/contracts.md §4.6 (user decision
2026-11-14) plus synthetic Heilbronn depot/disposal fixtures (§4.5).

**Every value below is a [demo assumption]**: the challenge brief (§3,
audited 2026-11-14) names the variable *categories* only — no numeric values
— and the data contains no coordinates, capacities, volumes, densities or
service times [observed]. Values here are request-overridable at M10/M11
(§4.6: overrides never relabel facts); host-supplied values replace defaults
in config only — never silently.

Coordinates are synthetic demo fixtures near Heilbronn (~49.15 N, 9.22 E),
labelled via ``demo_``-prefixed ids so real and simulated locations can never
be confused (M4 rule).
"""

from __future__ import annotations

from src.data.schema import MATERIALS, MaterialType
from src.routing.schemas import Depot, DisposalSite, RoutingConfig, VehicleType

__all__ = [
    "DEMO_AVG_SPEED_KMH",
    "DEMO_CONTAINER_VOLUME_LITRES",
    "DEMO_DENSITIES_KG_PER_LITRE",
    "DEMO_DEPOT_ID",
    "DEMO_DEPOT_LAT",
    "DEMO_DEPOT_LON",
    "DEMO_DEPOT_NAME",
    "DEMO_DETOUR_FACTOR",
    "DEMO_DISPOSAL_ID",
    "DEMO_DISPOSAL_LAT",
    "DEMO_DISPOSAL_LON",
    "DEMO_DISPOSAL_NAME",
    "DEMO_DISPOSAL_SERVICE_MINUTES",
    "DEMO_MAX_SHIFT_MINUTES",
    "DEMO_SOLVER_SOLUTION_LIMIT",
    "DEMO_SOLVER_TIME_LIMIT_S",
    "DEMO_STOP_SERVICE_MINUTES",
    "DEMO_VEHICLE_COUNT_AVAILABLE",
    "DEMO_VEHICLE_ID",
    "DEMO_VEHICLE_NAME",
    "DEMO_VEHICLE_VOLUME_CAPACITY_LITRES",
    "DEMO_VEHICLE_WEIGHT_CAPACITY_KG",
    "demo_depot",
    "demo_disposal_site",
    "demo_routing_config",
    "demo_vehicle_type",
]

# --- §4.6 user-agreed defaults — each [demo assumption] --------------------

DEMO_CONTAINER_VOLUME_LITRES = 1900  # litres; typical glass igloo size [demo assumption]

DEMO_DENSITIES_KG_PER_LITRE: dict[MaterialType, float] = {
    # conservative loose-cullet demo value, uniform across materials §4.6 [demo assumption]
    "brown": 0.5,
    "green": 0.5,
    "white": 0.5,
}

DEMO_VEHICLE_ID = "demo_truck"  # one vehicle type in v1 §4.6 [demo assumption]
DEMO_VEHICLE_NAME = "Demo Collection Truck"  # [demo assumption]
DEMO_VEHICLE_VOLUME_CAPACITY_LITRES = 12_000  # litres [demo assumption]
DEMO_VEHICLE_WEIGHT_CAPACITY_KG = 10_000  # kilograms [demo assumption]
DEMO_VEHICLE_COUNT_AVAILABLE = 3  # vehicles available [demo assumption]

DEMO_STOP_SERVICE_MINUTES = 10  # minutes per stop §4.6 [demo assumption]
DEMO_DISPOSAL_SERVICE_MINUTES = 30  # minutes per disposal unload §4.6 [demo assumption]
DEMO_MAX_SHIFT_MINUTES = 480  # minutes; 8 h demo cap §4.6 [demo assumption]

DEMO_AVG_SPEED_KMH = 30.0  # km/h; urban demo speed §4.6 [demo assumption]
DEMO_DETOUR_FACTOR = 1.4  # haversine → approx road factor §4.6 [demo assumption]

# --- §4.6 v2 solver defaults (user-approved 2026-11-14) ---------------------

# Primary stopping criterion (§4.4/§4.7): a fixed solution budget — repeated
# solves that reach it return identical totals.distance_m [demo assumption].
DEMO_SOLVER_SOLUTION_LIMIT = 200

# Safety cap only (§4.7): fires before the solution limit ⇒ status "timeout",
# run explicitly not reproducible [demo assumption].
DEMO_SOLVER_TIME_LIMIT_S = 30.0

# --- Synthetic demo geography (§4.5: no real coordinates exist) ------------

DEMO_DEPOT_ID = "demo_depot"  # synthetic id prefix guards real/simulated confusion
DEMO_DEPOT_NAME = "Demo Depot Heilbronn (synthetic)"  # [demo assumption]
DEMO_DEPOT_LAT = 49.15  # WGS84 degrees; near Heilbronn [demo assumption]
DEMO_DEPOT_LON = 9.22  # WGS84 degrees; near Heilbronn [demo assumption]

DEMO_DISPOSAL_ID = "demo_disposal_1"  # synthetic id
DEMO_DISPOSAL_NAME = "Demo Disposal Site Heilbronn (synthetic)"  # [demo assumption]
DEMO_DISPOSAL_LAT = 49.17  # WGS84 degrees; ~3.7 km straight line from depot [demo assumption]
DEMO_DISPOSAL_LON = 9.26  # WGS84 degrees [demo assumption]


def demo_depot() -> Depot:
    """Synthetic demo depot near Heilbronn — [demo assumption], labelled."""
    return Depot(
        id=DEMO_DEPOT_ID,
        name=DEMO_DEPOT_NAME,
        lat=DEMO_DEPOT_LAT,
        lon=DEMO_DEPOT_LON,
    )


def demo_disposal_site() -> DisposalSite:
    """Synthetic demo disposal site near Heilbronn — [demo assumption]."""
    return DisposalSite(
        id=DEMO_DISPOSAL_ID,
        name=DEMO_DISPOSAL_NAME,
        lat=DEMO_DISPOSAL_LAT,
        lon=DEMO_DISPOSAL_LON,
        service_minutes=DEMO_DISPOSAL_SERVICE_MINUTES,
    )


def demo_vehicle_type() -> VehicleType:
    """The single §4.6 demo vehicle type (fresh instance per call)."""
    return VehicleType(
        id=DEMO_VEHICLE_ID,
        name=DEMO_VEHICLE_NAME,
        volume_capacity_litres=DEMO_VEHICLE_VOLUME_CAPACITY_LITRES,
        weight_capacity_kg=DEMO_VEHICLE_WEIGHT_CAPACITY_KG,
        count_available=DEMO_VEHICLE_COUNT_AVAILABLE,
    )


def demo_routing_config() -> RoutingConfig:
    """All §4.6 defaults in one validated :class:`RoutingConfig`.

    Fresh instances per call (the densities dict is mutable; callers must
    never share state across requests).
    """
    return RoutingConfig(
        max_shift_minutes=DEMO_MAX_SHIFT_MINUTES,
        densities_kg_per_litre={
            material: DEMO_DENSITIES_KG_PER_LITRE[material] for material in MATERIALS
        },
        detour_factor=DEMO_DETOUR_FACTOR,
        avg_speed_kmh=DEMO_AVG_SPEED_KMH,
        solver_solution_limit=DEMO_SOLVER_SOLUTION_LIMIT,
        solver_time_limit_s=DEMO_SOLVER_TIME_LIMIT_S,
    )
