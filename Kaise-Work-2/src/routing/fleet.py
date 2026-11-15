"""Fleet-size recommendation (M9) — docs/contracts.md §4.3/§4.4 and challenge
brief §4 ("recommend fleet size from total weight and volume").

§4.4 protocol: per vehicle type, ``count = max(⌈total_volume / volume_cap⌉,
⌈total_weight / weight_cap⌉)``; both ceilings are reported as ``basis`` so the
dominating dimension is visible. Totals use **all** stops of the problem
(served and unserved): fleet sizing addresses the full demand of the batch —
stops the solver had to leave unserved are exactly why a larger fleet would be
recommended. The recommendation is a *requirement* and is never clamped to
``count_available``; a requirement above the available count is actionable
output, not an error. [protocol choice v1 — document in the model card]

When the problem carries more than one vehicle type, the single §4.3
recommendation reports the type with the smallest required count (ties broken
by type id ascending) [protocol choice v1; §4.6 demo has one type].

Deterministic: integer ceil arithmetic only, no floats, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.routing.schemas import (
    RoutingProblem,
    RoutingSchemaError,
    VehicleType,
    effective_collected_volume_litres,
    effective_collected_weight_kg,
)

__all__ = [
    "FleetBasis",
    "FleetRecommendation",
    "fleet_recommendation",
    "recommend_fleet_for_problem",
]


@dataclass(frozen=True)
class FleetBasis:
    """The two §4.4 ceilings a recommendation is the max of — contract §4.3
    ``basis: {ceil_by_volume, ceil_by_weight}``."""

    ceil_by_volume: int  # ⌈total litres / volume capacity⌉ [predicted]
    ceil_by_weight: int  # ⌈total kilograms / weight capacity⌉ [predicted]


@dataclass(frozen=True)
class FleetRecommendation:
    """One fleet-size recommendation — contract §4.3."""

    vehicle_type_id: str
    count: int  # required vehicles [predicted]; never clamped to count_available
    basis: FleetBasis


def _require_non_negative_int(field_name: str, value: int) -> None:
    """True ints only (bool excluded); must be >= 0 (a zero total is valid)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RoutingSchemaError(
            f"{field_name} must be an int, got {type(value).__name__} ({value!r})"
        )
    if value < 0:
        raise RoutingSchemaError(f"{field_name} must be >= 0, got {value}")


def _ceil_div(total: int, capacity: int) -> int:
    """Integer ⌈total / capacity⌉ — no float rounding for large totals."""
    return (total + capacity - 1) // capacity


def fleet_recommendation(
    collected_volume_litres: int,  # litres [predicted]
    collected_weight_kg: int,  # kilograms [predicted]
    vehicle_type: VehicleType,
) -> FleetRecommendation:
    """§4.4 fleet math for one vehicle type and one demand total."""
    _require_non_negative_int("collected_volume_litres", collected_volume_litres)
    _require_non_negative_int("collected_weight_kg", collected_weight_kg)
    ceil_by_volume = _ceil_div(collected_volume_litres, vehicle_type.volume_capacity_litres)
    ceil_by_weight = _ceil_div(collected_weight_kg, vehicle_type.weight_capacity_kg)
    return FleetRecommendation(
        vehicle_type_id=vehicle_type.id,
        count=max(ceil_by_volume, ceil_by_weight),
        basis=FleetBasis(ceil_by_volume=ceil_by_volume, ceil_by_weight=ceil_by_weight),
    )


def demand_totals(problem: RoutingProblem) -> tuple[int, int]:
    """Total demand volume/weight over **all** stops of the problem (litres,
    kilograms) — the effective §4.2 v4 quantities (per-material densities from
    the routing config plus the ``containers_per_series`` multiplier), the
    same quantities the solver loads onto vehicles."""
    total_volume = 0
    total_weight = 0
    for stop in problem.stops:
        total_volume += effective_collected_volume_litres(stop, problem.config)
        total_weight += effective_collected_weight_kg(stop, problem.config)
    return total_volume, total_weight


def recommend_fleet_for_problem(problem: RoutingProblem) -> FleetRecommendation:
    """Fleet recommendation for a full :class:`RoutingProblem` (§4.4).

    Totals cover every stop (served and unserved — full demand, see module
    docstring); per-type counts are computed with :func:`fleet_recommendation`
    and the type with the smallest required count is reported, ties broken by
    id ascending [protocol choice v1].
    """
    total_volume, total_weight = demand_totals(problem)
    recommendations = [
        fleet_recommendation(total_volume, total_weight, vt) for vt in problem.vehicle_types
    ]
    return min(recommendations, key=lambda rec: (rec.count, rec.vehicle_type_id))
