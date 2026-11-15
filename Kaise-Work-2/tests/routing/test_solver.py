"""OR-Tools CVRP solver tests — docs/contracts.md §4.3 (RoutingSolution/Route)
and §4.4 invariants.

Fixtures are tiny hand-checkable matrices [demo assumption]; expected numbers
are derived from the fixture matrices, never guessed. Determinism is asserted
as *same status + same invariants across two runs* — a wall-clock-bounded
guided local search may vary exact sequences, so sequence equality is
deliberately NOT asserted (no faked bitwise determinism).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise

import pytest
from ortools.constraint_solver import routing_enums_pb2

from src.data.schema import MATERIALS, MaterialType
from src.routing.demo_config import (
    DEMO_DISPOSAL_SERVICE_MINUTES,
    DEMO_STOP_SERVICE_MINUTES,
)
from src.routing.fleet import FleetRecommendation
from src.routing.schemas import (
    Depot,
    DisposalSite,
    RoutingConfig,
    RoutingProblem,
    Stop,
    TravelMatrix,
    VehicleType,
    stop_point_id,
)
from src.routing.solver import (
    Route,
    RoutingSolution,
    RoutingSolverError,
    _build_layout,
    _build_model,
    _map_status,
    _resolve_status,
    _solve_model,
    _unserved_reason,
    solve,
)

# ---------------------------------------------------------------------------
# Hand-checkable fixture: 0 depot, 1 disposal, 2..4 stops
# ---------------------------------------------------------------------------

DEPOT = Depot(id="depot", name="Test Depot", lat=49.15, lon=9.22)
DISPOSAL = DisposalSite(
    id="disposal", name="Test Disposal", lat=49.17, lon=9.26, service_minutes=30
)

POINT_IDS = [
    "depot",
    "disposal",
    "loc-1:green",
    "loc-2:green",
    "loc-3:green",
    "loc-9:green",
]
LOC9_DISTANCE = [4000, 2000, 3000, 1500, 800]
LOC9_DURATION = [8, 4, 6, 3, 2]

# distance_m[i][j] / duration_min[i][j], symmetric, zero diagonal.
DISTANCE_M = [
    [0, 3000, 1000, 2000, 3000, 4000],
    [3000, 0, 2000, 1500, 1000, 2000],
    [1000, 2000, 0, 1500, 2500, 3000],
    [2000, 1500, 1500, 0, 1200, 1500],
    [3000, 1000, 2500, 1200, 0, 800],
    [4000, 2000, 3000, 1500, 800, 0],
]
DURATION_MIN = [
    [0, 6, 2, 4, 6, 8],
    [6, 0, 4, 3, 2, 4],
    [2, 4, 0, 3, 5, 6],
    [4, 3, 3, 0, 2, 3],
    [6, 2, 5, 2, 0, 2],
    [8, 4, 6, 3, 2, 0],
]

STOP_KEYS: list[tuple[str, MaterialType]] = [
    ("loc-1", "green"),
    ("loc-2", "green"),
    ("loc-3", "green"),
]


@dataclass(frozen=True)
class Fixture:
    problem: RoutingProblem
    stops: list[Stop]


def make_config(
    max_shift_minutes: int = 480,
    density: float = 1.0,
    solver_time_limit_s: float = 0.4,
) -> RoutingConfig:
    return RoutingConfig(
        max_shift_minutes=max_shift_minutes,
        densities_kg_per_litre={"brown": density, "green": density, "white": density},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
        solver_time_limit_s=solver_time_limit_s,
    )


def make_vehicle(
    vehicle_id: str = "truck",
    volume_capacity_litres: int = 2_000,
    weight_capacity_kg: int = 1_500,
    count_available: int = 2,
    compartment_volume_litres: dict[MaterialType, int] | None = None,
) -> VehicleType:
    """§4.2 v3: explicit compartment layout, or the 1/4-1/2-1/4 test split
    [demo assumption] — green gets HALF the drum so a full 1,000 L green
    container (the fixture stop) fits exactly one compartment on the
    default 2,000 L truck. Integer split; sums exactly to the capacity."""
    if compartment_volume_litres is None:
        quarter = volume_capacity_litres // 4
        half = volume_capacity_litres // 2
        compartment_volume_litres = {
            "brown": quarter,
            "green": half,
            "white": volume_capacity_litres - quarter - half,
        }
    return VehicleType(
        id=vehicle_id,
        name="Test Truck",
        volume_capacity_litres=volume_capacity_litres,
        weight_capacity_kg=weight_capacity_kg,
        count_available=count_available,
        compartment_volume_litres=dict(compartment_volume_litres),
    )


def make_stop(location_id: str, service_minutes: int = DEMO_STOP_SERVICE_MINUTES) -> Stop:
    return Stop(
        location_id=location_id,
        material_type="green",
        lat=49.15,
        lon=9.22,
        container_volume_litres=1_000,
        predicted_fill_pct=100.0,  # full -> collects the whole container
        service_minutes=service_minutes,
    )


def make_fixture(
    stops: list[Stop] | None = None,
    vehicles: list[VehicleType] | None = None,
    config: RoutingConfig | None = None,
    provenance: str = "haversine_straight_line_derived",
) -> Fixture:
    stops = stops if stops is not None else [make_stop(f"loc-{i}") for i in (1, 2, 3)]
    vehicles = vehicles if vehicles is not None else [make_vehicle()]
    config = config if config is not None else make_config()
    ids = [DEPOT.id, DISPOSAL.id] + [stop_point_id(stop) for stop in stops]
    # Map the fixed fixture matrices onto whatever subset/order the stops use.
    fixture_index = {point_id: i for i, point_id in enumerate(POINT_IDS)}
    distance = [[DISTANCE_M[fixture_index[a]][fixture_index[b]] for b in ids] for a in ids]
    duration = [[DURATION_MIN[fixture_index[a]][fixture_index[b]] for b in ids] for a in ids]
    travel = TravelMatrix(
        point_ids=ids,
        distance_m=distance,
        duration_min=duration,
        provenance=provenance,  # type: ignore[arg-type]
    )
    problem = RoutingProblem(
        depot=DEPOT,
        disposal_sites=[DISPOSAL],
        stops=stops,
        vehicle_types=vehicles,
        travel=travel,
        config=config,
    )
    return Fixture(problem=problem, stops=stops)


# ---------------------------------------------------------------------------
# Shared invariant validator (§4.4)
# ---------------------------------------------------------------------------


def assert_solution_invariants(solution: RoutingSolution, fixture: Fixture) -> None:
    problem = fixture.problem
    stop_cap_by_key = {
        stop_point_id(stop): (
            stop.collected_volume_litres,
            stop.collected_weight_kg(problem.config.densities_kg_per_litre[stop.material_type]),
        )
        for stop in problem.stops
    }

    # 1. Every stop exactly once: served (in exactly one route) or unserved.
    served_keys: list[str] = []
    for route in solution.routes:
        served_keys.extend(
            node_point_id
            for node_point_id in (
                stop_point_id(node) for node in route.sequence if isinstance(node, Stop)
            )
        )
    assert len(served_keys) == len(set(served_keys)), "a stop is served more than once"
    unserved_keys = [f"{key[0]}:{key[1]}" for key, _reason in solution.unserved]
    assert set(served_keys) | set(unserved_keys) == set(stop_cap_by_key)
    assert not (set(served_keys) & set(unserved_keys))
    assert solution.totals.stops_served == len(served_keys)
    assert solution.totals.stops_total == len(problem.stops)
    assert solution.totals.stops_served + len(solution.unserved) == len(problem.stops)
    assert len(solution.unserved) == len(set(unserved_keys)), "duplicate unserved entry"
    for _key, reason in solution.unserved:
        assert isinstance(reason, str) and reason

    # 2. Volume and weight capacities hold at every load-progression point;
    #    progression has one entry per collection stop; depot ends the route.
    #    §4.2 v3: per-material load stays within the route vehicle's
    #    COMPARTMENT capacity for that material; a disposal visit resets
    #    every material dimension (§4.4).
    collected_volume = 0
    collected_weight = 0
    for route in solution.routes:
        vehicle = next(v for v in problem.vehicle_types if v.id == route.vehicle_type_id)
        compartments = vehicle.compartment_capacities()
        assert isinstance(route.sequence[0], Depot)
        assert isinstance(route.sequence[-1], Depot)
        stops_in_sequence = [node for node in route.sequence if isinstance(node, Stop)]
        assert len(route.load_progression) == len(stops_in_sequence)
        running_volume = 0
        running_weight = 0
        running_by_material: dict[MaterialType, int] = {material: 0 for material in MATERIALS}
        progression_index = 0
        for node in route.sequence:
            if isinstance(node, DisposalSite):
                running_volume = 0  # unload resets the load (§4.3)
                running_weight = 0
                running_by_material = {material: 0 for material in MATERIALS}
            elif isinstance(node, Stop):
                running_volume += node.collected_volume_litres
                running_weight += node.collected_weight_kg(
                    problem.config.densities_kg_per_litre[node.material_type]
                )
                running_by_material[node.material_type] += node.collected_volume_litres
                volume, weight = route.load_progression[progression_index]
                assert (volume, weight) == (running_volume, running_weight), (
                    f"load progression mismatch at entry {progression_index}"
                )
                assert volume <= vehicle.volume_capacity_litres, "volume capacity exceeded"
                assert weight <= vehicle.weight_capacity_kg, "weight capacity exceeded"
                assert (
                    running_by_material[node.material_type] <= compartments[node.material_type]
                ), (
                    f"compartment capacity exceeded for {node.material_type} "
                    f"({running_by_material[node.material_type]} L > "
                    f"{compartments[node.material_type]} L)"
                )
                progression_index += 1
        collected_volume += sum(node.collected_volume_litres for node in stops_in_sequence)
        collected_weight += sum(
            node.collected_weight_kg(problem.config.densities_kg_per_litre[node.material_type])
            for node in stops_in_sequence
        )

    # 3. Shift limit holds on every route (hard constraint -> no violation).
    for route in solution.routes:
        assert route.duration_minutes <= problem.config.max_shift_minutes

    # 4. Totals reconcile with per-route sums; §4.3 v3 per-material split.
    collected_by_material: dict[MaterialType, int] = {material: 0 for material in MATERIALS}
    for route in solution.routes:
        for node in route.sequence:
            if isinstance(node, Stop):
                collected_by_material[node.material_type] += node.collected_volume_litres
    assert solution.totals.distance_m == sum(route.distance_m for route in solution.routes)
    assert solution.totals.duration_min == sum(route.duration_minutes for route in solution.routes)
    assert solution.totals.collected_volume_litres == collected_volume
    assert solution.totals.collected_volume_by_material == collected_by_material
    assert sum(solution.totals.collected_volume_by_material.values()) == (
        solution.totals.collected_volume_litres
    )
    assert solution.totals.collected_weight_kg == collected_weight
    assert solution.objective_value == solution.totals.distance_m

    # 4b. §4.3 v3 cost block and travel_time_mode echo — pure derivations
    # from RoutingConfig parameters, [predicted], never invoiced amounts.
    rate = problem.config.cost_per_truck_day_eur
    days = problem.config.operating_days_per_year
    cost = solution.cost
    assert cost.vehicles_used == len(solution.routes)
    assert cost.cost_eur_per_day == cost.vehicles_used * rate
    assert cost.cost_eur_per_year == cost.cost_eur_per_day * days
    assert cost.fleet_cost.trucks == solution.fleet_recommendation.count
    assert cost.fleet_cost.cost_eur_per_day == cost.fleet_cost.trucks * rate
    assert cost.fleet_cost.cost_eur_per_year == cost.fleet_cost.cost_eur_per_day * days
    assert solution.travel_time_mode == problem.config.travel_time_mode

    # 5. Fleet recommendation echoes the §4.4 math over full demand.
    volumes = sum(stop.collected_volume_litres for stop in problem.stops)
    weights = sum(
        stop.collected_weight_kg(problem.config.densities_kg_per_litre[stop.material_type])
        for stop in problem.stops
    )
    rec = solution.fleet_recommendation
    assert isinstance(rec, FleetRecommendation)
    expected_count = max(
        -(
            -volumes
            // next(
                v.volume_capacity_litres
                for v in problem.vehicle_types
                if v.id == rec.vehicle_type_id
            )
        ),
        -(
            -weights
            // next(
                v.weight_capacity_kg for v in problem.vehicle_types if v.id == rec.vehicle_type_id
            )
        ),
    )
    assert rec.count == expected_count

    # 6. Provenance is echoed, never renamed (never "road").
    assert solution.distance_provenance == problem.travel.provenance
    assert solution.distance_provenance != "road"
    assert solution.status in {"optimal", "feasible", "infeasible", "timeout"}


# ---------------------------------------------------------------------------
# Core solving behaviour
# ---------------------------------------------------------------------------


def test_all_stops_served_when_capacity_allows() -> None:
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
    )
    solution = solve(fixture.problem)
    assert solution.status in {"optimal", "feasible"}
    assert solution.unserved == []
    assert solution.totals.stops_served == 2
    assert solution.routes, "expected at least one non-empty route"
    assert_solution_invariants(solution, fixture)


def test_capacity_respected_at_every_progression_point_many_stops() -> None:
    fixture = make_fixture()
    solution = solve(fixture.problem)
    assert_solution_invariants(solution, fixture)


def test_weight_forces_disposal_trip_and_resets_load() -> None:
    # One truck 2000 L / 1500 kg; two full 1000 L containers at density 1.0
    # -> 2000 kg total > 1500 kg, so a disposal unload must sit between stops.
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        vehicles=[make_vehicle(volume_capacity_litres=5_000, weight_capacity_kg=1_500)],
    )
    solution = solve(fixture.problem)
    assert solution.status in {"optimal", "feasible"}
    assert solution.totals.stops_served == 2
    disposal_routes = [
        route
        for route in solution.routes
        if any(isinstance(node, DisposalSite) for node in route.sequence)
    ]
    assert disposal_routes, "weight over capacity must force a disposal visit"
    for route in disposal_routes:
        stops_after_disposal: list[Stop] = []
        seen_disposal = False
        for node in route.sequence:
            if isinstance(node, DisposalSite):
                seen_disposal = True
                stops_after_disposal = []
            elif isinstance(node, Stop) and seen_disposal:
                stops_after_disposal.append(node)
        if stops_after_disposal:
            volume_after_reset, weight_after_reset = route.load_progression[
                len(route.load_progression) - len(stops_after_disposal)
            ]
            first_after = stops_after_disposal[0]
            assert volume_after_reset == first_after.collected_volume_litres
            assert weight_after_reset == first_after.collected_weight_kg(1.0)
    assert_solution_invariants(solution, fixture)


def test_shift_violation_is_surfaced_as_unserved_not_hidden() -> None:
    # Shift 30 min: loc-1 solo trip 2+10+2 = 14 min (served); loc-3 solo trip
    # 6+25+6 = 37 min > 30 (unserved, reason explains the shift).
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-3", service_minutes=25)],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
        config=make_config(max_shift_minutes=30),
    )
    solution = solve(fixture.problem)
    assert solution.totals.stops_served == 1
    assert len(solution.unserved) == 1
    key, reason = solution.unserved[0]
    assert key == ("loc-3", "green")
    assert "shift" in reason.lower()
    assert "max_shift_minutes" in reason
    assert_solution_invariants(solution, fixture)


def test_capacity_infeasible_stop_dropped_with_reason() -> None:
    # Truck 2,000 L (green compartment 1,000 L on the 1/4-1/2-1/4 split):
    # the 1,000 L container fits its material's compartment exactly; the
    # 2,000 L container exceeds ANY green compartment -> dropped with a
    # per-material volume reason (§4.2 v3; never silently hidden).
    big_stop = make_stop("loc-1")
    huge_stop = Stop(
        location_id="loc-9",
        material_type="green",
        lat=49.15,
        lon=9.22,
        container_volume_litres=2_000,
        predicted_fill_pct=100.0,
        service_minutes=10,
    )
    fixture = make_fixture(
        stops=[big_stop, huge_stop],
        vehicles=[make_vehicle(volume_capacity_litres=2_000, weight_capacity_kg=10_000)],
    )
    solution = solve(fixture.problem)
    assert solution.totals.stops_served == 1
    assert len(solution.unserved) == 1
    key, reason = solution.unserved[0]
    assert key == ("loc-9", "green")
    assert "volume" in reason.lower()
    assert_solution_invariants(solution, fixture)


def test_counts_reconcile_on_partial_service() -> None:
    # 3 full containers = 3000 L / 3000 kg vs ONE 2000 L / 1500 kg truck:
    # some stops must remain unserved, never silently dropped.
    fixture = make_fixture(
        vehicles=[make_vehicle(count_available=1)],
    )
    solution = solve(fixture.problem)
    assert solution.totals.stops_served + len(solution.unserved) == 3
    assert solution.totals.stops_served >= 1
    assert_solution_invariants(solution, fixture)


def test_unserved_reasons_deterministic() -> None:
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-3", service_minutes=25)],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
        config=make_config(max_shift_minutes=30),
    )
    first = solve(fixture.problem)
    second = solve(fixture.problem)
    assert [u.reason for u in first.unserved] == [u.reason for u in second.unserved]
    assert [u.stop_key for u in first.unserved] == [u.stop_key for u in second.unserved]


def test_unserved_reason_reports_true_fleet_size_not_expanded() -> None:
    # Regression (M12 e2e smoke): the reason must state the true fleet size,
    # summed over the UNexpanded vehicle_types, never over the per-vehicle
    # expanded list (one type x count 3 would multiply to "9 vehicles").
    # The stop below fits every capacity/shift limit -> insertion branch.
    fixture = make_fixture(
        stops=[make_stop("loc-1")],
        vehicles=[make_vehicle(count_available=3)],
    )
    reason = _unserved_reason(fixture.stops[0], fixture.problem)
    assert "no feasible insertion" in reason
    assert "(3 vehicles)" in reason
    assert "(9 vehicles)" not in reason

    multi_type = make_fixture(
        stops=[make_stop("loc-1")],
        vehicles=[
            make_vehicle(
                vehicle_id="small",
                volume_capacity_litres=1_200,
                weight_capacity_kg=1_100,
                count_available=1,
                # Explicit layout: green fits a 1,000 L container exactly.
                compartment_volume_litres={"green": 1_000, "brown": 100, "white": 100},
            ),
            make_vehicle(
                vehicle_id="large",
                volume_capacity_litres=3_000,
                weight_capacity_kg=2_500,
                count_available=2,
                compartment_volume_litres={"green": 1_000, "brown": 1_000, "white": 1_000},
            ),
        ],
    )
    reason_multi = _unserved_reason(multi_type.stops[0], multi_type.problem)
    assert "(3 vehicles)" in reason_multi


def test_empty_stops_returns_zeroed_solution() -> None:
    fixture = make_fixture(stops=[])
    solution = solve(fixture.problem)
    assert solution.status == "optimal"
    assert solution.routes == []
    assert solution.unserved == []
    assert solution.objective_value == 0
    assert solution.totals.distance_m == 0
    assert solution.totals.duration_min == 0
    assert solution.totals.collected_volume_litres == 0
    assert solution.totals.collected_weight_kg == 0
    assert solution.totals.stops_served == 0
    assert solution.totals.stops_total == 0
    assert solution.fleet_recommendation is not None
    assert solution.fleet_recommendation.count == 0
    assert solution.distance_provenance == fixture.problem.travel.provenance


def test_provenance_echo_external() -> None:
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        provenance="external",
    )
    solution = solve(fixture.problem)
    assert solution.distance_provenance == "external"
    assert_solution_invariants(solution, fixture)


def test_route_distance_and_duration_match_matrix_walk() -> None:
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
    )
    solution = solve(fixture.problem)
    assert_solution_invariants(solution, fixture)
    ids = fixture.problem.travel.point_ids
    distance = fixture.problem.travel.distance_m
    duration = fixture.problem.travel.duration_min
    services: dict[str, int] = {DEPOT.id: 0, DISPOSAL.id: DEMO_DISPOSAL_SERVICE_MINUTES}
    for stop in fixture.problem.stops:
        services[stop_point_id(stop)] = stop.service_minutes
    for route in solution.routes:
        seq_ids = [
            node.id if not isinstance(node, Stop) else stop_point_id(node)
            for node in route.sequence
        ]
        walk_distance = sum(distance[ids.index(a)][ids.index(b)] for a, b in pairwise(seq_ids))
        walk_duration = sum(
            duration[ids.index(a)][ids.index(b)] + services[a] for a, b in pairwise(seq_ids)
        )
        assert route.distance_m == walk_distance
        assert route.duration_minutes == walk_duration


def test_objective_equals_total_distance() -> None:
    fixture = make_fixture(
        vehicles=[make_vehicle(count_available=1)],
    )
    solution = solve(fixture.problem)
    assert solution.objective_value == solution.totals.distance_m


def test_input_order_independence_of_stop_list() -> None:
    stops = [make_stop(f"loc-{i}") for i in (1, 2, 3)]
    forward = make_fixture(stops=list(stops))
    reversed_fixture = make_fixture(stops=list(reversed(stops)))
    first = solve(forward.problem)
    second = solve(reversed_fixture.problem)
    assert first.status == second.status
    assert {u.stop_key for u in first.unserved} == {u.stop_key for u in second.unserved}
    assert first.totals.stops_served == second.totals.stops_served
    assert first.totals.collected_volume_litres == second.totals.collected_volume_litres


def test_multiple_vehicle_types_capacities_and_recommendation() -> None:
    small = make_vehicle(
        vehicle_id="aa_small",
        volume_capacity_litres=1_200,
        weight_capacity_kg=1_100,
        count_available=1,
    )
    large = make_vehicle(
        vehicle_id="zz_large",
        volume_capacity_litres=10_000,
        weight_capacity_kg=10_000,
        count_available=1,
    )
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2"), make_stop("loc-3")],
        vehicles=[small, large],
    )
    solution = solve(fixture.problem)
    assert_solution_invariants(solution, fixture)
    route_type_ids = {route.vehicle_type_id for route in solution.routes}
    assert route_type_ids <= {"aa_small", "zz_large"}
    # Full demand 3000 L / 3000 kg: small -> 3, large -> 1 => min is large.
    assert solution.fleet_recommendation.vehicle_type_id == "zz_large"
    assert solution.fleet_recommendation.count == 1


# ---------------------------------------------------------------------------
# §4.2 v3 compartments and §4.3 v3 cost block
# ---------------------------------------------------------------------------


def test_compartment_overflow_forces_disposal_even_when_weight_fits() -> None:
    # One truck 2,000 L / 5,000 kg (green compartment 1,000 L on the
    # 1/4-1/2-1/4 split): two full 1,000 L green containers fit the drum
    # AND the weight cap in total, but each material compartment takes only
    # one container — a disposal unload must sit between the two stops
    # (§4.4: materials never mix; a disposal resets every material dimension).
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        vehicles=[
            make_vehicle(
                vehicle_id="truck",
                volume_capacity_litres=2_000,
                weight_capacity_kg=5_000,
                count_available=1,
            )
        ],
    )
    solution = solve(fixture.problem)
    assert solution.status in {"optimal", "feasible"}
    assert solution.totals.stops_served == 2
    # Compartment visibility (§4.3 v3): both green containers collected.
    assert solution.totals.collected_volume_by_material["green"] == 2_000
    assert solution.totals.collected_volume_by_material["brown"] == 0
    assert solution.totals.collected_volume_by_material["white"] == 0
    # The serving route must contain a disposal visit between green stops —
    # the green compartment cannot hold both without the reset.
    route = next(route for route in solution.routes if len(route.sequence) > 2)
    green_positions = [i for i, node in enumerate(route.sequence) if isinstance(node, Stop)]
    disposal_positions = [
        i for i, node in enumerate(route.sequence) if isinstance(node, DisposalSite)
    ]
    assert disposal_positions, "compartment overflow must force a disposal visit"
    assert min(green_positions) < disposal_positions[0] < max(green_positions)
    assert_solution_invariants(solution, fixture)


def test_cost_block_derives_from_explicit_config_parameters() -> None:
    """§4.3 v3 formulas over NON-default config values (250 EUR/day,
    100 days/year): day = vehicles_used x 250; year = day x 100; fleet cost
    from fleet_recommendation.count — labelled [predicted] derivations."""
    config = RoutingConfig(
        max_shift_minutes=480,
        densities_kg_per_litre={"brown": 1.0, "green": 1.0, "white": 1.0},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
        cost_per_truck_day_eur=250.0,
        operating_days_per_year=100,
    )
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
        config=config,
    )
    solution = solve(fixture.problem)
    assert solution.cost.vehicles_used == len(solution.routes)
    assert solution.cost.cost_eur_per_day == solution.cost.vehicles_used * 250.0
    assert solution.cost.cost_eur_per_year == solution.cost.cost_eur_per_day * 100
    assert solution.cost.fleet_cost.trucks == solution.fleet_recommendation.count
    assert solution.cost.fleet_cost.cost_eur_per_day == (solution.cost.fleet_cost.trucks * 250.0)
    assert solution.cost.fleet_cost.cost_eur_per_year == (
        solution.cost.fleet_cost.cost_eur_per_day * 100
    )
    assert_solution_invariants(solution, fixture)


def test_travel_time_mode_is_echoed_from_config() -> None:
    """§4.3 v3: the effective travel_time_mode is echoed on the solution;
    with an explicit fixture matrix the mode changes durations accounting
    nowhere — it is a pure echo here (matrix derivation lives in geography)."""
    config = RoutingConfig(
        max_shift_minutes=480,
        densities_kg_per_litre={"brown": 1.0, "green": 1.0, "white": 1.0},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
        travel_time_mode="haversine_derived",
    )
    fixture = make_fixture(
        stops=[make_stop("loc-1")],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
        config=config,
    )
    solution = solve(fixture.problem)
    assert solution.travel_time_mode == "haversine_derived"
    assert_solution_invariants(solution, fixture)


# ---------------------------------------------------------------------------
# Determinism: same status + invariants across two runs (no bitwise claims)
# ---------------------------------------------------------------------------


def test_two_runs_same_status_and_valid_invariants() -> None:
    fixture = make_fixture(vehicles=[make_vehicle(count_available=1)])
    statuses: set[str] = set()
    for _ in range(2):
        solution = solve(fixture.problem)
        statuses.add(solution.status)
        assert_solution_invariants(solution, fixture)
    assert len(statuses) == 1, f"status varied across runs: {statuses}"


def test_deterministic_with_external_provenance_matrix() -> None:
    fixture = make_fixture(provenance="external")
    statuses: set[str] = set()
    for _ in range(2):
        solution = solve(fixture.problem)
        statuses.add(solution.status)
        assert_solution_invariants(solution, fixture)
    assert len(statuses) == 1


# ---------------------------------------------------------------------------
# Status mapping (OR-Tools -> contract §4.3)
# ---------------------------------------------------------------------------

STATUS = routing_enums_pb2.RoutingSearchStatus.Value


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        (STATUS.ROUTING_OPTIMAL, "optimal"),
        (STATUS.ROUTING_SUCCESS, "feasible"),
        (STATUS.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED, "feasible"),
        (STATUS.ROUTING_FAIL, "infeasible"),
        (STATUS.ROUTING_INFEASIBLE, "infeasible"),
        (STATUS.ROUTING_FAIL_TIMEOUT, "timeout"),
    ],
)
def test_map_status(raw_status: int, expected: str) -> None:
    assert _map_status(raw_status) == expected


@pytest.mark.parametrize("raw_status", [STATUS.ROUTING_NOT_SOLVED, STATUS.ROUTING_INVALID])
def test_map_status_raises_on_internal_statuses(raw_status: int) -> None:
    with pytest.raises(RoutingSolverError):
        _map_status(raw_status)


def test_timeout_status_reports_objective_none_when_no_solution() -> None:
    # A 1 ms limit on a 3-stop problem usually still finds a first solution;
    # the assertions stay honest for both outcomes instead of pretending.
    fixture = make_fixture(config=make_config(solver_time_limit_s=0.001))
    solution = solve(fixture.problem)
    if solution.status == "timeout":
        assert solution.objective_value is None
        assert solution.routes == []
        assert solution.totals.stops_served == 0
        assert len(solution.unserved) == 3
        assert all(
            "safety cap fired" in reason.lower() and "not reproducible" in reason.lower()
            for _k, reason in solution.unserved
        )
    else:
        assert solution.status in {"optimal", "feasible"}
        assert_solution_invariants(solution, fixture)


def test_map_status_is_pure_callable() -> None:
    mapper: Callable[[int], str] = _map_status
    assert isinstance(mapper(STATUS.ROUTING_OPTIMAL), str)


# ---------------------------------------------------------------------------
# Route shape contract §4.3
# ---------------------------------------------------------------------------


def test_route_sequence_starts_and_ends_at_depot_and_contains_progression() -> None:
    fixture = make_fixture(
        stops=[make_stop("loc-1"), make_stop("loc-2")],
        vehicles=[make_vehicle(volume_capacity_litres=10_000, weight_capacity_kg=10_000)],
    )
    solution = solve(fixture.problem)
    assert solution.routes
    for route in solution.routes:
        assert isinstance(route, Route)
        assert isinstance(route.sequence[0], Depot)
        assert isinstance(route.sequence[-1], Depot)
        stops = [n for n in route.sequence if isinstance(n, Stop)]
        assert stops, "empty routes must be omitted"
        assert route.vehicle_type_id == "truck"
        assert len(route.load_progression) == len(stops)
        for volume, weight in route.load_progression:
            assert isinstance(volume, int) and isinstance(weight, int)


# ---------------------------------------------------------------------------
# §4.7 v2 determinism gate: solution budget reached ⇒ identical distances
# ---------------------------------------------------------------------------

GRID_COLS = 8
GRID_STOPS = 48  # >= ~40: GLS must still be finding solutions at the budget


def make_grid_problem() -> RoutingProblem:
    """48 synthetic grid stops with varied derived pairwise distances — big
    enough that guided local search hits the 200-solution budget instead of
    exhausting on its own. Distances are deterministic derived integers
    (metre-scaled planar approximation), symmetric with zero diagonal."""
    stops = [
        Stop(
            location_id=f"grid-{i:03d}",
            material_type="green",
            lat=49.15 + 0.002 * (i // GRID_COLS),
            lon=9.22 + 0.002 * (i % GRID_COLS),
            container_volume_litres=1_000,
            predicted_fill_pct=100.0,
            service_minutes=2,  # keeps 48 stops far inside the shift
        )
        for i in range(GRID_STOPS)
    ]
    ids = [DEPOT.id, DISPOSAL.id] + [stop_point_id(stop) for stop in stops]
    points = [(DEPOT.lat, DEPOT.lon), (DISPOSAL.lat, DISPOSAL.lon)] + [
        (stop.lat, stop.lon) for stop in stops
    ]
    n = len(ids)
    distance = [[0] * n for _ in range(n)]
    duration = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            (lat_i, lon_i), (lat_j, lon_j) = points[i], points[j]
            metres = max(
                1,
                round(math.hypot((lat_i - lat_j) * 111_320.0, (lon_i - lon_j) * 74_200.0)),
            )
            distance[i][j] = distance[j][i] = metres
            duration[i][j] = duration[j][i] = max(1, metres // 500)
    travel = TravelMatrix(
        point_ids=ids,
        distance_m=distance,
        duration_min=duration,
        provenance="haversine_straight_line_derived",
    )
    config = RoutingConfig(
        max_shift_minutes=600,
        densities_kg_per_litre={"brown": 1.0, "green": 1.0, "white": 1.0},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
        # §4.6 v2 defaults: solver_solution_limit=200 (primary stop),
        # solver_time_limit_s=30.0 (safety cap only) — asserted below.
    )
    return RoutingProblem(
        depot=DEPOT,
        disposal_sites=[DISPOSAL],
        stops=stops,
        vehicle_types=[make_vehicle(volume_capacity_litres=60_000, weight_capacity_kg=60_000)],
        travel=travel,
        config=config,
    )


def test_solution_budget_is_reached_and_distances_identical_across_five_solves() -> None:
    """§4.4/§4.7 gate: repeated solves that reach the fixed solution budget
    return identical totals.distance_m (deterministic stop criterion)."""
    problem = make_grid_problem()
    assert problem.config.solver_solution_limit == 200
    assert problem.config.solver_time_limit_s == 30.0

    # Probe the internals once: the budget must actually be the stopping
    # reason (solutions_found == limit), not early exhaustion or the cap.
    layout = _build_layout(problem, set())
    _manager, routing = _build_model(problem, layout)
    outcome = _solve_model(problem, routing)
    assert outcome.solutions_found == problem.config.solver_solution_limit
    assert outcome.solutions_found == 200

    distances: list[int] = []
    for _ in range(5):
        solution = solve(problem)
        assert solution.status == "feasible"  # budget stop, never timeout
        distances.append(solution.totals.distance_m)
        assert solution.totals.stops_served + len(solution.unserved) == GRID_STOPS
    assert_solution_invariants(solution, Fixture(problem=problem, stops=problem.stops))
    assert len(set(distances)) == 1, f"distance varied across budgeted solves: {distances}"


# ---------------------------------------------------------------------------
# §4.7 v2 _resolve_status: stop-criterion evidence classification
# ---------------------------------------------------------------------------


def test_resolve_status_cap_fired_with_solution_shortfall_is_timeout() -> None:
    # Raw status maps to "feasible", but few solutions were found and the
    # measured elapsed time sits at the configured cap ⇒ honest "timeout".
    fixture = make_fixture(config=make_config(solver_time_limit_s=0.4))
    status = _resolve_status(
        STATUS.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED,
        solutions_found=3,
        elapsed_s=0.4,
        problem=fixture.problem,
    )
    assert status == "timeout"


def test_resolve_status_budget_reached_is_feasible_even_if_slow() -> None:
    # The primary stop is the solution budget: reaching it is deterministic
    # and stays "feasible" even when elapsed time brushed the safety cap.
    fixture = make_fixture(config=make_config(solver_time_limit_s=0.4))
    status = _resolve_status(
        STATUS.ROUTING_SUCCESS,
        solutions_found=200,  # == config.solver_solution_limit
        elapsed_s=0.9,
        problem=fixture.problem,
    )
    assert status == "feasible"


def test_resolve_status_exhausted_early_is_feasible() -> None:
    # Small problem: search ended on its own before both limits ⇒ the
    # deterministic "feasible", not a timeout.
    fixture = make_fixture(config=make_config(solver_time_limit_s=0.4))
    status = _resolve_status(
        STATUS.ROUTING_PARTIAL_SUCCESS_LOCAL_OPTIMUM_NOT_REACHED,
        solutions_found=3,
        elapsed_s=0.05,  # well under 0.4 - tolerance
        problem=fixture.problem,
    )
    assert status == "feasible"


def test_resolve_status_raw_timeout_stays_timeout() -> None:
    # FAIL_TIMEOUT maps straight to "timeout" regardless of the counters.
    fixture = make_fixture(config=make_config(solver_time_limit_s=0.4))
    status = _resolve_status(
        STATUS.ROUTING_FAIL_TIMEOUT,
        solutions_found=1,
        elapsed_s=0.05,
        problem=fixture.problem,
    )
    assert status == "timeout"
