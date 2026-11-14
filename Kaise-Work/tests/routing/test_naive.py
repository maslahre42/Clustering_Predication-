"""Naive fixed-order baseline tests (M12) — docs/contracts.md §4.3/§4.4.

Every fixture is hand-built (no CSV): small symmetric travel matrices with
hand-checked distances (metres) and durations (minutes). Capacities, service
times and shift caps are [demo assumption] test values — the tests pin the
simulation arithmetic and §4.4 invariants, not any real-world fleet.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeAlias

from src.data.schema import MaterialType
from src.routing.fleet import FleetRecommendation
from src.routing.naive import (
    METHOD_NAIVE_SWEEP_ORDER,
    NaiveRoute,
    naive_fixed_order_simulation,
    naive_sweep_simulation,
    sweep_visit_order,
)
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

DEPOT = Depot(id="depot", name="Test Depot", lat=49.15, lon=9.22)
DISPOSAL = DisposalSite(
    id="disposal", name="Test Disposal", lat=49.17, lon=9.26, service_minutes=30
)
SITE_A = DisposalSite(id="site-a", name="Test Disposal A", lat=49.17, lon=9.26, service_minutes=30)
SITE_B = DisposalSite(id="site-b", name="Test Disposal B", lat=49.18, lon=9.27, service_minutes=30)

PairKey: TypeAlias = tuple[str, str]
MatrixPairs: TypeAlias = dict[PairKey, tuple[int, int]]  # ((distance_m, duration_min))


def pk(a: str, b: str) -> PairKey:
    """Sorted unordered pair key for the symmetric matrix fixtures."""
    return (a, b) if a < b else (b, a)


def make_matrix(point_ids: list[str], pairs: MatrixPairs) -> TravelMatrix:
    n = len(point_ids)
    distance = [[0] * n for _ in range(n)]
    duration = [[0] * n for _ in range(n)]
    index = {point_id: i for i, point_id in enumerate(point_ids)}
    for (a, b), (distance_m, duration_min) in pairs.items():
        i = index[a]
        j = index[b]
        distance[i][j] = distance_m
        distance[j][i] = distance_m
        duration[i][j] = duration_min
        duration[j][i] = duration_min
    return TravelMatrix(
        point_ids=point_ids,
        distance_m=distance,
        duration_min=duration,
        provenance="haversine_straight_line_derived",
    )


def make_stop(
    location_id: str,
    material_type: MaterialType,
    fill_pct: float,
    volume_litres: int = 600,
    service_minutes: int = 10,
    lat: float = 0.0,
    lon: float = 0.0,
) -> Stop:
    return Stop(
        location_id=location_id,
        material_type=material_type,
        lat=lat,
        lon=lon,
        container_volume_litres=volume_litres,
        predicted_fill_pct=fill_pct,
        service_minutes=service_minutes,
    )


def make_config(max_shift_minutes: int) -> RoutingConfig:
    return RoutingConfig(
        max_shift_minutes=max_shift_minutes,
        densities_kg_per_litre={"brown": 0.5, "green": 0.5, "white": 0.5},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
        solver_time_limit_s=1.0,
    )


def make_problem(
    stops: Sequence[Stop],
    point_ids: list[str],
    pairs: MatrixPairs,
    *,
    max_shift_minutes: int = 480,
    volume_capacity_litres: int = 1000,
    weight_capacity_kg: int = 600,
    count_available: int = 2,
    disposal_sites: Sequence[DisposalSite] = (DISPOSAL,),
) -> RoutingProblem:
    # Fixtures key pairs by short ids ("s1"); the RoutingProblem travel matrix
    # must carry contract point ids: depot + disposal ids + stop_point_id(stop).
    translation = {stop.location_id: stop_point_id(stop) for stop in stops}
    resolved_ids = [translation.get(point_id, point_id) for point_id in point_ids]
    resolved_pairs = {
        (translation.get(a, a), translation.get(b, b)): value for (a, b), value in pairs.items()
    }
    return RoutingProblem(
        depot=DEPOT,
        disposal_sites=list(disposal_sites),
        stops=list(stops),
        vehicle_types=[
            VehicleType(
                id="truck",
                name="Test Truck",
                volume_capacity_litres=volume_capacity_litres,
                weight_capacity_kg=weight_capacity_kg,
                count_available=count_available,
            )
        ],
        travel=make_matrix(resolved_ids, resolved_pairs),
        config=make_config(max_shift_minutes),
    )


def sequence_ids(route: NaiveRoute) -> list[str]:
    """Point ids of a route sequence (depot/disposal ids, stop point ids)."""
    return [
        node.id if isinstance(node, (Depot, DisposalSite)) else stop_point_id(node)
        for node in route.sequence
    ]


def stop_key(location_id: str, material_type: MaterialType) -> tuple[str, MaterialType]:
    return (location_id, material_type)


# ---------------------------------------------------------------------------
# Overflow -> disposal visit first (unload reset)
# ---------------------------------------------------------------------------


def test_overflow_visits_disposal_first() -> None:
    # Hand check (vehicle cap 1000 L): s1 loads 600 L; s2 would overflow
    # (600 + 600 > 1000), so the truck unloads at the disposal in between.
    # Route: depot ->s1 -> disposal -> s2 -> depot.
    # distance_m = 500 + 500 + 500 + 1000 = 2500.
    # duration_min = (10+10 s1) + (10+30 disposal) + (10+10 s2) + 20 return = 100.
    stops = [
        make_stop("s1", "brown", 100.0),
        make_stop("s2", "green", 100.0),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("s1", "disposal"): (500, 10),
        pk("disposal", "s2"): (500, 10),
        pk("depot", "disposal"): (750, 15),
        pk("depot", "s2"): (1000, 20),
        pk("s1", "s2"): (1000, 20),
    }
    problem = make_problem(stops, ["depot", "disposal", "s1", "s2"], pairs)
    solution = naive_fixed_order_simulation(problem)

    assert solution.method == "naive_fixed_order"
    assert solution.status == "complete"
    assert solution.shift_violations == []
    assert len(solution.routes) == 1  # second vehicle never dispatched
    route = solution.routes[0]
    assert route.vehicle_index == 0
    assert sequence_ids(route) == [
        "depot",
        "s1:brown",
        "disposal",
        "s2:green",
        "depot",
    ]
    # Load progression after each STOP only; the disposal reset shows in the
    # second entry being 600 L again, never above the 1000 L capacity.
    assert route.load_progression == [(600, 300), (600, 300)]
    assert route.distance_m == 2500
    assert route.duration_minutes == 100
    assert solution.unserved == []
    assert solution.totals.distance_m == 2500
    assert solution.totals.duration_min == 100
    assert solution.totals.collected_volume_litres == 1200
    assert solution.totals.collected_weight_kg == 600
    assert solution.totals.stops_served == 2
    assert solution.totals.stops_total == 2
    assert solution.distance_provenance == "haversine_straight_line_derived"


# ---------------------------------------------------------------------------
# Shift end -> vehicle returns to depot, next vehicle continues
# ---------------------------------------------------------------------------


def test_shift_end_hands_over_to_next_vehicle() -> None:
    # Hand check (max_shift 30, service 10): s1 fits (10+10=20). s2 would need
    # leg 30 + service 10 = 40 -> 20+40 > 30, so vehicle 0 returns (10 min) and
    # vehicle 1 serves s2. Each route: depot->stop->depot = 1000 m / 30 min.
    stops = [
        make_stop("s1", "brown", 100.0, volume_litres=300),
        make_stop("s2", "green", 100.0, volume_litres=300),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("depot", "s2"): (500, 10),
        pk("s1", "s2"): (1500, 30),
        pk("depot", "disposal"): (800, 16),
        pk("s1", "disposal"): (900, 18),
        pk("s2", "disposal"): (900, 18),
    }
    problem = make_problem(
        stops,
        ["depot", "disposal", "s1", "s2"],
        pairs,
        max_shift_minutes=30,
    )
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "complete"
    assert solution.shift_violations == []
    assert [route.vehicle_index for route in solution.routes] == [0, 1]
    assert [route.duration_minutes for route in solution.routes] == [30, 30]
    assert [route.distance_m for route in solution.routes] == [1000, 1000]
    assert solution.routes[0].load_progression == [(300, 150)]
    assert solution.routes[1].load_progression == [(300, 150)]
    assert sequence_ids(solution.routes[0]) == ["depot", "s1:brown", "depot"]
    assert sequence_ids(solution.routes[1]) == ["depot", "s2:green", "depot"]
    assert solution.totals.distance_m == 2000
    assert solution.totals.duration_min == 60
    assert solution.totals.collected_volume_litres == 600
    assert solution.totals.stops_served == 2


# ---------------------------------------------------------------------------
# Fleet exhaustion -> remaining stops unserved with a reason
# ---------------------------------------------------------------------------


def test_fleet_exhaustion_leaves_remaining_unserved() -> None:
    # One vehicle, max_shift 30: it serves s1 only; s2 triggers the shift hand
    # over, but no second vehicle exists -> s2 and s3 stay unserved.
    stops = [
        make_stop("s1", "brown", 100.0, volume_litres=300),
        make_stop("s2", "green", 100.0, volume_litres=300),
        make_stop("s3", "white", 100.0, volume_litres=300),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("depot", "s2"): (500, 10),
        pk("depot", "s3"): (500, 10),
        pk("s1", "s2"): (1500, 30),
        pk("s1", "s3"): (1500, 30),
        pk("s2", "s3"): (1500, 30),
        pk("depot", "disposal"): (800, 16),
        pk("s1", "disposal"): (900, 18),
        pk("s2", "disposal"): (900, 18),
        pk("s3", "disposal"): (900, 18),
    }
    problem = make_problem(
        stops,
        ["depot", "disposal", "s1", "s2", "s3"],
        pairs,
        max_shift_minutes=30,
        count_available=1,
    )
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "incomplete"
    assert len(solution.routes) == 1
    assert solution.totals.stops_served == 1
    assert solution.totals.stops_total == 3
    assert [entry.stop_key for entry in solution.unserved] == [
        ("s2", "green"),
        ("s3", "white"),
    ]
    assert all("fleet_exhausted" in entry.reason for entry in solution.unserved)
    assert all("1 vehicles" in entry.reason for entry in solution.unserved)


# ---------------------------------------------------------------------------
# Zero-fill stop (no persistence value) is still visited, collects 0 L / 0 kg
# ---------------------------------------------------------------------------


def test_zero_fill_stop_still_visited_and_labelled() -> None:
    stops = [
        make_stop("loc-a", "brown", 0.0),
        make_stop("loc-b", "green", 100.0),
    ]
    pairs: MatrixPairs = {
        pk("depot", "loc-a"): (500, 10),
        pk("loc-a", "loc-b"): (500, 10),
        pk("loc-b", "depot"): (500, 10),
        pk("depot", "disposal"): (800, 16),
        pk("loc-a", "disposal"): (900, 18),
        pk("loc-b", "disposal"): (900, 18),
    }
    problem = make_problem(stops, ["depot", "disposal", "loc-a", "loc-b"], pairs)
    solution = naive_fixed_order_simulation(problem, no_forecast_stop_keys=[("loc-a", "brown")])

    assert solution.status == "complete"
    assert len(solution.routes) == 1
    route = solution.routes[0]
    assert sequence_ids(route) == ["depot", "loc-a:brown", "loc-b:green", "depot"]
    # The zero-fill stop is visited (travel + service) but collects nothing.
    assert route.load_progression == [(0, 0), (600, 300)]
    assert solution.totals.collected_volume_litres == 600
    assert solution.totals.collected_weight_kg == 300
    assert solution.totals.stops_served == 2
    assert solution.no_forecast_stop_keys == [("loc-a", "brown")]
    assert solution.unserved == []


# ---------------------------------------------------------------------------
# Served + unserved reconciles to stops_total (contract §4.4)
# ---------------------------------------------------------------------------


def test_served_plus_unserved_reconciles() -> None:
    stops = [
        make_stop("s1", "brown", 100.0, volume_litres=300),
        make_stop("s2", "green", 100.0, volume_litres=300),
        make_stop("s3", "white", 100.0, volume_litres=300),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("depot", "s2"): (500, 10),
        pk("depot", "s3"): (500, 10),
        pk("s1", "s2"): (1500, 30),
        pk("s1", "s3"): (1500, 30),
        pk("s2", "s3"): (1500, 30),
        pk("depot", "disposal"): (800, 16),
    }
    problem = make_problem(
        stops,
        ["depot", "disposal", "s1", "s2", "s3"],
        pairs,
        max_shift_minutes=30,
        count_available=1,
    )
    solution = naive_fixed_order_simulation(problem)

    assert solution.totals.stops_served + len(solution.unserved) == (solution.totals.stops_total)
    served_keys = {
        (node.location_id, node.material_type)
        for route in solution.routes
        for node in route.sequence
        if isinstance(node, Stop)
    }
    unserved_keys = {entry.stop_key for entry in solution.unserved}
    assert served_keys | unserved_keys == {
        ("s1", "brown"),
        ("s2", "green"),
        ("s3", "white"),
    }
    assert not served_keys & unserved_keys  # exactly once (§4.4)


# ---------------------------------------------------------------------------
# Capacity holds at every load-progression point (contract §4.4)
# ---------------------------------------------------------------------------


def test_load_within_capacity_at_every_step() -> None:
    # Five stops (collected 600/540/480/420/360 L, cap 1000 L): hand-checked
    # unloads before s2, s3 and s5; s4 fits on top of s3 (900 L).
    fills = [100.0, 90.0, 80.0, 70.0, 60.0]
    stops = [make_stop(f"s{i}", "brown", fill) for i, fill in enumerate(fills, start=1)]
    point_ids = ["depot", "disposal", *(f"s{i}" for i in range(1, 6))]
    pairs: MatrixPairs = {pk("depot", "disposal"): (500, 10)}
    for i in range(1, 6):
        pairs[pk("depot", f"s{i}")] = (500, 10)
        pairs[pk("disposal", f"s{i}")] = (500, 10)
    for i in range(1, 6):
        for j in range(i + 1, 6):
            pairs[pk(f"s{i}", f"s{j}")] = (500, 10)
    problem = make_problem(stops, point_ids, pairs, count_available=1)
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "complete"
    assert solution.shift_violations == []
    assert len(solution.routes) == 1
    progression = solution.routes[0].load_progression
    assert progression == [(600, 300), (540, 270), (480, 240), (900, 450), (360, 180)]
    assert all(volume <= 1000 for volume, _weight in progression)
    assert all(weight <= 600 for _volume, weight in progression)
    sequence = sequence_ids(solution.routes[0])
    assert sequence.count("disposal") == 3


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_determinism_same_solution_twice() -> None:
    stops = [
        make_stop("s1", "brown", 100.0),
        make_stop("s2", "green", 100.0),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("s1", "disposal"): (500, 10),
        pk("disposal", "s2"): (500, 10),
        pk("depot", "disposal"): (750, 15),
        pk("depot", "s2"): (1000, 20),
        pk("s1", "s2"): (1000, 20),
    }
    problem = make_problem(stops, ["depot", "disposal", "s1", "s2"], pairs)
    first = naive_fixed_order_simulation(problem)
    second = naive_fixed_order_simulation(problem)
    assert first == second


# ---------------------------------------------------------------------------
# A stop bigger than any vehicle is unserved, never visited
# ---------------------------------------------------------------------------


def test_volume_oversize_stop_unserved_not_visited() -> None:
    stops = [make_stop("s1", "brown", 100.0, volume_litres=1200)]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("depot", "disposal"): (800, 16),
        pk("s1", "disposal"): (900, 18),
    }
    problem = make_problem(stops, ["depot", "disposal", "s1"], pairs)
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "incomplete"
    assert solution.routes == []
    assert solution.totals.stops_served == 0
    assert solution.totals.collected_volume_litres == 0
    assert len(solution.unserved) == 1
    assert solution.unserved[0].stop_key == ("s1", "brown")
    assert "collected volume 1200 L exceeds" in solution.unserved[0].reason
    assert solution.totals.stops_served + len(solution.unserved) == 1


def test_weight_oversize_stop_unserved() -> None:
    # 1200 L x 0.5 kg/l = 600 kg > 500 kg weight cap (volume cap 2000 L holds).
    stops = [make_stop("s1", "brown", 100.0, volume_litres=1200)]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (500, 10),
        pk("depot", "disposal"): (800, 16),
        pk("s1", "disposal"): (900, 18),
    }
    problem = make_problem(
        stops,
        ["depot", "disposal", "s1"],
        pairs,
        volume_capacity_litres=2000,
        weight_capacity_kg=500,
    )
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "incomplete"
    assert solution.routes == []
    assert "collected weight 600 kg exceeds" in solution.unserved[0].reason


# ---------------------------------------------------------------------------
# Shift overrun through the mandatory return leg is reported (§4.4)
# ---------------------------------------------------------------------------


def test_return_leg_overrun_reported() -> None:
    # max_shift 45: s1 fits (20+10=30). s2 would need 20+10=30 -> 30+30 > 45,
    # so vehicle 0 returns home: duration 20+10+20 = 50 > 45 -> reported.
    # Vehicle 1 then serves s2 and its return leg also lands on 50 > 45.
    stops = [
        make_stop("s1", "brown", 100.0, volume_litres=300),
        make_stop("s2", "green", 100.0, volume_litres=300),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s1"): (1000, 20),
        pk("depot", "s2"): (1000, 20),
        pk("s1", "s2"): (1000, 20),
        pk("depot", "disposal"): (800, 16),
        pk("s1", "disposal"): (900, 18),
        pk("s2", "disposal"): (900, 18),
    }
    problem = make_problem(
        stops,
        ["depot", "disposal", "s1", "s2"],
        pairs,
        max_shift_minutes=45,
    )
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "complete"  # nothing unserved...
    assert len(solution.shift_violations) == 2  # ...but both overruns reported
    assert [route.duration_minutes for route in solution.routes] == [50, 50]
    assert all("exceeds max_shift_minutes 45 min by 5 min" in v for v in solution.shift_violations)


# ---------------------------------------------------------------------------
# Nearest disposal, ties broken by site id
# ---------------------------------------------------------------------------


def test_nearest_disposal_tie_broken_by_id() -> None:
    stops = [
        make_stop("s0", "brown", 100.0),
        make_stop("s1", "green", 100.0),
    ]
    pairs: MatrixPairs = {
        pk("depot", "s0"): (500, 10),
        pk("depot", "s1"): (1200, 24),
        pk("s0", "s1"): (1200, 24),
        pk("depot", "site-a"): (800, 16),
        pk("depot", "site-b"): (800, 16),
        pk("s0", "site-a"): (500, 10),
        pk("s0", "site-b"): (500, 10),  # tie with site-a from s0
        pk("site-a", "s1"): (500, 10),
        pk("site-b", "s1"): (500, 10),
        pk("site-a", "site-b"): (200, 4),
    }
    problem = make_problem(
        stops,
        ["depot", "site-a", "site-b", "s0", "s1"],
        pairs,
        disposal_sites=(SITE_A, SITE_B),
        count_available=1,
    )
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "complete"
    sequence = sequence_ids(solution.routes[0])
    assert "site-a" in sequence  # deterministic tie-break by site id
    assert "site-b" not in sequence


# ---------------------------------------------------------------------------
# Empty problem and fleet recommendation shape
# ---------------------------------------------------------------------------


def test_empty_problem_completes_with_zero_totals() -> None:
    problem = make_problem([], ["depot", "disposal"], {pk("depot", "disposal"): (800, 16)})
    solution = naive_fixed_order_simulation(problem)

    assert solution.status == "complete"
    assert solution.routes == []
    assert solution.unserved == []
    assert solution.totals.distance_m == 0
    assert solution.totals.stops_total == 0
    assert solution.fleet_recommendation.count == 0
    assert solution.fleet_recommendation.basis.ceil_by_volume == 0
    assert solution.fleet_recommendation.basis.ceil_by_weight == 0
    assert isinstance(solution.fleet_recommendation, FleetRecommendation)
    assert solution.no_forecast_stop_keys == []


# ---------------------------------------------------------------------------
# §4.7 area-sweep order (v2): row-major cells, lexicographic within a cell
# ---------------------------------------------------------------------------


def test_sweep_order_visits_cells_row_major_not_by_lon() -> None:
    # stopA sits in cell (0, 1) — lower lat band; stopB in (1, 0). Row-major
    # (lat band ascending, then lon ascending) visits stopA first even though
    # stopB has the smaller longitude.
    stop_a = make_stop("s-a", "brown", 10.0, lat=0.005, lon=0.015)  # cell (0, 1)
    stop_b = make_stop("s-b", "brown", 10.0, lat=0.015, lon=0.005)  # cell (1, 0)
    assert sweep_visit_order([stop_b, stop_a]) == [stop_a, stop_b]


def test_sweep_order_is_lexicographic_within_one_cell() -> None:
    # All three stops share cell (0, 0); inserted deliberately out of order.
    stops = [
        make_stop("s3", "brown", 10.0, lat=0.009, lon=0.005),
        make_stop("s1", "brown", 10.0, lat=0.002, lon=0.003),
        make_stop("s2", "green", 10.0, lat=0.007, lon=0.001),
    ]
    ordered = sweep_visit_order(stops)
    assert [(s.location_id, s.material_type) for s in ordered] == [
        ("s1", "brown"),
        ("s2", "green"),
        ("s3", "brown"),
    ]


def test_sweep_simulation_uses_sweep_order_and_method_label() -> None:
    # Three stops in three distinct cells; empty matrix pairs -> an all-zero
    # matrix (every cell defaults to 0, symmetric, zero diagonal). Fills are
    # tiny so one truck serves all stops in a single in-shift route.
    stops = [
        make_stop("s-b", "brown", 10.0, lat=0.015, lon=0.005),  # cell (1, 0)
        make_stop("s-a", "green", 10.0, lat=0.005, lon=0.015),  # cell (0, 1)
        make_stop("s-c", "white", 10.0, lat=0.006, lon=0.003),  # cell (0, 0)
    ]
    problem = make_problem(
        stops,
        ["depot", "disposal"] + [s.location_id for s in stops],
        {},  # all-zero distances/durations: order is simulated, not optimised
    )
    solution = naive_sweep_simulation(problem)

    assert solution.method == METHOD_NAIVE_SWEEP_ORDER
    assert solution.method == "naive_sweep_order"
    assert solution.status == "complete"
    assert solution.unserved == []
    visited = [
        node_id
        for node_id in sequence_ids(solution.routes[0])
        if node_id not in ("depot", "disposal")
    ]
    expected = [stop_point_id(s) for s in sweep_visit_order(problem.stops)]
    assert visited == expected
    assert [s.location_id for s in sweep_visit_order(problem.stops)] == [
        "s-c",
        "s-a",
        "s-b",
    ]  # row-major: (0,0) -> (0,1) -> (1,0)
