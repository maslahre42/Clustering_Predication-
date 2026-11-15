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
- Compartments (§4.2 v3): materials are collected separated, so the binding
  volume bound per vehicle is the material's COMPARTMENT capacity (``None``
  layout ⇒ equal thirds). A stop whose collected volume exceeds its
  material's compartment even on an empty vehicle is unserved; before a stop
  that would overflow its material's compartment (or the total volume/weight
  capacity), the vehicle first visits the disposal site nearest to its
  current position (by travel minutes, ties by site id), unloads (disposal
  ``service_minutes``) and EVERY material dimension resets to zero.
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
``"naive_fixed_order"`` (docs/tests only), ``"naive_sweep_order"`` (§4.7 v2
scenarios) or ``"naive_fixed_frequency"`` (§4.7 v4 status quo: only series
due under the fixed ``frequency_days`` cycle, :func:`due_series_keys`).
Distance provenance is echoed from the travel matrix untouched —
straight-line-derived matrices are never presented as road distance
(contract §4.2).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

from src.data.schema import MATERIALS, MaterialType
from src.forecasting.features import SeriesKey
from src.routing.fleet import FleetRecommendation, recommend_fleet_for_problem
from src.routing.schemas import (
    Depot,
    DisposalSite,
    Provenance,
    RoutingProblem,
    Stop,
    VehicleType,
    effective_collected_volume_litres,
    effective_collected_weight_kg,
    effective_service_minutes,
    stop_point_id,
)
from src.routing.solver import SolutionTotals, UnservedStop, derive_shift_totals

__all__ = [
    "METHOD_NAIVE_FIXED_FREQUENCY",
    "METHOD_NAIVE_FIXED_ORDER",
    "METHOD_NAIVE_SWEEP_ORDER",
    "SWEEP_CELL_SIZE_DEG",
    "NaiveRoute",
    "NaiveSolution",
    "NaiveStatus",
    "due_series_keys",
    "naive_fixed_frequency_simulation",
    "naive_fixed_order_simulation",
    "naive_sweep_simulation",
    "sweep_visit_order",
]

METHOD_NAIVE_FIXED_ORDER: Literal["naive_fixed_order"] = "naive_fixed_order"
METHOD_NAIVE_SWEEP_ORDER: Literal["naive_sweep_order"] = "naive_sweep_order"
# §4.7 v4 status-quo scenario: only series DUE under the fixed k-day cycle
# (as_of - last_emptying_date >= frequency_days; no last date ⇒ due), visited
# in the same area-sweep order.
METHOD_NAIVE_FIXED_FREQUENCY: Literal["naive_fixed_frequency"] = "naive_fixed_frequency"

NaiveMethod: TypeAlias = Literal["naive_fixed_order", "naive_sweep_order", "naive_fixed_frequency"]

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
    compartment = vehicle_type.compartment_capacities()[stop.material_type]
    if volume_litres > compartment:
        return (
            f"collected volume {volume_litres} L exceeds the {vehicle_type.id} compartment "
            f"capacity {compartment} L for material {stop.material_type} even when the "
            "vehicle is empty"
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
    # Current vehicle state (fresh start on vehicle 0 at the depot).
    vehicle_index = 0
    vehicle_type = fleet[0]
    pos_pid = depot.id
    sequence: list[Depot | DisposalSite | Stop] = [depot]
    # §4.2 v3: load is tracked PER MATERIAL (collected separated [representative]).
    volume_by_material: dict[MaterialType, int] = {material: 0 for material in MATERIALS}
    weight = 0  # kilograms aboard
    elapsed = 0  # minutes since depot departure (travel + arrival services)
    route_distance = 0
    progression: list[tuple[int, int]] = []
    # §4.2 v3: per-material compartment capacities of the CURRENT vehicle —
    # recomputed on each vehicle hand-over (types may differ per vehicle).
    compartments = vehicle_type.compartment_capacities()

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
        """Start the next vehicle at the depot with an empty load — including
        a fresh per-material dict and the next vehicle's compartment layout
        (§4.2 v3; types may differ per vehicle)."""
        nonlocal vehicle_index, vehicle_type, sequence, volume_by_material, weight, elapsed
        nonlocal route_distance, progression, compartments
        vehicle_index += 1
        if vehicle_index < len(fleet):
            vehicle_type = fleet[vehicle_index]
        sequence = [depot]
        volume_by_material = {material: 0 for material in MATERIALS}
        weight = 0
        elapsed = 0
        route_distance = 0
        progression = []
        compartments = vehicle_type.compartment_capacities()

    routes: list[NaiveRoute] = []
    unserved: list[UnservedStop] = []
    shift_violations: list[str] = []

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
        # §4.2 v4: containers_per_series multiplies litres collected, weight
        # and the stop's service minutes (predictive fill % unchanged).
        collected_volume = effective_collected_volume_litres(stop, problem.config)
        collected_weight = effective_collected_weight_kg(stop, problem.config)
        service_min = effective_service_minutes(stop, problem.config)

        # 1) A stop that cannot fit even an empty vehicle is never servable.
        # §4.2 v3: the binding volume bound is the stop material's COMPARTMENT
        # capacity (materials collected separated); weight stays a total bound.
        if (
            collected_volume > compartments[stop.material_type]
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
        # with load aboard; an empty vehicle passed check 1. §4.2 v3: the
        # trigger is per material (the stop's compartment would overflow);
        # total volume and weight stay fallback bounds (§4.4 invariants).
        needs_disposal = (
            volume_by_material[stop.material_type] + collected_volume
            > compartments[stop.material_type]
            or sum(volume_by_material.values()) + collected_volume
            > vehicle_type.volume_capacity_litres
            or weight + collected_weight > vehicle_type.weight_capacity_kg
        )
        if needs_disposal:
            disposal = nearest_disposal(pos_pid)
            needed_min = (
                minutes(pos_pid, disposal.id)
                + disposal.service_minutes
                + minutes(disposal.id, stop_pid)
                + service_min
            )
        else:
            needed_min = minutes(pos_pid, stop_pid) + service_min

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
            volume_by_material = {material: 0 for material in MATERIALS}
            weight = 0
            pos_pid = disposal.id
        route_distance += dist(pos_pid, stop_pid)
        elapsed += minutes(pos_pid, stop_pid) + service_min
        sequence.append(stop)
        volume_by_material[stop.material_type] += collected_volume
        weight += collected_weight
        progression.append((sum(volume_by_material.values()), weight))
        pos_pid = stop_pid
        stop_cursor += 1

    if len(sequence) > 1 and vehicle_index < len(fleet):
        return_to_depot_and_emit()

    served_stops = [node for route in routes for node in route.sequence if isinstance(node, Stop)]
    served_volume_by_material: dict[MaterialType, int] = {material: 0 for material in MATERIALS}
    for stop in served_stops:
        served_volume_by_material[stop.material_type] += effective_collected_volume_litres(
            stop, problem.config
        )
    shift_minutes_used, stops_per_shift = derive_shift_totals(
        [route.duration_minutes for route in routes], len(served_stops)
    )
    totals = SolutionTotals(
        distance_m=sum(route.distance_m for route in routes),
        duration_min=sum(route.duration_minutes for route in routes),
        collected_volume_litres=sum(
            effective_collected_volume_litres(stop, problem.config) for stop in served_stops
        ),
        collected_volume_by_material=served_volume_by_material,
        collected_weight_kg=sum(
            effective_collected_weight_kg(stop, problem.config) for stop in served_stops
        ),
        stops_served=len(served_stops),
        stops_total=len(ordered_stops),
        shift_minutes_used=shift_minutes_used,
        stops_per_shift=stops_per_shift,
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


def _is_due(last_date: date | None, as_of: date, frequency_days: int) -> bool:
    """§4.7 v4 due rule for one series: no last emptying date ⇒ due (never
    collected), otherwise due iff ``as_of - last_date >= k`` days."""
    return last_date is None or (as_of - last_date).days >= frequency_days


def due_series_keys(
    last_emptying_dates: Mapping[SeriesKey, date | None],
    as_of: date,
    frequency_days: int,
) -> set[SeriesKey]:
    """§4.7 v4 status-quo due-set (pure): a series is **due** iff
    ``as_of - last_emptying_date >= frequency_days`` days; a series with no
    last emptying date (``None``) is **due** too (never collected ⇒ must be
    visited). A last date after ``as_of`` (negative gap) is never due. The
    set covers exactly the series present in ``last_emptying_dates``;
    :func:`naive_fixed_frequency_simulation` additionally treats problem
    stops ABSENT from the mapping as due (§4.7: no last date ⇒ due).
    ``frequency_days`` must be >= 1 (§4.2 v4: ``RoutingConfig.frequency_days``
    default 28 [demo assumption]).

    Deterministic: same inputs ⇒ identical set (set ordering is not part of
    the contract; the scenario visits due stops in area-sweep order).
    """
    if isinstance(frequency_days, bool) or not isinstance(frequency_days, int):
        raise ValueError(f"frequency_days must be an int >= 1, got {type(frequency_days).__name__}")
    if frequency_days < 1:
        raise ValueError(f"frequency_days must be >= 1, got {frequency_days}")
    return {
        key
        for key, last_date in last_emptying_dates.items()
        if _is_due(last_date, as_of, frequency_days)
    }


def naive_fixed_frequency_simulation(
    problem: RoutingProblem,
    last_emptying_dates: Mapping[SeriesKey, date | None],
    as_of: date,
    no_forecast_stop_keys: Sequence[SeriesKey] = (),
    frequency_days: int | None = None,
) -> NaiveSolution:
    """§4.7 v4 ``naive_fixed_frequency`` status-quo scenario: visit only the
    problem stops whose series is **due** under the fixed k-day cycle (see
    :func:`due_series_keys`), in the same §4.7 area-sweep order and with the
    identical simulation physics as the other naive scenarios (capacities,
    nearest-disposal unload, shift hand-over, fleet exhaustion — never silent
    drops, §4.4).

    ``frequency_days`` defaults to ``problem.config.frequency_days`` (§4.2
    v4, default 28 [demo assumption]) so the scenario always shares the
    request's effective physics. Problem stops ABSENT from
    ``last_emptying_dates`` count as "no last date" and are due (§4.7).
    Deterministic: same inputs ⇒ identical :class:`NaiveSolution`."""
    resolved_frequency = problem.config.frequency_days if frequency_days is None else frequency_days
    due_stops = [
        stop
        for stop in problem.stops
        if _is_due(
            last_emptying_dates.get((stop.location_id, stop.material_type)),
            as_of,
            resolved_frequency,
        )
    ]
    ordered = sweep_visit_order(due_stops)
    return _simulate_order(problem, ordered, no_forecast_stop_keys, METHOD_NAIVE_FIXED_FREQUENCY)
