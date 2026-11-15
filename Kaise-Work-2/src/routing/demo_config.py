"""Demo defaults for routing inputs — docs/contracts.md §4.6 v3 (2026-11-14)
plus synthetic Heilbronn depot/disposal fixtures (§4.5).

Source labels per §4.6 v3: values the challenge representative supplied
verbally on 14 Nov 2026 are **[representative]** (trusted defaults, absent
from brief and data, always echoed with their source); everything else is a
**[demo assumption]** — the challenge brief (§3, audited 2026-11-14) names
the variable *categories* only, and the data contains no coordinates,
capacities, volumes, densities or service times [observed]. All values are
request-overridable at M10/M11 (§4.6: overrides never relabel facts);
host-supplied values replace defaults in config only — never silently.

Coordinates are synthetic demo fixtures near Heilbronn (~49.15 N, 9.22 E),
labelled via ``demo_``-prefixed ids so real and simulated locations can never
be confused (M4 rule).
"""

from __future__ import annotations

from src.data.schema import MATERIALS, MaterialType
from src.routing.schemas import (
    TRAVEL_MODE_FIXED_PER_LEG,
    Depot,
    DisposalSite,
    RoutingConfig,
    TravelTimeMode,
    VehicleType,
)

__all__ = [
    "DEMO_AVG_SPEED_KMH",
    "DEMO_CONTAINERS_PER_SERIES",
    "DEMO_CONTAINER_VOLUME_LITRES",
    "DEMO_COST_PER_TRUCK_DAY_EUR",
    "DEMO_DENSITIES_KG_PER_LITRE",
    "DEMO_DENSITY_SOURCE_LABEL",
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
    "DEMO_FIXED_TRAVEL_MINUTES",
    "DEMO_FREQUENCY_DAYS",
    "DEMO_GEOGRAPHY_SEED",
    "DEMO_GEOGRAPHY_SPREAD_KM",
    "DEMO_MAX_SHIFT_MINUTES",
    "DEMO_OPERATING_DAYS_PER_WEEK",
    "DEMO_OPERATING_DAYS_PER_YEAR",
    "DEMO_SOLVER_SOLUTION_LIMIT",
    "DEMO_SOLVER_TIME_LIMIT_S",
    "DEMO_STOP_SERVICE_MINUTES",
    "DEMO_TRAVEL_TIME_MODE",
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

# --- §4.6 v3 defaults — each labelled [representative] or [demo assumption] --

DEMO_CONTAINER_VOLUME_LITRES = 3000  # litres; 3 m³ per container [representative]

# §4.6 v4 density (2026-11-14): 0.40 kg/L uniform across materials —
# [literature] German AVV conversion table, AVV 20 01 02 "Altglas
# (Flaschen-/Behälterglas, Depotcontainer)" (0.40 t/m³; the partner's
# 380 kg/m³ figure corroborates within 5 %). Request-overridable per material;
# the label below must travel with every echo of the default (§4.6: overrides
# never relabel facts).
DEMO_DENSITY_SOURCE_LABEL = (
    "[literature] German AVV table AVV 20 01 02 (entsorgen-versorgen.de, retrieved 2026-11-14)"
)

DEMO_DENSITIES_KG_PER_LITRE: dict[MaterialType, float] = {
    "brown": 0.4,
    "green": 0.4,
    "white": 0.4,
}  # kg/litre [literature] — see DEMO_DENSITY_SOURCE_LABEL (§4.6 v4)

DEMO_VEHICLE_ID = "demo_truck"  # one vehicle type in v1 §4.6 [demo assumption]
DEMO_VEHICLE_NAME = "Demo Collection Truck"  # [demo assumption]
DEMO_VEHICLE_VOLUME_CAPACITY_LITRES = 12_000  # litres [demo assumption]
DEMO_VEHICLE_WEIGHT_CAPACITY_KG = 10_000  # kilograms [demo assumption]
DEMO_VEHICLE_COUNT_AVAILABLE = 3  # vehicles available [demo assumption]
# Compartment layout stays None ⇒ equal thirds (4,000 L per material)
# [demo assumption — layout unknown, §4.6 v3].

DEMO_STOP_SERVICE_MINUTES = 5  # minutes per container [representative; per
# location? open question — docs/open_questions.md]
DEMO_DISPOSAL_SERVICE_MINUTES = 30  # minutes per disposal unload §4.6 [demo assumption]
DEMO_MAX_SHIFT_MINUTES = 480  # minutes; 8 h shift [representative]

DEMO_TRAVEL_TIME_MODE: TravelTimeMode = TRAVEL_MODE_FIXED_PER_LEG  # [representative
# reading of "10 min between containers"]
DEMO_FIXED_TRAVEL_MINUTES = 10  # minutes on EVERY leg incl. depot/disposal
# [representative] + [interpretation — open question]
DEMO_AVG_SPEED_KMH = 30.0  # km/h; urban demo speed §4.6 [demo assumption];
# used ONLY in haversine_derived mode
DEMO_DETOUR_FACTOR = 1.4  # haversine → approx road factor §4.6 [demo assumption];
# provenance stays "straight-line derived"

DEMO_COST_PER_TRUCK_DAY_EUR = 500.0  # euros per truck-day [representative]
DEMO_OPERATING_DAYS_PER_WEEK = 5  # days/week [representative] (echo/display)
DEMO_OPERATING_DAYS_PER_YEAR = 200  # days/year [representative] (echo/display)

# Geography sensitivity knobs (§4.6 v3, user decision ①): parameterise the
# SYNTHETIC layout only — defaults reproduce the current coordinates exactly
# (regression-tested). [demo assumption knobs]
DEMO_GEOGRAPHY_SEED = 0  # 0 = current SHA-256 layout
DEMO_GEOGRAPHY_SPREAD_KM = 6.0  # km; outer radius of the current 1-6 km band

# --- §4.6 v4 knobs (2026-11-14) ----------------------------------------------

# One igloo per colour per location; 441/449 sites carry all three colours
# [observed]. Multiplies litres collected AND stop service minutes; predicted
# fill % unchanged (§4.2 v4) [demo assumption — Q11].
DEMO_CONTAINERS_PER_SERIES = 1

# naive_fixed_frequency cycle length (§4.7/§5.2.4): due iff
# as_of - last_emptying_date >= frequency_days; observed median gap 28 days
# [demo assumption].
DEMO_FREQUENCY_DAYS = 28

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
    """The single §4.6 demo vehicle type (fresh instance per call).

    ``compartment_volume_litres`` stays ``None`` ⇒ equal thirds
    (12,000 / 3 = 4,000 L per material) [demo assumption — layout unknown,
    §4.6 v3]."""
    return VehicleType(
        id=DEMO_VEHICLE_ID,
        name=DEMO_VEHICLE_NAME,
        volume_capacity_litres=DEMO_VEHICLE_VOLUME_CAPACITY_LITRES,
        weight_capacity_kg=DEMO_VEHICLE_WEIGHT_CAPACITY_KG,
        count_available=DEMO_VEHICLE_COUNT_AVAILABLE,
    )


def demo_routing_config() -> RoutingConfig:
    """All §4.6 v3 defaults in one validated :class:`RoutingConfig`.

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
        travel_time_mode=DEMO_TRAVEL_TIME_MODE,
        fixed_travel_minutes=DEMO_FIXED_TRAVEL_MINUTES,
        cost_per_truck_day_eur=DEMO_COST_PER_TRUCK_DAY_EUR,
        operating_days_per_week=DEMO_OPERATING_DAYS_PER_WEEK,
        operating_days_per_year=DEMO_OPERATING_DAYS_PER_YEAR,
        geography_seed=DEMO_GEOGRAPHY_SEED,
        geography_spread_km=DEMO_GEOGRAPHY_SPREAD_KM,
        containers_per_series=DEMO_CONTAINERS_PER_SERIES,
        frequency_days=DEMO_FREQUENCY_DAYS,
    )
