"""OR-Tools route optimisation (M9) — docs/contracts.md §4.3/§4.4.

Single-depot CVRP with per-material volume capacity dimensions (one OR-Tools
dimension per observed material, capacities = the vehicle's compartment
volumes §4.2 v3) plus a total weight dimension, and disposal sites as
optional unload nodes that reset EVERY dimension (materials are never mixed
on one truck [representative]; a disposal visit unloads everything). There
is deliberately NO Time dimension in the OR-Tools model: a span cap on any
optional node that
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
  ``-max_capacity`` on each material dimension AND the weight dimension,
  which resets the following cumul to its 0 lower bound ("unload
  everything" — §4.4: a disposal visit resets every material dimension).
- Compartments: each material dimension is capped by the route vehicle's
  compartment capacity for that material (§4.2: ``None`` ⇒ equal thirds).
  Total volume needs no extra dimension: validated compartment layouts sum
  exactly to ``volume_capacity_litres``, so per-material bounds imply the
  total. Output ``load_progression`` stays the §4.3/§5.2.1 wire shape
  ``(volume_litres, weight_kg)``; per-material visibility comes from
  ``totals.collected_volume_by_material``.
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

Cost figures (§4.3 v3) are pure derivations from ``vehicles_used`` (routes
emitted) / ``fleet_recommendation.count`` x ``RoutingConfig`` cost
parameters — labelled [predicted], never invoiced amounts (§4.4).

Distance provenance is echoed from the travel matrix untouched —
straight-line-derived matrices are never called road distance (§4.2).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, NamedTuple, TypeAlias

from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # type: ignore[import-untyped]

from src.data.schema import MATERIALS, MaterialType
from src.forecasting.features import SeriesKey
from src.routing.fleet import FleetRecommendation, recommend_fleet_for_problem
from src.routing.schemas import (
    Depot,
    DisposalSite,
    Provenance,
    RoutingConfig,
    RoutingProblem,
    Stop,
    TravelTimeMode,
    VehicleType,
    effective_collected_volume_litres,
    effective_collected_weight_kg,
    effective_service_minutes,
    stop_point_id,
)

__all__ = [
    "FleetRecommendation",
    "Route",
    "RoutingSolution",
    "RoutingSolverError",
    "SolutionCost",
    "SolutionFleetCost",
    "SolutionStatus",
    "SolutionTotals",
    "UnservedStop",
    "derive_shift_totals",
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
    """Solution-wide totals — contract §4.3 (``collected_volume_by_material``
    added v3: per-material litres for compartment visibility, §4.4;
    ``shift_minutes_used``/``stops_per_shift`` added v4 as [predicted]
    derived fields — §4.3/§4.4 flat-mode anchor)."""

    distance_m: int  # metres [predicted]
    duration_min: int  # minutes [predicted]
    collected_volume_litres: int  # litres [predicted]
    collected_volume_by_material: dict[MaterialType, int]  # litres per material [predicted]
    collected_weight_kg: int  # kilograms [predicted]
    stops_served: int
    stops_total: int
    # §4.3 v4 [predicted] derived: max single-route duration (busiest truck).
    shift_minutes_used: int
    # §4.3 v4 [predicted] derived: stops_served / vehicles_used, 1 d.p.
    # (0.0 when no vehicle was used — e.g. an infeasible/empty problem).
    stops_per_shift: float


def derive_shift_totals(
    route_duration_minutes: Sequence[int], stops_served: int
) -> tuple[int, float]:
    """§4.3 v4 derived totals shared by the solver and naive paths (both emit
    routes with a ``duration_minutes`` field):

    - ``shift_minutes_used`` = max single-route duration (busiest truck), 0
      when no route was emitted;
    - ``stops_per_shift`` = ``stops_served / vehicles_used`` rounded to
      1 decimal place, 0.0 when no vehicle was used.
    """
    shift_minutes_used = max(route_duration_minutes, default=0)
    vehicles_used = len(route_duration_minutes)
    stops_per_shift = round(stops_served / vehicles_used, 1) if vehicles_used else 0.0
    return shift_minutes_used, stops_per_shift


@dataclass(frozen=True)
class SolutionFleetCost:
    """Cost of the §4.3 fleet recommendation — contract §4.3 ``cost.fleet_cost``
    (``trucks`` = ``fleet_recommendation.count``). All figures [predicted]
    derived, never invoiced amounts (§4.4)."""

    trucks: int
    cost_eur_per_day: float
    cost_eur_per_year: float


@dataclass(frozen=True)
class SolutionCost:
    """Cost block — contract §4.3 v3 formulas: ``cost_eur_per_day =
    vehicles_used x cost_per_truck_day_eur``; ``cost_eur_per_year =
    cost_eur_per_day x operating_days_per_year`` [predicted] derived
    (decision ③)."""

    vehicles_used: int
    cost_eur_per_day: float
    cost_eur_per_year: float
    fleet_cost: SolutionFleetCost


@dataclass(frozen=True)
class Route:
    """One vehicle route — contract §4.3 ``Route`` (``load_progression``
    stays the §5.2.1 wire shape ``(volume_litres, weight_kg)``; per-material
    visibility comes from ``SolutionTotals.collected_volume_by_material``)."""

    vehicle_type_id: str
    sequence: list[Depot | DisposalSite | Stop]  # depot start ... depot end
    load_progression: list[tuple[int, int]]  # (volume_litres, weight_kg) after each stop
    distance_m: int
    duration_minutes: int


@dataclass(frozen=True)
class RoutingSolution:
    """Complete solver output — contract §4.3 (v3: ``travel_time_mode`` echo
    + derived ``cost`` block)."""

    status: SolutionStatus
    objective_value: int | None  # metres; None iff no solution (infeasible/timeout)
    routes: list[Route]
    unserved: list[UnservedStop]
    totals: SolutionTotals
    fleet_recommendation: FleetRecommendation
    travel_time_mode: TravelTimeMode  # echoed effective mode (§4.2 v3)
    cost: SolutionCost
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
        # §4.2 v4: containers_per_series multiplies the stop's service minutes.
        service_by_node.append(effective_service_minutes(stop, problem.config))
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
    """(litres, kilograms) the stop contributes — the effective §4.2 v4
    quantities including ``containers_per_series`` (Stop round-half-to-even,
    densities from config; never hardcoded)."""
    return (
        effective_collected_volume_litres(stop, problem.config),
        effective_collected_weight_kg(stop, problem.config),
    )


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

    max_weight = max(vehicle_type.weight_capacity_kg for vehicle_type in vehicles)
    demand_by_node = {
        node: _stop_collected_quantities(stop, problem)
        for node, stop in layout.stops_by_node.items()
    }
    compartments_by_vehicle = [vehicle_type.compartment_capacities() for vehicle_type in vehicles]

    def weight_callback(from_index: int, to_index: int) -> int:
        if from_index == to_index:
            return 0
        node = node_of(from_index)
        if node in layout.disposal_by_node:
            return -max_weight
        return demand_by_node.get(node, (0, 0))[1]

    weight_idx = routing.RegisterTransitCallback(weight_callback)
    # slack_max = max capacity so the negative unload transit can reach 0.
    routing.AddDimensionWithVehicleCapacity(
        weight_idx,
        max_weight,
        [vehicle_type.weight_capacity_kg for vehicle_type in vehicles],
        True,
        "Weight",
    )

    # One volume dimension per observed material (§4.2 v3 compartments):
    # each stop loads only its own material; disposal transits
    # -max_compartment so the unload resets every material dimension; the
    # per-vehicle capacities are the compartment volumes. Total volume needs
    # no dimension — validated compartments sum to volume_capacity_litres.
    def make_volume_callback(
        material: MaterialType,
    ) -> Callable[[int, int], int]:
        max_compartment = max(compartments[material] for compartments in compartments_by_vehicle)

        def volume_callback(from_index: int, to_index: int) -> int:
            if from_index == to_index:
                return 0  # self-loop of an inactive node
            node = node_of(from_index)
            if node in layout.disposal_by_node:
                return -max_compartment  # unload resets this material too
            stop_quantities = demand_by_node.get(node)
            if stop_quantities is None:
                return 0
            stop = layout.stops_by_node[node]
            return stop_quantities[0] if stop.material_type == material else 0

        return volume_callback

    for material in MATERIALS:
        max_compartment = max(compartments[material] for compartments in compartments_by_vehicle)
        volume_idx = routing.RegisterTransitCallback(make_volume_callback(material))
        routing.AddDimensionWithVehicleCapacity(
            volume_idx,
            max_compartment,
            [compartments[material] for compartments in compartments_by_vehicle],
            True,
            f"Volume_{material}",
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
        volume_by_material: dict[MaterialType, int] = {material: 0 for material in MATERIALS}
        weight = 0
        for node in sequence_nodes:
            if node in layout.stops_by_node:
                stop = layout.stops_by_node[node]
                stop_volume, stop_weight = _stop_collected_quantities(stop, problem)
                volume_by_material[stop.material_type] += stop_volume
                weight += stop_weight
                progression.append((sum(volume_by_material.values()), weight))
            elif node in layout.disposal_by_node:
                volume_by_material = {material: 0 for material in MATERIALS}
                weight = 0

        vehicle_type = vehicle_types[vehicle]
        compartments = vehicle_type.compartment_capacities()
        for material, load_volume in volume_by_material.items():
            if load_volume > compartments[material]:
                raise RoutingSolverError(
                    f"internal consistency: {material} volume {load_volume} L exceeds "
                    f"vehicle compartment capacity {compartments[material]} L on a "
                    "solved route"
                )
        total_volume = sum(volume_by_material.values())
        if total_volume > vehicle_type.volume_capacity_litres:
            raise RoutingSolverError(
                f"internal consistency: volume {total_volume} L exceeds vehicle "
                f"capacity {vehicle_type.volume_capacity_litres} L on a solved route"
            )
        for _load_volume, load_weight in progression:
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
    service_min = effective_service_minutes(stop, problem.config)  # §4.2 v4 multiplier
    direct_min = (
        matrix.duration_min[i_depot][i_stop] + service_min + matrix.duration_min[i_stop][i_depot]
    )
    via_disposal_min = min(
        (
            matrix.duration_min[i_stop][index[site.id]]
            + site.service_minutes
            + matrix.duration_min[index[site.id]][i_depot]
        )
        for site in problem.disposal_sites
    )
    return min(direct_min, matrix.duration_min[i_depot][i_stop] + service_min + via_disposal_min)


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
) -> tuple[int, int, list[tuple[int, int]], list[dict[MaterialType, int]]]:
    """(distance_m, duration_minutes, load_progression,
    material_load_progression) recomputed from the travel matrix and config
    for an object-level route sequence. ``material_load_progression`` is
    aligned with ``load_progression``: per-material litres aboard after each
    stop (§4.2 v3 compartments)."""
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
        if isinstance(node_a, Depot):
            service = 0
        elif isinstance(node_a, Stop):
            # §4.2 v4: containers_per_series multiplies the stop's service.
            service = effective_service_minutes(node_a, problem.config)
        else:  # DisposalSite — unload minutes are per visit, never multiplied
            service = node_a.service_minutes
        duration += matrix.duration_min[i][j] + service

    def fresh_materials() -> dict[MaterialType, int]:
        return {material: 0 for material in MATERIALS}

    progression: list[tuple[int, int]] = []
    material_progression: list[dict[MaterialType, int]] = []
    volume_by_material = fresh_materials()
    weight = 0
    for node in sequence:
        if isinstance(node, Stop):
            stop_volume, stop_weight = _stop_collected_quantities(node, problem)
            volume_by_material[node.material_type] += stop_volume
            weight += stop_weight
            progression.append((sum(volume_by_material.values()), weight))
            material_progression.append(dict(volume_by_material))
        elif isinstance(node, DisposalSite):
            volume_by_material = fresh_materials()
            weight = 0
    return distance, duration, progression, material_progression


def _apply_shift_limits(
    routes: list[Route], problem: RoutingProblem
) -> tuple[list[Route], list[UnservedStop]]:
    """§4.4 post-hoc shift enforcement. While a route's duration exceeds
    ``max_shift_minutes``: first drop disposal visits (they are optional in
    the model; a vehicle may end at the depot loaded [demo assumption]) as
    long as the remaining load progression stays within the route vehicle's
    compartment capacities (per material, §4.2 v3), its volume and its
    weight; then remove the lowest-priority stop (smallest predicted_fill_pct,
    ties by (location_id, material_type)). Each step shrinks the sequence, so
    the loop terminates; removed stops surface as unserved with a
    ``shift_limit_exceeded`` reason (never hidden)."""
    shifted_routes: list[Route] = []
    removed_unserved: list[UnservedStop] = []
    for route in routes:
        sequence: list[Depot | DisposalSite | Stop] = list(route.sequence)
        vehicle_type = next(vt for vt in problem.vehicle_types if vt.id == route.vehicle_type_id)
        compartments = vehicle_type.compartment_capacities()
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
        distance, duration, progression, _material_progression = _route_metrics(sequence, problem)

        def within_caps(
            c_progression: list[tuple[int, int]],
            c_material_progression: list[dict[MaterialType, int]],
            c_compartments: dict[MaterialType, int] = compartments,
            c_vehicle_type: VehicleType = vehicle_type,
        ) -> bool:
            """Compartments (per material, §4.2 v3), total volume and weight
            all hold at every load-progression point of the candidate. The
            route's own vehicle layout is bound via defaults (B023: loop
            variables are not captured late)."""
            return (
                all(
                    all(load <= c_compartments[material] for material, load in entry.items())
                    for entry in c_material_progression
                )
                and all(v <= c_vehicle_type.volume_capacity_litres for v, _w in c_progression)
                and all(w <= c_vehicle_type.weight_capacity_kg for _v, w in c_progression)
            )

        while duration > problem.config.max_shift_minutes:
            # 1) disposal visit removable? keeps >= 1 stop, caps respected.
            disposal_positions = [
                i for i, node in enumerate(sequence) if isinstance(node, DisposalSite)
            ]
            if disposal_positions and any(isinstance(node, Stop) for node in sequence):
                position = disposal_positions[-1]  # deterministic: last visit
                candidate = [node for i, node in enumerate(sequence) if i != position]
                c_distance, c_duration, c_progression, c_material_progression = _route_metrics(
                    candidate, problem
                )
                if within_caps(c_progression, c_material_progression):
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
            distance, duration, progression, _material_progression = _route_metrics(
                sequence, problem
            )
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
    Volume feasibility is per material (§4.2 v3): a stop can only load its own
    material, so the binding bound is the largest COMPARTMENT for that
    material across types (validated compartments sum to each type's volume
    capacity, so the compartment bound dominates).
    """
    volume, weight = _stop_collected_quantities(stop, problem)
    max_compartment = max(
        vehicle_type.compartment_capacities()[stop.material_type]
        for vehicle_type in problem.vehicle_types
    )
    max_weight = max(vehicle_type.weight_capacity_kg for vehicle_type in problem.vehicle_types)
    if volume > max_compartment:
        return (
            f"collected volume {volume} L of {stop.material_type} exceeds the largest "
            f"compartment capacity {max_compartment} L for that material"
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


def _zero_volumes_by_material() -> dict[MaterialType, int]:
    return {material: 0 for material in MATERIALS}


def _empty_totals(problem: RoutingProblem) -> SolutionTotals:
    return SolutionTotals(
        distance_m=0,
        duration_min=0,
        collected_volume_litres=0,
        collected_volume_by_material=_zero_volumes_by_material(),
        collected_weight_kg=0,
        stops_served=0,
        stops_total=len(problem.stops),
        shift_minutes_used=0,
        stops_per_shift=0.0,
    )


def _cost_block(
    vehicles_used: int,
    fleet_count: int,
    config: RoutingConfig,
) -> SolutionCost:
    """§4.3 v3 cost formulas — pure derivations from ``RoutingConfig``
    parameters, labelled [predicted], never invoiced amounts (§4.4)."""
    cost_eur_per_day = vehicles_used * config.cost_per_truck_day_eur
    fleet_cost_eur_per_day = fleet_count * config.cost_per_truck_day_eur
    return SolutionCost(
        vehicles_used=vehicles_used,
        cost_eur_per_day=cost_eur_per_day,
        cost_eur_per_year=cost_eur_per_day * config.operating_days_per_year,
        fleet_cost=SolutionFleetCost(
            trucks=fleet_count,
            cost_eur_per_day=fleet_cost_eur_per_day,
            cost_eur_per_year=fleet_cost_eur_per_day * config.operating_days_per_year,
        ),
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
    including unserved stops. ``travel_time_mode`` and the derived ``cost``
    block echo config (§4.3 v3).
    """
    fleet_recommendation_result = recommend_fleet_for_problem(problem)
    provenance: Provenance = problem.travel.provenance
    travel_time_mode: TravelTimeMode = problem.config.travel_time_mode
    empty_cost = _cost_block(
        vehicles_used=0,
        fleet_count=fleet_recommendation_result.count,
        config=problem.config,
    )

    if not problem.stops:
        return RoutingSolution(
            status="optimal",
            objective_value=0,
            routes=[],
            unserved=[],
            totals=_empty_totals(problem),
            fleet_recommendation=fleet_recommendation_result,
            travel_time_mode=travel_time_mode,
            cost=empty_cost,
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
            travel_time_mode=travel_time_mode,
            cost=empty_cost,
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
    volume_by_material = _zero_volumes_by_material()
    for stop in served_stops:
        volume_by_material[stop.material_type] += _stop_collected_quantities(stop, problem)[0]
    shift_minutes_used, stops_per_shift = derive_shift_totals(
        [route.duration_minutes for route in routes], len(served_stops)
    )
    totals = SolutionTotals(
        distance_m=sum(route.distance_m for route in routes),
        duration_min=sum(route.duration_minutes for route in routes),
        collected_volume_litres=sum(
            _stop_collected_quantities(stop, problem)[0] for stop in served_stops
        ),
        collected_volume_by_material=volume_by_material,
        collected_weight_kg=sum(
            _stop_collected_quantities(stop, problem)[1] for stop in served_stops
        ),
        stops_served=len(served_stops),
        stops_total=len(problem.stops),
        shift_minutes_used=shift_minutes_used,
        stops_per_shift=stops_per_shift,
    )

    return RoutingSolution(
        status=status,
        objective_value=totals.distance_m,
        routes=routes,
        unserved=unserved,
        totals=totals,
        fleet_recommendation=fleet_recommendation_result,
        travel_time_mode=travel_time_mode,
        cost=_cost_block(
            vehicles_used=len(routes),
            fleet_count=fleet_recommendation_result.count,
            config=problem.config,
        ),
        distance_provenance=provenance,
    )
