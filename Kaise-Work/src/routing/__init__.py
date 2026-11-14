"""Geography/fleet inputs and travel matrices (M8) — docs/contracts.md §4.

Validated input schemas (:mod:`src.routing.schemas`), §4.6 demo defaults
(:mod:`src.routing.demo_config`, all values [demo assumption]) and the
deterministic matrix/problem builders (:mod:`src.routing.geography`).
Distances are haversine straight-line x detour factor — provenance stays
``"haversine_straight_line_derived"``, never "road". OR-Tools solving
arrives in M9.
"""

from __future__ import annotations

from src.routing.demo_config import (
    DEMO_AVG_SPEED_KMH,
    DEMO_CONTAINER_VOLUME_LITRES,
    DEMO_DENSITIES_KG_PER_LITRE,
    DEMO_DETOUR_FACTOR,
    DEMO_DISPOSAL_SERVICE_MINUTES,
    DEMO_MAX_SHIFT_MINUTES,
    DEMO_SOLVER_TIME_LIMIT_S,
    DEMO_STOP_SERVICE_MINUTES,
    DEMO_VEHICLE_COUNT_AVAILABLE,
    DEMO_VEHICLE_ID,
    DEMO_VEHICLE_VOLUME_CAPACITY_LITRES,
    DEMO_VEHICLE_WEIGHT_CAPACITY_KG,
    demo_depot,
    demo_disposal_site,
    demo_routing_config,
    demo_vehicle_type,
)
from src.routing.fleet import (
    FleetBasis,
    FleetRecommendation,
    fleet_recommendation,
    recommend_fleet_for_problem,
)
from src.routing.geography import (
    build_routing_problem,
    build_travel_matrix,
    haversine_distance_m,
    synthetic_stop_coordinates,
)
from src.routing.schemas import (
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
from src.routing.solver import (
    Route,
    RoutingSolution,
    RoutingSolverError,
    SolutionStatus,
    SolutionTotals,
    UnservedStop,
    solve,
)

__all__ = [
    "DEMO_AVG_SPEED_KMH",
    "DEMO_CONTAINER_VOLUME_LITRES",
    "DEMO_DENSITIES_KG_PER_LITRE",
    "DEMO_DETOUR_FACTOR",
    "DEMO_DISPOSAL_SERVICE_MINUTES",
    "DEMO_MAX_SHIFT_MINUTES",
    "DEMO_SOLVER_TIME_LIMIT_S",
    "DEMO_STOP_SERVICE_MINUTES",
    "DEMO_VEHICLE_COUNT_AVAILABLE",
    "DEMO_VEHICLE_ID",
    "DEMO_VEHICLE_VOLUME_CAPACITY_LITRES",
    "DEMO_VEHICLE_WEIGHT_CAPACITY_KG",
    "Depot",
    "DisposalSite",
    "FleetBasis",
    "FleetRecommendation",
    "Route",
    "RoutingConfig",
    "RoutingProblem",
    "RoutingSchemaError",
    "RoutingSolution",
    "RoutingSolverError",
    "SolutionStatus",
    "SolutionTotals",
    "Stop",
    "TravelMatrix",
    "UnservedStop",
    "VehicleType",
    "build_routing_problem",
    "build_travel_matrix",
    "demo_depot",
    "demo_disposal_site",
    "demo_routing_config",
    "demo_vehicle_type",
    "fleet_recommendation",
    "haversine_distance_m",
    "recommend_fleet_for_problem",
    "solve",
    "stop_point_id",
    "synthetic_stop_coordinates",
]
