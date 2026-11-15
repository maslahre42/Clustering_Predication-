"""OR-Tools route optimisation (M9) — docs/contracts.md §4.3/§4.4.

Single-depot CVRP with volume AND weight capacity dimensions and disposal
sites as optional unload nodes that reset the load. There is deliberately NO
Time dimension in the OR-Tools model: a span cap on any optional node that
cannot fit makes the whole model FAIL at root propagation (OR-Tools
limitation, empirically verified; slack and service-on-arrival variants do
not help). Shift compliance (``max_shift_minutes``) is therefore enforced in
Python, post-hoc: shift-infeasible stops are pre-filtered into ``unserved``
and over-long routes are truncated by ``_apply_shift_limits`` (§4.4:
violations are surfaced, never hidden); durations are recomputed from the
travel matrix either way.
OR-Tools only (AGENTS rule 8). Deterministic node order and reasons; the
search uses PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH. v2 determinism protocol
(§4.4/§4.7, user-approved 2026-11-14): the **primary stopping criterion is
``RoutingConfig.solver_solution_limit``** — a fixed solution budget counted
via ``AddAtSolutionCallback``, with no wall-clock dependence, so repeated
solves that reach the budget return identical ``totals.distance_m``.
``solver_time_limit_s`` is a **safety cap only**: when it fires before the
solution budget (detected from the solutions counter and the measured
elapsed time, never guessed), the status is honestly ``timeout`` and the run
is explicitly non-reproducible (§4.7).

Model notes (all [protocol choice v1], documented for the model card):
- Load cumul semantics: the transit callback adds a stop's pickup on the arc
  LEAVING it, so ``cumul(node)`` is the load on the incoming arc; capacity is
  enforced on every arc. An arc leaving a disposal site transits
  ``-max_capacity``, which resets the following cumul to its 0 lower bound
  ("unload everything").
- A vehicle may finish at the depot with load aboard (the yard absorbs it);
  nothing in the brief forbids this [demo assumption].
- Stops are optional nodes with a drop penalty larger than any possible route
  distance, so the solver drops a stop only when no feasible assignment
  exists; every dropped stop is reported in ``unserved`` with a computed,
  deterministic reason (§4.4: never silently dropped).
- Reported ``objective_value`` is the solved routes' total distance in metres
  (the solver's internal objective mixes in drop penalties, so it is not
  reported).
- Status mapping: ROUTING_OPTIMAL → "optimal" (proven optimality);
  SUCCESS / PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED → "feasible" **when the
  solution budget was reached** (or the search ended on its own before both
  limits); FAIL / INFEASIBLE → "infeasible"; FAIL_TIMEOUT → "timeout";
  NOT_SOLVED / INVALID → :class:`RoutingSolverError` (a search that never ran
  is a bug, not a user-facing status). SUCCESS/PARTIAL with fewer solutions
  than the budget while the measured elapsed time shows the safety cap fired
  → "timeout" (§4.7: never silently presented as deterministic).

Distance provenance is echoed from the travel matrix untouched —
straight-line-derived matrices are never called road distance (§4.2).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, NamedTuple, TypeAlias

from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore[import-untyped]

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

__all__ = [
    "FleetRecommendation",
    "Route",
    "RoutingSolution",
    "RoutingSolverError",
    "SolutionStatus",
    "SolutionTotals",
    "UnservedStop",
    "solve",
]

SolutionStatus: TypeAlias = Literal["optimal", "feasible", "infeasible", "timeout"]

_STATUS = routing_enums_pb2.RoutingSearchStatus.Value


class RoutingSolverError(RuntimeError):
    """Raised when the routing search itself is unusable (never-solved or
    invalid model) or an internal post-solve consistency check fails — these
    are bugs to surface, not user-facing solver statuses."""


def _map_status(raw_status: int) -> SolutionStatus:
    """Map the OR-Tools routing status onto contract §4.3 statuses."""
    if raw_status == _STATUS.ROUTING_OPTIMAL:
        return "optimal"
    if raw_status == _STATUS.ROUTING_SUCCESS:
        return "feasible"
    if raw_status == _STATUS.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED:
        return "feasible"
    if raw_status in (_STATUS.ROUTING_FAIL, _STATUS.ROUTING_INFEASIBLE):
        return "infeasible"
    if raw_status == _STATUS.ROUTING_FAIL_TIMEOUT:
        return "timeout"
    raise RoutingSolverError(
        f"routing search did not produce a usable status: {raw_status} "
        "(NOT_SOLVED or INVALID means the model never ran — a bug, not a result)"
    )


# ---------------------------------------------------------------------------
# Output schemas — contract §4.3
# ---------------------------------------------------------------------------


class UnservedStop(NamedTuple):
    """A stop that could not be served, with an explicit reason (§4.3/§4.4).

    NamedTuple so the contract shape ``{stop_key, reason}`` supports both
    attribute access and tuple unpacking.
    """

    stop_key: SeriesKey  # (location_id, material_type)
    reason: str  # deterministic, carries the deciding numbers


@dataclass(frozen=True)
class SolutionTotals:
    """Solution-wide totals — contract §4.3 ``totals``."""

    distance_m: int  # metres [predicted]
    duration_min: int  # minutes [predicted]
    collected_volume_litres: int  # litres [predicted]
    collected_weight_kg: int  # kilograms [predicted]
    stops_served: int
    stops_total: int


@dataclass(frozen=True)
class Route:
    """One vehicle route — contract §4.3 ``Route``."""

    vehicle_type_id: str
    sequence: list[Depot | DisposalSite | Stop]  # depot start ... depot end
    load_progression: list[tuple[int, int]]  # (volume_litres, weight_kg) after each stop
    distance_m: int
    duration_minutes: int


@dataclass(frozen=True)
class RoutingSolution:
    """Complete solver output — contract §4.3."""

    status: SolutionStatus
    objective_value: int | None  # metres; None iff no solution (infeasible/timeout)
    routes: list[Route]
    unserved: list[UnservedStop]
    totals: SolutionTotals
    fleet_recommendation: FleetRecommendation
    distance_provenance: Provenance  # echoed from TravelMatrix (§4.2)


# ---------------------------------------------------------------------------
# Internal model layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _NodeLayout:
    """Node order: depot 0, disposal sites by id, stops by (location_id,
    material) — deterministic and independent of input order."""

    node_point_ids: list[str]  # point id per routing-model node index
    stops_by_node: dict[int, Stop]
    disposal_by_node: dict[int, DisposalSite]
    service_by_node: list[int]  # minutes served at each node (depot 0)
    matrix_index: dict[str, int]  # point id -> travel matrix row/col


def _build_layout(problem: RoutingProblem, excluded_stop_keys: set[SeriesKey]) -> _NodeLayout:
    """Node order: depot 0, disposal sites by id, stops by (location_id,
    material) — deterministic and independent of input order. Stops whose key
    is in ``excluded_stop_keys`` are pre-filtered out of the model (shift
    infeasibility, :func:`_prefilter_shift_infeasible`) and surface as
    unserved; the travel matrix keeps covering them (§4.2)."""
    matrix_index = {point_id: i for i, point_id in enumerate(problem.travel.point_ids)}
    node_point_ids: list[str] = [problem.depot.id]
    disposal_by_node: dict[int, DisposalSite] = {}
    stops_by_node: dict[int, Stop] = {}
    service_by_node: list[int] = [0]
    for site in sorted(problem.disposal_sites, key=lambda site: site.id):
        disposal_by_node[len(node_point_ids)] = site
        node_point_ids.append(site.id)
        service_by_node.append(site.service_minutes)
    for stop in sorted(problem.stops, key=lambda stop: (stop.location_id, stop.material_type)):
        if (stop.location_id, stop.material_type) in excluded_stop_keys:
            continue
        stops_by_node[len(node_point_ids)] = stop
        node_point_ids.append(stop_point_id(stop))
        service_by_node.append(stop.service_minutes)
    return _NodeLayout(
        node_point_ids=node_point_ids,
        stops_by_node=stops_by_node,
        disposal_by_node=disposal_by_node,
        service_by_node=service_by_node,
        matrix_index=matrix_index,
    )


def _vehicle_type_per_vehicle(problem: RoutingProblem) -> list[VehicleType]:
    """Vehicle number -> its type; types by id, each repeated count_available
    times (deterministic)."""
    ordered = sorted(problem.vehicle_types, key=lambda vehicle_type: vehicle_type.id)
    return [vehicle_type for vehicle_type in ordered for _ in range(vehicle_type.count_available)]


def _stop_collected_quantities(stop: Stop, problem: RoutingProblem) -> tuple[int, int]:
    """(litres, kilograms) the stop contributes — the same derived quantities
    the load dimensions use (Stop round-half-to-even, densities from config)."""
    density = problem.config.densities_kg_per_litre[stop.material_type]
    return stop.collected_volume_litres, stop.collected_weight_kg(density)


def _build_model(
    problem: RoutingProblem, layout: _NodeLayout
) -> tuple[pywrapcp.RoutingIndexManager, pywrapcp.RoutingModel]:
    """Register callbacks, dimensions and disjunctions (see module docstring)."""
    n_nodes = len(layout.node_point_ids)
    vehicles = _vehicle_type_per_vehicle(problem)
    manager = pywrapcp.RoutingIndexManager(n_nodes, len(vehicles), 0)
    routing = pywrapcp.RoutingModel(manager)

    distance_m = problem.travel.distance_m

    def node_of(index: int) -> int:
        return int(manager.IndexToNode(index))

    def matrix_cell(matrix: list[list[int]], node_i: int, node_j: int) -> int:
        i = layout.matrix_index[layout.node_point_ids[node_i]]
        j = layout.matrix_index[layout.node_point_ids[node_j]]
        return int(matrix[i][j])

    def distance_callback(from_index: int, to_index: int) -> int:
        if from_index == to_index:
            return 0  # self-loop of an inactive (dropped) node — must stay 0
        return matrix_cell(distance_m, node_of(from_index), node_of(to_index))

    distance_idx = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_idx)

    max_volume = max(vehicle_type.volume_capacity_litres for vehicle_type in vehicles)
    max_weight = max(vehicle_type.weight_capacity_kg for vehicle_type in vehicles)
    demand_by_node = {
        node: _stop_collected_quantities(stop, problem)
        for node, stop in layout.stops_by_node.items()
    }

    def volume_callback(from_index: int, to_index: int) -> int:
        if from_index == to_index:
            return 0  # self-loop of an inactive node (see duration_callback)
        node = node_of(from_index)
        if node in layout.disposal_by_node:
            return -max_volume  # unload everything; cumul >= 0 clamps the rest
        return demand_by_node.get(node, (0, 0))[0]

    def weight_callback(from_index: int, to_index: int) -> int:
        if from_index == to_index:
            return 0
        node = node_of(from_index)
        if node in layout.disposal_by_node:
            return -max_weight
        return demand_by_node.get(node, (0, 0))[1]

    volume_idx = routing.RegisterTransitCallback(volume_callback)
    weight_idx = routing.RegisterTransitCallback(weight_callback)
    # slack_max = max capacity so the negative unload transit can reach 0.
    routing.AddDimensionWithVehicleCapacity(
        volume_idx,
        max_volume,
        [vehicle_type.volume_capacity_litres for vehicle_type in vehicles],
        True,
        "Volume",
    )
    routing.AddDimensionWithVehicleCapacity(
        weight_idx,
        max_weight,
        [vehicle_type.weight_capacity_kg for vehicle_type in vehicles],
        True,
        "Weight",
    )
    # NOTE: no Time dimension in the model. An OR-Tools span cap makes the
    # whole model ROUTING_FAIL at root propagation whenever any optional node
    # (stop or disposal) cannot fit within the cap — empirically verified
    # (see _apply_shift_limits): slack variants and service-on-arrival transit
    # do not change it. Shift compliance is therefore enforced in Python AFTER
    # solving (_prefilter_shift_infeasible + _apply_shift_limits, §4.4:
    # violations are surfaced as unserved stops, never hidden). Route
    # durations are recomputed from the matrix in Python regardless.

    # Disposal sites: optional unload nodes — skipping one costs nothing.
    for node in layout.disposal_by_node:
        routing.AddDisjunction([manager.NodeToIndex(node)])
    # Stops: droppable only as a last resort — the penalty exceeds the total
    # of all matrix distances, i.e. any conceivable route detour.
    n_matrix = len(distance_m)
    drop_penalty = 1 + sum(
        distance_m[i][j] for i in range(n_matrix) for j in range(n_matrix) if i != j
    )
    for node in layout.stops_by_node:
        routing.AddDisjunction([manager.NodeToIndex(node)], drop_penalty)

    return manager, routing


@dataclass(frozen=True)
class _SearchOutcome:
    """Raw search results plus the v2 §4.7 stop-criterion evidence.

    ``solutions_found`` counts intermediate solutions reported by the solver
    (``AddAtSolutionCallback``); together with the measured ``elapsed_s`` it
    classifies WHY the search stopped — the solution budget (deterministic)
    or the wall-clock safety cap (non-reproducible, §4.7) — instead of
    guessing from the raw status alone.
    """

    assignment: pywrapcp.Assignment | None
    raw_status: int
    solutions_found: int
    elapsed_s: float


# Tolerance for classifying the safety cap as fired: OR-Tools enforces the
# time limit at millisecond granularity, so a cap-bounded run ends within a
# few milliseconds past (or a hair under) the configured seconds.
_SAFETY_CAP_TOLERANCE_S = 0.01


def _resolve_status(
    raw_status: int,
    solutions_found: int,
    elapsed_s: float,
    problem: RoutingProblem,
) -> SolutionStatus:
    """Honest §4.3/§4.7 status mapping driven by stop-criterion evidence.

    - The solution budget (``solver_solution_limit``) is the primary stop:
      reaching it is deterministic and reported as "feasible" (or "optimal"
      when OR-Tools proved optimality).
    - The wall-clock ``solver_time_limit_s`` is a safety cap only: raw
      FAIL_TIMEOUT, or a solution-short stop with the cap measured as fired,
      is reported as "timeout" — explicitly non-reproducible (§4.7).
    - A search that ends on its own before both limits (small problems where
      GUIDED_LOCAL_SEARCH runs out of improving moves) is deterministic and
      reported as "feasible".
    """
    status = _map_status(raw_status)
    if (
        status == "feasible"
        and solutions_found < problem.config.solver_solution_limit
        and elapsed_s >= problem.config.solver_time_limit_s - _SAFETY_CAP_TOLERANCE_S
    ):
        # The budget was NOT the stop: the safety cap fired (the measured
        # elapsed time sits at the configured limit — report the honest,
        # non-reproducible "timeout", §4.7). A search that instead ends on
        # its own before both limits is deterministic and stays "feasible".
        return "timeout"
    return status


def _solve_model(problem: RoutingProblem, routing: pywrapcp.RoutingModel) -> _SearchOutcome:
    """Run the search with the configured strategy and §4.7 v2 limits: the
    solution budget as the primary stop and the wall-clock time limit as a
    safety cap only. The solutions counter and elapsed time are the evidence
    used by :func:`_resolve_status` to classify the stop criterion."""
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search.solution_limit = problem.config.solver_solution_limit
    millis = max(1, round(problem.config.solver_time_limit_s * 1000))
    search.time_limit.FromMilliseconds(millis)
    counter = [0]  # int cell so the solver callback can increment by reference
    routing.AddAtSolutionCallback(lambda: counter.__setitem__(0, counter[0] + 1))
    started_s = time.perf_counter()
    assignment = routing.SolveWithParameters(search)
    elapsed_s = time.perf_counter() - started_s
    return _SearchOutcome(
        assignment=assignment,
        raw_status=routing.status(),
        solutions_found=counter[0],
        elapsed_s=elapsed_s,
    )


def _extract_routes(
    problem: RoutingProblem,
    layout: _NodeLayout,
    manager: pywrapcp.RoutingIndexManager,
    routing: pywrapcp.RoutingModel,
    assignment: pywrapcp.Assignment,
) -> tuple[list[Route], set[int]]:
    """Decode vehicle sequences into Routes; also return the visited node set.

    Distance/duration/load are recomputed in Python from the travel matrix and
    config (authoritative for output), not read back from solver cumuls.
    Internal consistency checks raise :class:`RoutingSolverError` — the
    enforced dimensions make violations impossible; a violation means a bug.
    """
    distance_m = problem.travel.distance_m
    duration_min = problem.travel.duration_min
    vehicle_types = _vehicle_type_per_vehicle(problem)
    routes: list[Route] = []
    visited_nodes: set[int] = set()

    for vehicle in range(len(vehicle_types)):
        sequence_nodes: list[int] = []
        index = routing.Start(vehicle)
        while True:
            node = manager.IndexToNode(index)
            sequence_nodes.append(node)
            visited_nodes.add(node)
            if routing.IsEnd(index):
                break
            index = assignment.Value(routing.NextVar(index))

        if not any(node in layout.stops_by_node for node in sequence_nodes):
            continue  # omit empty routes (vehicle unused)

        sequence: list[Depot | DisposalSite | Stop] = []
        for node in sequence_nodes:
            if node in layout.stops_by_node:
                sequence.append(layout.stops_by_node[node])
            elif node in layout.disposal_by_node:
                sequence.append(layout.disposal_by_node[node])
            else:
                sequence.append(problem.depot)

        total_distance = 0
        total_duration = 0
        for node_i, node_j in pairwise(sequence_nodes):
            i = layout.matrix_index[layout.node_point_ids[node_i]]
            j = layout.matrix_index[layout.node_point_ids[node_j]]
            total_distance += distance_m[i][j]
            total_duration += duration_min[i][j] + layout.service_by_node[node_i]

        progression: list[tuple[int, int]] = []
        volume = 0
        weight = 0
        for node in sequence_nodes:
            if node in layout.stops_by_node:
                stop_volume, stop_weight = _stop_collected_quantities(
                    layout.stops_by_node[node], problem
                )
                volume += stop_volume
                weight += stop_weight
                progression.append((volume, weight))
            elif node in layout.disposal_by_node:
                volume = 0
                weight = 0

        vehicle_type = vehicle_types[vehicle]
        for load_volume, load_weight in progression:
            if load_volume > vehicle_type.volume_capacity_litres:
                raise RoutingSolverError(
                    f"internal consistency: volume {load_volume} L exceeds vehicle "
                    f"capacity {vehicle_type.volume_capacity_litres} L on a solved route"
                )
            if load_weight > vehicle_type.weight_capacity_kg:
                raise RoutingSolverError(
                    f"internal consistency: weight {load_weight} kg exceeds vehicle "
                    f"capacity {vehicle_type.weight_capacity_kg} kg on a solved route"
                )
        # NOTE: route duration may exceed max_shift_minutes here — shift
        # compliance is enforced post-hoc by _apply_shift_limits in solve().

        routes.append(
            Route(
                vehicle_type_id=vehicle_type.id,
                sequence=sequence,
                load_progression=progression,
                distance_m=total_distance,
                duration_minutes=total_duration,
            )
        )
    return routes, visited_nodes


def _minimum_round_trip_minutes(stop: Stop, problem: RoutingProblem) -> int:
    """Minimum minutes any legal route serving ``stop`` takes. Two variants:
    direct return with load aboard (the depot yard absorbs it — documented v1
    [demo assumption]) or via a disposal unload (including its service). The
    smaller is the honest lower bound — matrices need not satisfy the
    triangle inequality."""
    matrix = problem.travel
    index = {point_id: i for i, point_id in enumerate(matrix.point_ids)}
    i_depot = index[problem.depot.id]
    i_stop = index[stop_point_id(stop)]
    direct_min = (
        matrix.duration_min[i_depot][i_stop]
        + stop.service_minutes
        + matrix.duration_min[i_stop][i_depot]
    )
    via_disposal_min = min(
        (
            matrix.duration_min[i_stop][index[site.id]]
            + site.service_minutes
            + matrix.duration_min[index[site.id]][i_depot]
        )
        for site in problem.disposal_sites
    )
    return min(
        direct_min, matrix.duration_min[i_depot][i_stop] + stop.service_minutes + via_disposal_min
    )


def _shift_limit_reason(minimum_trip_min: int, problem: RoutingProblem) -> str:
    return (
        f"shift_limit_exceeded: minimum collection round trip takes "
        f"{minimum_trip_min} min, exceeding max_shift_minutes "
        f"{problem.config.max_shift_minutes} min"
    )


def _prefilter_shift_infeasible(
    problem: RoutingProblem,
) -> list[UnservedStop]:
    """Stops whose minimum round trip alone exceeds ``max_shift_minutes``
    cannot be served by any vehicle; they are excluded from the OR-Tools
    model (a span cap on a node that cannot fit makes the model FAIL at root)
    and reported as unserved (§4.4: surfaced, never hidden)."""
    unserved: list[UnservedStop] = []
    for stop in sorted(problem.stops, key=lambda stop: (stop.location_id, stop.material_type)):
        minimum_trip_min = _minimum_round_trip_minutes(stop, problem)
        if minimum_trip_min > problem.config.max_shift_minutes:
            unserved.append(
                UnservedStop(
                    stop_key=(stop.location_id, stop.material_type),
                    reason=_shift_limit_reason(minimum_trip_min, problem),
                )
            )
    return unserved


def _route_metrics(
    sequence: list[Depot | DisposalSite | Stop], problem: RoutingProblem
) -> tuple[int, int, list[tuple[int, int]]]:
    """(distance_m, duration_minutes, load_progression) recomputed from the
    travel matrix and config for an object-level route sequence."""
    matrix = problem.travel
    index = {point_id: i for i, point_id in enumerate(matrix.point_ids)}

    def pid_of(node: Depot | DisposalSite | Stop) -> str:
        if isinstance(node, Stop):
            return stop_point_id(node)
        return node.id

    ids = [pid_of(node) for node in sequence]
    distance = 0
    duration = 0
    for (node_a, id_a), (_node_b, id_b) in pairwise(zip(sequence, ids, strict=True)):
        i = index[id_a]
        j = index[id_b]
        distance += matrix.distance_m[i][j]
        service = 0 if isinstance(node_a, Depot) else node_a.service_minutes
        duration += matrix.duration_min[i][j] + service
    progression: list[tuple[int, int]] = []
    volume = 0
    weight = 0
    for node in sequence:
        if isinstance(node, Stop):
            stop_volume, stop_weight = _stop_collected_quantities(node, problem)
            volume += stop_volume
            weight += stop_weight
            progression.append((volume, weight))
        elif isinstance(node, DisposalSite):
            volume = 0
            weight = 0
    return distance, duration, progression


def _apply_shift_limits(
    routes: list[Route], problem: RoutingProblem
) -> tuple[list[Route], list[UnservedStop]]:
    """§4.4 post-hoc shift enforcement. While a route's duration exceeds
    ``max_shift_minutes``: first drop disposal visits (they are optional in
    the model; a vehicle may end at the depot loaded [demo assumption]) as
    long as the remaining load progression stays within the route vehicle's
    volume/weight capacities; then remove the lowest-priority stop (smallest
    predicted_fill_pct, ties by (location_id, material_type)). Each step
    shrinks the sequence, so the loop terminates; removed stops surface as
    unserved with a ``shift_limit_exceeded`` reason (never hidden)."""
    shifted_routes: list[Route] = []
    removed_unserved: list[UnservedStop] = []
    for route in routes:
        sequence: list[Depot | DisposalSite | Stop] = list(route.sequence)
        vehicle_type = next(vt for vt in problem.vehicle_types if vt.id == route.vehicle_type_id)
        stops_in_route = [node for node in sequence if isinstance(node, Stop)]
        removal_order = sorted(
            stops_in_route,
            key=lambda stop: (
                stop.predicted_fill_pct,
                stop.location_id,
                stop.material_type,
            ),
        )
        drop_candidates = iter(removal_order)
        removed: list[Stop] = []
        distance, duration, progression = _route_metrics(sequence, problem)
        while duration > problem.config.max_shift_minutes:
            # 1) disposal visit removable? keeps >= 1 stop, caps respected.
            disposal_positions = [
                i for i, node in enumerate(sequence) if isinstance(node, DisposalSite)
            ]
            if disposal_positions and any(isinstance(node, Stop) for node in sequence):
                position = disposal_positions[-1]  # deterministic: last visit
                candidate = [node for i, node in enumerate(sequence) if i != position]
                c_distance, c_duration, c_progression = _route_metrics(candidate, problem)
                if all(v <= vehicle_type.volume_capacity_litres for v, _w in c_progression) and all(
                    w <= vehicle_type.weight_capacity_kg for _v, w in c_progression
                ):
                    sequence, distance, duration, progression = (
                        candidate,
                        c_distance,
                        c_duration,
                        c_progression,
                    )
                    continue
            # 2) lowest-priority stop removable?
            drop = next(drop_candidates, None)
            if drop is None:
                break  # empty routes have duration 0 — cannot still exceed
            sequence = [
                node
                for node in sequence
                if not (
                    isinstance(node, Stop)
                    and node.location_id == drop.location_id
                    and node.material_type == drop.material_type
                )
            ]
            removed.append(drop)
            distance, duration, progression = _route_metrics(sequence, problem)
        if removed:
            for stop in sorted(removed, key=lambda stop: (stop.location_id, stop.material_type)):
                removed_unserved.append(
                    UnservedStop(
                        stop_key=(stop.location_id, stop.material_type),
                        reason=(
                            "shift_limit_exceeded: route duration exceeded "
                            f"max_shift_minutes {problem.config.max_shift_minutes} min "
                            "(lowest-priority stops removed first)"
                        ),
                    )
                )
        if not any(isinstance(node, Stop) for node in sequence):
            continue  # route became empty — omit it, stops are in unserved
        shifted_routes.append(
            Route(
                vehicle_type_id=route.vehicle_type_id,
                sequence=sequence,
                load_progression=progression,
                distance_m=distance,
                duration_minutes=duration,
            )
        )
    return shifted_routes, removed_unserved


def _unserved_reason(stop: Stop, problem: RoutingProblem) -> str:
    """Deterministic reason string for a stop the solver had to drop (§4.4).

    Fleet size/capacity figures come from the UNexpanded problem.vehicle_types
    (one entry per type). Summing over the per-vehicle expanded list would
    multiply count_available by itself (one type x 3 vehicles -> "9 vehicles").
    """
    volume, weight = _stop_collected_quantities(stop, problem)
    max_volume = max(vehicle_type.volume_capacity_litres for vehicle_type in problem.vehicle_types)
    max_weight = max(vehicle_type.weight_capacity_kg for vehicle_type in problem.vehicle_types)
    if volume > max_volume:
        return (
            f"collected volume {volume} L exceeds the largest vehicle volume "
            f"capacity {max_volume} L"
        )
    if weight > max_weight:
        return (
            f"collected weight {weight} kg exceeds the largest vehicle weight "
            f"capacity {max_weight} kg"
        )
    # Minimum honest round trip: depot -> stop -> (any) disposal -> depot,
    # including unload service — any route serving the stop does at least this.
    minimum_trip_min = _minimum_round_trip_minutes(stop, problem)
    if minimum_trip_min > problem.config.max_shift_minutes:
        return _shift_limit_reason(minimum_trip_min, problem)
    available = sum(vehicle_type.count_available for vehicle_type in problem.vehicle_types)
    return (
        "no feasible insertion within the available fleet "
        f"({available} vehicles) and the configured capacity/shift limits"
    )


def _global_unserved(status: SolutionStatus, problem: RoutingProblem) -> list[UnservedStop]:
    reason = (
        f"solver stopped before the solution limit "
        f"{problem.config.solver_solution_limit}: the "
        f"{problem.config.solver_time_limit_s} s wall-clock safety cap fired "
        "(status timeout — this run is not reproducible, contract §4.7)"
        if status == "timeout"
        else "solver proved the problem infeasible; no stop can be served"
    )
    return [
        UnservedStop(stop_key=(stop.location_id, stop.material_type), reason=reason)
        for stop in sorted(problem.stops, key=lambda stop: (stop.location_id, stop.material_type))
    ]


def _empty_totals(problem: RoutingProblem) -> SolutionTotals:
    return SolutionTotals(
        distance_m=0,
        duration_min=0,
        collected_volume_litres=0,
        collected_weight_kg=0,
        stops_served=0,
        stops_total=len(problem.stops),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def solve(problem: RoutingProblem) -> RoutingSolution:
    """Solve a :class:`RoutingProblem` into a contract §4.3 solution.

    Deterministic node order and reasons; the search stops on the configured
    solution budget (``config.solver_solution_limit``, primary criterion) with
    ``config.solver_time_limit_s`` as a safety cap only (§4.4/§4.7 v2 — see
    the module docstring for the honest determinism claim). Every input stop
    is served in exactly one route or reported in ``unserved`` with a reason
    (§4.4). The fleet recommendation (§4.4) always covers the full demand,
    including unserved stops.
    """
    fleet_recommendation_result = recommend_fleet_for_problem(problem)
    provenance: Provenance = problem.travel.provenance

    if not problem.stops:
        return RoutingSolution(
            status="optimal",
            objective_value=0,
            routes=[],
            unserved=[],
            totals=_empty_totals(problem),
            fleet_recommendation=fleet_recommendation_result,
            distance_provenance=provenance,
        )

    prefiltered_unserved = _prefilter_shift_infeasible(problem)
    excluded_stop_keys = {entry.stop_key for entry in prefiltered_unserved}
    layout = _build_layout(problem, excluded_stop_keys)
    manager, routing = _build_model(problem, layout)
    outcome = _solve_model(problem, routing)
    status = _resolve_status(
        outcome.raw_status, outcome.solutions_found, outcome.elapsed_s, problem
    )

    if outcome.assignment is None or status in ("infeasible", "timeout"):
        # No usable solution: surface every stop as unserved, never hidden.
        return RoutingSolution(
            status=status,
            objective_value=None,
            routes=[],
            unserved=_global_unserved(status, problem),
            totals=_empty_totals(problem),
            fleet_recommendation=fleet_recommendation_result,
            distance_provenance=provenance,
        )

    routes, visited_nodes = _extract_routes(problem, layout, manager, routing, outcome.assignment)
    routes, truncated_unserved = _apply_shift_limits(routes, problem)
    dropped_nodes = sorted(
        (node for node in layout.stops_by_node if node not in visited_nodes),
        key=lambda node: (
            layout.stops_by_node[node].location_id,
            layout.stops_by_node[node].material_type,
        ),
    )
    unserved = sorted(
        [
            *prefiltered_unserved,
            *truncated_unserved,
            *[
                UnservedStop(
                    stop_key=(
                        layout.stops_by_node[node].location_id,
                        layout.stops_by_node[node].material_type,
                    ),
                    reason=_unserved_reason(layout.stops_by_node[node], problem),
                )
                for node in dropped_nodes
            ],
        ],
        key=lambda entry: entry.stop_key,
    )

    served_stops = [node for route in routes for node in route.sequence if isinstance(node, Stop)]
    totals = SolutionTotals(
        distance_m=sum(route.distance_m for route in routes),
        duration_min=sum(route.duration_minutes for route in routes),
        collected_volume_litres=sum(
            _stop_collected_quantities(stop, problem)[0] for stop in served_stops
        ),
        collected_weight_kg=sum(
            _stop_collected_quantities(stop, problem)[1] for stop in served_stops
        ),
        stops_served=len(served_stops),
        stops_total=len(problem.stops),
    )

    return RoutingSolution(
        status=status,
        objective_value=totals.distance_m,
        routes=routes,
        unserved=unserved,
        totals=totals,
        fleet_recommendation=fleet_recommendation_result,
        distance_provenance=provenance,
    )
