"""Naive fixed-order collection baseline (M12) — user-defined demo comparison.

Deterministic simulation, **no OR-Tools** (AGENTS rule 8 applies to routing
optimisation; this module is the deliberately naive comparison anchor for the
M9 optimiser, defined by the user on 2026-11-14). It visits the stops of the
problem in one of two fixed deterministic orders — the data has no area/zone
field [observed, contract §4.5], so every visiting order is a **[demo
assumption]**, never derived from real geography:

- ``naive_fixed_order``: lexicographic ``(location_id, material_type)`` over
  all stops — the M12 v1 baseline, kept for continuity (docs/tests only,
  contract §4.7: not part of the API scenarios array).
- ``naive_sweep_order`` (v2, §4.7): area sweep — stops bucketed into grid
  cells of ``SWEEP_CELL_SIZE_DEG`` degrees (≈ 1 km, [demo assumption]), cells
  visited in fixed row-major order (lat band ascending, then lon ascending),
  stops within a cell in lexicographic ``(location_id, material_type)``
  order. Powers both ``naive_sweep_all`` (all series) and
  ``naive_sweep_selected`` (policy-selected stops only) API scenarios.

Simulation rules (user-defined, deterministic):
- Per stop, collect ``round(container_volume_litres x predicted_fill_pct/100)``
  litres, then ``round(x density)`` kilograms — the same :class:`Stop` derived
  quantities the optimiser loads (densities from ``RoutingConfig``, never
  hardcoded).
- Before a stop that would exceed the vehicle's volume or weight capacity, the
  vehicle first visits the disposal site nearest to its current position (by
  travel minutes, ties by site id), unloads (disposal ``service_minutes``) and
  its load resets to zero.
- When the next leg + service would exceed ``max_shift_minutes``, the vehicle
  returns to the depot and the **next** vehicle continues with that same stop.
- Vehicles exhausted with stops remaining ⇒ those stops are ``unserved`` with
  a deterministic reason (never silently dropped, contract §4.4).
- A stop that exceeds the vehicle capacity even when the vehicle is empty, or
  whose empty-vehicle depot round trip exceeds the shift, cannot be served by
  the simulation at all and is ``unserved`` with the deciding numbers (the
  §4.6 demo fleet has one vehicle type, so this matches the optimiser's
  per-stop verdicts).
- Stops named in ``no_forecast_stop_keys`` (no persistence value at as_of,
  contract §2.3) are still visited but collect **0 L / 0 kg** — labelled in
  the output, never fabricated.

Time accounting: travel uses the travel-matrix durations; each node's service
time is paid once on arrival (depot service is zero) — the same totals the
optimiser reports (sum of leg durations + all non-depot services). A route's
duration can exceed ``max_shift_minutes`` only through the mandatory
return-to-depot leg after the last stop that still fitted; such routes are
listed in ``shift_violations`` (contract §4.4: violations reported, never
hidden).

Output mirrors the contract §4.3 keys (``totals``, ``unserved``,
``fleet_recommendation``, ``distance_provenance``) plus ``method`` =
``"naive_fixed_order"`` or ``"naive_sweep_order"``. Distance provenance is
echoed from the travel matrix untouched — straight-line-derived matrices are
never presented as road distance (contract §4.2).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

from src.forecasting.features import SeriesKey
from src.routing.fleet import FleetRecommendation, recommend_fleet_for_problem
from src.routing.schemas import (
    Depot,
    DisposalSite,
    Provenance,
    RoutingProblem,
    Stop,
    VehicleType,
    stop_point_id,
)
from src.routing.solver import SolutionTotals, UnservedStop

__all__ = [
    "METHOD_NAIVE_FIXED_ORDER",
    "METHOD_NAIVE_SWEEP_ORDER",
    "SWEEP_CELL_SIZE_DEG",
    "NaiveRoute",
    "NaiveSolution",
    "NaiveStatus",
    "naive_fixed_order_simulation",
    "naive_sweep_simulation",
    "sweep_visit_order",
]

METHOD_NAIVE_FIXED_ORDER: Literal["naive_fixed_order"] = "naive_fixed_order"
METHOD_NAIVE_SWEEP_ORDER: Literal["naive_sweep_order"] = "naive_sweep_order"

NaiveMethod: TypeAlias = Literal["naive_fixed_order", "naive_sweep_order"]

# §4.7 area-sweep grid cell size in degrees (≈ 1 km) [demo assumption — the
# data has no area field, observed; every visiting order is a labelled choice].
SWEEP_CELL_SIZE_DEG = 0.01


def sweep_visit_order(stops: Iterable[Stop]) -> list[Stop]:
    """§4.7 area-sweep visiting order (deterministic): grid cells of
    ``SWEEP_CELL_SIZE_DEG`` degrees bucketed by ``floor(coordinate / cell)``,
    visited row-major (lat band ascending, then lon ascending), stops within
    a cell in lexicographic ``(location_id, material_type)`` order."""
    cell = SWEEP_CELL_SIZE_DEG

    def cell_of(stop: Stop) -> tuple[int, int]:
        return math.floor(stop.lat / cell), math.floor(stop.lon / cell)

    return sorted(
        stops,
        key=lambda stop: (
            *cell_of(stop),
            stop.location_id,
            stop.material_type,
        ),
    )


NaiveStatus: TypeAlias = Literal["complete", "incomplete"]
"""Simulation outcome: ``complete`` iff every stop was served; ``incomplete``
means at least one stop is unserved (fleet exhaustion, capacity or shift —
see the per-stop reasons; contract §4.4: never hidden)."""


@dataclass(frozen=True)
class NaiveRoute:
    """One vehicle's fixed-order work block — mirrors contract §4.3 ``Route``.

    ``vehicle_index`` counts over the expanded fleet (types by id, each
    repeated ``count_available`` times — same expansion as the optimiser).
    """

    vehicle_index: int
    vehicle_type_id: str
    sequence: list[Depot | DisposalSite | Stop]  # depot start ... depot end
    load_progression: list[tuple[int, int]]  # (volume_litres, weight_kg) after each stop
    distance_m: int
    duration_minutes: int


@dataclass(frozen=True)
class NaiveSolution:
    """Complete naive-baseline output — contract §4.3 keys + method label."""

    method: NaiveMethod
    status: NaiveStatus
    routes: list[NaiveRoute]
    unserved: list[UnservedStop]
    totals: SolutionTotals
    fleet_recommendation: FleetRecommendation
    distance_provenance: Provenance  # echoed from TravelMatrix (§4.2)
    no_forecast_stop_keys: list[SeriesKey]  # visited with 0 L / 0 kg, labelled
    shift_violations: list[str]  # routes whose return leg overran the shift (§4.4)


def _expanded_fleet(problem: RoutingProblem) -> list[VehicleType]:
    """Vehicle number -> its type; types by id, each repeated count_available
    times — the same deterministic expansion the optimiser uses."""
    ordered = sorted(problem.vehicle_types, key=lambda vehicle_type: vehicle_type.id)
    return [vehicle_type for vehicle_type in ordered for _ in range(vehicle_type.count_available)]


def _oversize_reason(
    stop: Stop, vehicle_type: VehicleType, volume_litres: int, weight_kg: int
) -> str:
    if volume_litres > vehicle_type.volume_capacity_litres:
        return (
            f"collected volume {volume_litres} L exceeds the {vehicle_type.id} volume "
            f"capacity {vehicle_type.volume_capacity_litres} L even when the vehicle is empty"
        )
    return (
        f"collected weight {weight_kg} kg exceeds the {vehicle_type.id} weight capacity "
        f"{vehicle_type.weight_capacity_kg} kg even when the vehicle is empty"
    )


def _shift_reason(needed_min: int, problem: RoutingProblem) -> str:
    return (
        f"shift_limit_exceeded: reaching and serving this stop takes {needed_min} min "
        f"even for an empty vehicle at the depot, exceeding max_shift_minutes "
        f"{problem.config.max_shift_minutes} min"
    )


def _fleet_exhausted_reason(problem: RoutingProblem) -> str:
    available = sum(vehicle_type.count_available for vehicle_type in problem.vehicle_types)
    return (
        f"fleet_exhausted: all {available} vehicles reached max_shift_minutes "
        f"{problem.config.max_shift_minutes} min with stops remaining in fixed order"
    )


def _simulate_order(
    problem: RoutingProblem,
    ordered_stops: list[Stop],
    no_forecast_stop_keys: Sequence[SeriesKey],
    method: NaiveMethod,
) -> NaiveSolution:
    """Shared simulation core: visit ``ordered_stops`` in the given fixed
    order with the deterministic physics below (capacities, nearest-disposal
    unload, shift hand-over, fleet exhaustion — never silent drops, §4.4).
    Both ``naive_fixed_order_simulation`` and ``naive_sweep_simulation`` call
    it with their respective orders; same inputs ⇒ identical output."""
    matrix = problem.travel
    index = {point_id: i for i, point_id in enumerate(matrix.point_ids)}
    distance_m = matrix.distance_m
    duration_min = matrix.duration_min
    max_shift = problem.config.max_shift_minutes
    densities = problem.config.densities_kg_per_litre
    depot = problem.depot

    def dist(a_pid: str, b_pid: str) -> int:
        return distance_m[index[a_pid]][index[b_pid]]

    def minutes(a_pid: str, b_pid: str) -> int:
        return duration_min[index[a_pid]][index[b_pid]]

    def pid_of(node: Depot | DisposalSite | Stop) -> str:
        if isinstance(node, Stop):
            return stop_point_id(node)
        return node.id

    def nearest_disposal(pos_pid: str) -> DisposalSite:
        return min(
            problem.disposal_sites,
            key=lambda site: (minutes(pos_pid, site.id), site.id),
        )

    fleet = _expanded_fleet(problem)

    routes: list[NaiveRoute] = []
    unserved: list[UnservedStop] = []
    shift_violations: list[str] = []

    # Current vehicle state (fresh start on vehicle 0 at the depot).
    vehicle_index = 0
    vehicle_type = fleet[0]
    pos_pid = depot.id
    sequence: list[Depot | DisposalSite | Stop] = [depot]
    volume = 0  # litres aboard
    weight = 0  # kilograms aboard
    elapsed = 0  # minutes since depot departure (travel + arrival services)
    route_distance = 0
    progression: list[tuple[int, int]] = []

    def return_to_depot_and_emit() -> None:
        """Close the current vehicle's route: travel home, emit the route,
        report a shift overrun if the return leg pushed it over the cap."""
        nonlocal elapsed, route_distance, pos_pid
        elapsed += minutes(pos_pid, depot.id)
        route_distance += dist(pos_pid, depot.id)
        sequence.append(depot)
        pos_pid = depot.id
        if elapsed > max_shift:
            shift_violations.append(
                f"vehicle_index {vehicle_index} ({vehicle_type.id}): route duration "
                f"{elapsed} min exceeds max_shift_minutes {max_shift} min by "
                f"{elapsed - max_shift} min through the mandatory return-to-depot leg"
            )
        routes.append(
            NaiveRoute(
                vehicle_index=vehicle_index,
                vehicle_type_id=vehicle_type.id,
                sequence=sequence,
                load_progression=progression,
                distance_m=route_distance,
                duration_minutes=elapsed,
            )
        )

    def reset_vehicle_state() -> None:
        nonlocal vehicle_index, vehicle_type, sequence, volume, weight, elapsed
        nonlocal route_distance, progression
        vehicle_index += 1
        if vehicle_index < len(fleet):
            vehicle_type = fleet[vehicle_index]
        sequence = [depot]
        volume = 0
        weight = 0
        elapsed = 0
        route_distance = 0
        progression = []

    stop_cursor = 0
    while stop_cursor < len(ordered_stops):
        if vehicle_index >= len(fleet):
            # Vehicles exhausted — every remaining stop is unserved (§4.4).
            unserved.extend(
                UnservedStop(
                    stop_key=(stop.location_id, stop.material_type),
                    reason=_fleet_exhausted_reason(problem),
                )
                for stop in ordered_stops[stop_cursor:]
            )
            break

        stop = ordered_stops[stop_cursor]
        stop_pid = stop_point_id(stop)
        collected_volume = stop.collected_volume_litres
        collected_weight = stop.collected_weight_kg(densities[stop.material_type])

        # 1) A stop that cannot fit even an empty vehicle is never servable.
        if (
            collected_volume > vehicle_type.volume_capacity_litres
            or collected_weight > vehicle_type.weight_capacity_kg
        ):
            unserved.append(
                UnservedStop(
                    stop_key=(stop.location_id, stop.material_type),
                    reason=_oversize_reason(stop, vehicle_type, collected_volume, collected_weight),
                )
            )
            stop_cursor += 1
            continue

        # 2) Capacity full enough to need an unload first: detour via the
        # nearest disposal site (travel + its unload service) — only possible
        # with load aboard; an empty vehicle passed check 1.
        needs_disposal = (
            volume + collected_volume > vehicle_type.volume_capacity_litres
            or weight + collected_weight > vehicle_type.weight_capacity_kg
        )
        if needs_disposal:
            disposal = nearest_disposal(pos_pid)
            needed_min = (
                minutes(pos_pid, disposal.id)
                + disposal.service_minutes
                + minutes(disposal.id, stop_pid)
                + stop.service_minutes
            )
        else:
            needed_min = minutes(pos_pid, stop_pid) + stop.service_minutes

        # 3) Shift: when the next leg + service would exceed the cap, return
        # to the depot; the next vehicle continues with the same stop.
        if elapsed + needed_min > max_shift:
            if elapsed == 0:
                # Fresh vehicle at the depot: no vehicle in the fleet can ever
                # serve this stop within the shift (check 1 passed, load is 0).
                unserved.append(
                    UnservedStop(
                        stop_key=(stop.location_id, stop.material_type),
                        reason=_shift_reason(needed_min, problem),
                    )
                )
                stop_cursor += 1
                continue
            return_to_depot_and_emit()
            reset_vehicle_state()
            continue  # retry the same stop with the next vehicle

        # 4) Serve the stop (via the disposal unload first when required).
        if needs_disposal:
            disposal = nearest_disposal(pos_pid)
            route_distance += dist(pos_pid, disposal.id)
            elapsed += minutes(pos_pid, disposal.id) + disposal.service_minutes
            sequence.append(disposal)
            volume = 0
            weight = 0
            pos_pid = disposal.id
        route_distance += dist(pos_pid, stop_pid)
        elapsed += minutes(pos_pid, stop_pid) + stop.service_minutes
        sequence.append(stop)
        volume += collected_volume
        weight += collected_weight
        progression.append((volume, weight))
        pos_pid = stop_pid
        stop_cursor += 1

    if len(sequence) > 1 and vehicle_index < len(fleet):
        return_to_depot_and_emit()

    served_stops = [node for route in routes for node in route.sequence if isinstance(node, Stop)]
    totals = SolutionTotals(
        distance_m=sum(route.distance_m for route in routes),
        duration_min=sum(route.duration_minutes for route in routes),
        collected_volume_litres=sum(stop.collected_volume_litres for stop in served_stops),
        collected_weight_kg=sum(
            stop.collected_weight_kg(densities[stop.material_type]) for stop in served_stops
        ),
        stops_served=len(served_stops),
        stops_total=len(ordered_stops),
    )

    return NaiveSolution(
        method=method,
        status="complete" if not unserved else "incomplete",
        routes=routes,
        unserved=sorted(unserved, key=lambda entry: entry.stop_key),
        totals=totals,
        fleet_recommendation=recommend_fleet_for_problem(problem),
        distance_provenance=matrix.provenance,
        no_forecast_stop_keys=sorted(set(no_forecast_stop_keys)),
        shift_violations=shift_violations,
    )


def naive_fixed_order_simulation(
    problem: RoutingProblem,
    no_forecast_stop_keys: Sequence[SeriesKey] = (),
) -> NaiveSolution:
    """Legacy M12 v1 baseline: lexicographic ``(location_id, material_type)``
    order over **all** problem stops (contract §4.7: docs/tests baseline only,
    not part of the API scenarios array).

    Deterministic: same problem (and keys) ⇒ identical
    :class:`NaiveSolution`. Distances/durations come from the travel matrix;
    provenance is echoed, never renamed.
    """
    ordered = sorted(problem.stops, key=lambda stop: (stop.location_id, stop.material_type))
    return _simulate_order(problem, ordered, no_forecast_stop_keys, METHOD_NAIVE_FIXED_ORDER)


def naive_sweep_simulation(
    problem: RoutingProblem,
    no_forecast_stop_keys: Sequence[SeriesKey] = (),
    stops: Iterable[Stop] | None = None,
) -> NaiveSolution:
    """§4.7 area-sweep baseline (v2): ``sweep_visit_order`` over ``stops``
    (default: **all** problem stops). Passing the policy-selected subset gives
    the ``naive_sweep_selected`` scenario; all stops gives
    ``naive_sweep_all`` — identical simulation physics in both cases.

    Deterministic: same problem (and stops) ⇒ identical
    :class:`NaiveSolution`. Distances/durations come from the travel matrix;
    provenance is echoed, never renamed.
    """
    ordered = sweep_visit_order(problem.stops if stops is None else stops)
    return _simulate_order(problem, ordered, no_forecast_stop_keys, METHOD_NAIVE_SWEEP_ORDER)
