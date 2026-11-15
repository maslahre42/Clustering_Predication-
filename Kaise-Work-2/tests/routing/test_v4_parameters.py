"""v4 parameter tests — docs/contracts.md §4.2/§4.3/§4.4/§4.6/§4.7 (2026-11-14).

Covers the v4 additions only:
- ``containers_per_series`` multiplier (litres collected AND stop service
  minutes scale; predicted fill % unchanged) — §4.2 v4 [demo assumption Q11];
- density default 0.40 kg/L uniform [literature AVV 20 01 02] — kg totals
  drop 20 % vs the previous 0.5 while ``ceil_by_volume`` stays binding;
- flat-mode arithmetic anchor §4.4: 5 min service + 10 min per leg ⇒
  ⌊480/15⌋ = 32 stops/shift, made visible by ``totals.stops_per_shift``;
- ``naive_fixed_frequency`` due-set (§4.7 v4) incl. boundary and no-last-date;
- §4.3 v4 totals ``shift_minutes_used``/``stops_per_shift`` on solver and
  naive solutions (and the empty problem).

All fixtures are hand-built (no CSV); every number below is [demo assumption]
test arithmetic, never a real-world claim.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import TypeAlias

import pytest

from src.data.schema import MaterialType
from src.routing.fleet import fleet_recommendation
from src.routing.naive import (
    METHOD_NAIVE_FIXED_FREQUENCY,
    NaiveRoute,
    due_series_keys,
    naive_fixed_frequency_simulation,
    sweep_visit_order,
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
    effective_collected_volume_litres,
    effective_collected_weight_kg,
    effective_service_minutes,
    stop_point_id,
)
from src.routing.solver import Route, solve

DEPOT = Depot(id="depot", name="Test Depot", lat=49.15, lon=9.22)
DISPOSAL = DisposalSite(
    id="disposal", name="Test Disposal", lat=49.17, lon=9.26, service_minutes=30
)

PairKey: TypeAlias = tuple[str, str]
MatrixPairs: TypeAlias = dict[PairKey, tuple[int, int]]  # (distance_m, duration_min)


def make_config(
    max_shift_minutes: int = 480,
    containers_per_series: int = 1,
    densities_kg_per_litre: dict[MaterialType, float] | None = None,
) -> RoutingConfig:
    return RoutingConfig(
        max_shift_minutes=max_shift_minutes,
        densities_kg_per_litre=densities_kg_per_litre or {"brown": 0.5, "green": 0.5, "white": 0.5},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
        solver_solution_limit=8,
        solver_time_limit_s=1.0,
        containers_per_series=containers_per_series,
    )


def make_stop(
    location_id: str,
    material_type: MaterialType = "brown",
    fill_pct: float = 50.0,
    volume_litres: int = 600,
    service_minutes: int = 10,
) -> Stop:
    return Stop(
        location_id=location_id,
        material_type=material_type,
        lat=49.14,
        lon=9.20,
        container_volume_litres=volume_litres,
        predicted_fill_pct=fill_pct,
        service_minutes=service_minutes,
    )


def flat_matrix(point_ids: Sequence[str]) -> TravelMatrix:
    """Flat-mode §4.4 matrix: EVERY off-diagonal leg costs the same (10 m,
    10 min), so duration is a function of stop count only."""
    n = len(point_ids)
    return TravelMatrix(
        point_ids=list(point_ids),
        distance_m=[[0 if i == j else 10 for j in range(n)] for i in range(n)],
        duration_min=[[0 if i == j else 10 for j in range(n)] for i in range(n)],
        provenance="haversine_straight_line_derived",
    )


def make_problem(
    stops: Sequence[Stop],
    *,
    config: RoutingConfig | None = None,
    volume_capacity_litres: int = 12_000,
    weight_capacity_kg: int = 10_000,
    count_available: int = 2,
) -> RoutingProblem:
    point_ids = [DEPOT.id, DISPOSAL.id, *(stop_point_id(stop) for stop in stops)]
    return RoutingProblem(
        depot=DEPOT,
        disposal_sites=[DISPOSAL],
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
        travel=flat_matrix(point_ids),
        config=config or make_config(),
    )


def route_stops(route: NaiveRoute | Route) -> list[Stop]:
    return [node for node in route.sequence if isinstance(node, Stop)]


# ---------------------------------------------------------------------------
# §4.2 v4 multiplier: volume + service minutes scale, fill % unchanged
# ---------------------------------------------------------------------------


def test_multiplier_scales_volume_weight_and_service_but_not_fill() -> None:
    stop = make_stop("loc-a", fill_pct=50.0, volume_litres=600, service_minutes=10)
    base = make_config(containers_per_series=1)
    tripled = make_config(containers_per_series=3)

    # Fill % is the series aggregate — the Stop itself never changes (§4.2 v4).
    assert stop.predicted_fill_pct == 50.0
    assert stop.collected_volume_litres == 300
    assert effective_collected_volume_litres(stop, tripled) == 3 * 300
    assert effective_collected_weight_kg(stop, tripled) == round(900 * 0.5)
    assert effective_service_minutes(stop, tripled) == 30
    # Default multiplier 1 keeps every quantity at the per-container value.
    assert effective_collected_volume_litres(stop, base) == 300
    assert effective_collected_weight_kg(stop, base) == 150
    assert effective_service_minutes(stop, base) == 10


def test_multiplier_scales_naive_simulation_quantities() -> None:
    """Same single-stop problem, containers_per_series 1 vs 2: the stop
    collects and takes twice as long; depot/stop/depot legs are unchanged."""
    single = make_problem([make_stop("loc-a")], count_available=1)
    doubled_config = make_config(containers_per_series=2)
    doubled = make_problem(
        [make_stop("loc-a")],
        config=doubled_config,
        count_available=1,
    )

    base_solution = naive_fixed_frequency_simulation(
        single, {(("loc-a", "brown")): None}, date(2026, 9, 30)
    )
    doubled_solution = naive_fixed_frequency_simulation(
        doubled, {("loc-a", "brown"): None}, date(2026, 9, 30)
    )

    assert base_solution.totals.collected_volume_litres == 300
    assert doubled_solution.totals.collected_volume_litres == 600
    assert base_solution.totals.collected_weight_kg == 150
    assert doubled_solution.totals.collected_weight_kg == 300
    # duration = depot->stop (10) + service (10 vs 20) + stop->depot (10).
    assert base_solution.routes[0].duration_minutes == 30
    assert doubled_solution.routes[0].duration_minutes == 40


# ---------------------------------------------------------------------------
# §4.6 v4 density 0.40: kg totals drop 20 %, volume ceil stays binding
# ---------------------------------------------------------------------------


def test_density_040_drops_weight_20pct_and_volume_ceil_stays_binding() -> None:
    truck = VehicleType(
        id="truck",
        name="Test Truck",
        volume_capacity_litres=12_000,
        weight_capacity_kg=10_000,
        count_available=1,
    )
    volume_litres = 24_000  # two full truckloads by volume
    weight_at_05 = 12_000  # 0.5 kg/L: two truckloads by weight too
    weight_at_04 = round(volume_litres * 0.4)  # 9,600 kg

    assert weight_at_04 == round(0.8 * weight_at_05)  # exactly 20 % lighter

    rec_05 = fleet_recommendation(volume_litres, weight_at_05, truck)
    rec_04 = fleet_recommendation(volume_litres, weight_at_04, truck)

    assert rec_05.basis.ceil_by_volume == rec_04.basis.ceil_by_volume == 2
    assert rec_05.basis.ceil_by_weight == 2
    assert rec_04.basis.ceil_by_weight == 1  # weight no longer co-binds
    assert rec_05.count == rec_04.count == 2  # fleet size unchanged: volume binds


# ---------------------------------------------------------------------------
# §4.4 flat-mode anchor: ⌊480/15⌋ = 32 stops/shift
# ---------------------------------------------------------------------------


def _anchor_stops(count: int) -> list[Stop]:
    materials: tuple[MaterialType, ...] = ("brown", "green", "white")
    return [
        make_stop(
            f"loc-{index:03d}",
            material_type=materials[index % 3],
            fill_pct=1.0,  # 6 L / 3 kg per stop: no disposal detours, pure anchor
            volume_litres=600,
            service_minutes=5,
        )
        for index in range(count)
    ]


def test_naive_flat_mode_anchor_32_stops_per_shift() -> None:
    """64 stops, 10-min legs, 5-min service, 480-min shift, 2 vehicles:
    each vehicle serves exactly ⌊480/15⌋ = 32 stops (the return-to-depot leg
    pushes the route to 490 min — a §4.4 reported shift violation, never
    hidden) and totals.stops_per_shift == 32.0."""
    stops = _anchor_stops(64)
    problem = make_problem(stops, count_available=2)
    solution = naive_fixed_frequency_simulation(
        problem,
        {(stop.location_id, stop.material_type): None for stop in stops},
        date(2026, 9, 30),
    )

    assert solution.totals.stops_served == 64
    assert len(solution.routes) == 2
    assert all(len(route_stops(route)) == 32 for route in solution.routes)
    assert solution.totals.stops_per_shift == 32.0
    assert solution.totals.shift_minutes_used == 490  # 32 x 15 + 10 return leg
    assert len(solution.shift_violations) == 2  # both return legs overran


def test_solver_flat_mode_respects_shift_and_reports_derived_totals() -> None:
    """Solver path: post-hoc §4.4 truncation must keep every route <= 480 min
    INCLUDING the return leg (<= 31 stops per route here, vs the naive 32),
    and the §4.3 v4 derived totals must reconcile."""
    stops = _anchor_stops(24)
    problem = make_problem(stops, count_available=1)
    solution = solve(problem)

    assert solution.status in ("optimal", "feasible")
    assert solution.routes
    assert all(route.duration_minutes <= 480 for route in solution.routes)
    assert all(len(route_stops(route)) <= 31 for route in solution.routes)
    assert solution.totals.shift_minutes_used == max(
        route.duration_minutes for route in solution.routes
    )
    assert solution.totals.stops_per_shift == round(
        solution.totals.stops_served / len(solution.routes), 1
    )
    # Every input stop is served or unserved with a reason (§4.4).
    assert solution.totals.stops_served + len(solution.unserved) == solution.totals.stops_total


# ---------------------------------------------------------------------------
# §4.7 v4 due-set + naive_fixed_frequency scenario
# ---------------------------------------------------------------------------

AS_OF = date(2026, 9, 30)


def test_due_series_keys_boundary_and_gaps() -> None:
    last_dates: dict[tuple[str, MaterialType], date | None] = {
        ("due-exactly-28", "brown"): date(2026, 9, 2),  # gap == 28 ⇒ due (>=)
        ("not-due-27", "brown"): date(2026, 9, 3),  # gap 27 ⇒ not due
        ("no-last-date", "brown"): None,  # never emptied ⇒ due
        ("future-date", "brown"): date(2026, 10, 1),  # negative gap ⇒ not due
    }
    due = due_series_keys(last_dates, AS_OF, frequency_days=28)
    assert due == {("due-exactly-28", "brown"), ("no-last-date", "brown")}

    # Smaller cycle pulls the 27-day series in as well.
    assert ("not-due-27", "brown") in due_series_keys(last_dates, AS_OF, frequency_days=27)


def test_due_series_keys_rejects_invalid_frequency() -> None:
    for bad in (0, -28):
        with pytest.raises(ValueError, match="frequency_days"):
            due_series_keys({}, AS_OF, frequency_days=bad)


def test_naive_fixed_frequency_visits_only_due_stops_in_sweep_order() -> None:
    due_stop = make_stop("loc-due")
    not_due_stop = make_stop("loc-fresh")
    missing_entry_stop = make_stop("loc-unknown")
    stops = [not_due_stop, missing_entry_stop, due_stop]
    problem = make_problem(stops, count_available=3)
    last_dates: dict[tuple[str, MaterialType], date | None] = {
        ("loc-due", "brown"): date(2026, 9, 2),  # gap 28 ⇒ due
        ("loc-fresh", "brown"): date(2026, 9, 25),  # gap 5 ⇒ not due
        # loc-unknown absent ⇒ due (never collected)
    }

    solution = naive_fixed_frequency_simulation(problem, last_dates, AS_OF)

    assert solution.method == METHOD_NAIVE_FIXED_FREQUENCY
    assert solution.status == "complete"
    assert solution.totals.stops_total == 2
    assert solution.totals.stops_served == 2
    assert solution.unserved == []
    served_ids = [stop.location_id for route in solution.routes for stop in route_stops(route)]
    expected_order = [
        stop.location_id for stop in sweep_visit_order([due_stop, missing_entry_stop])
    ]
    assert served_ids == expected_order
    # config default cycle (28) equals the explicit argument here.
    assert problem.config.frequency_days == 28


# ---------------------------------------------------------------------------
# §4.3 v4 totals on both solution paths + empty problem
# ---------------------------------------------------------------------------


def test_naive_totals_derived_fields_reconcile() -> None:
    stops = _anchor_stops(40)
    problem = make_problem(stops, count_available=2)
    solution = naive_fixed_frequency_simulation(
        problem,
        {(stop.location_id, stop.material_type): None for stop in stops},
        AS_OF,
    )

    assert solution.totals.shift_minutes_used == max(
        route.duration_minutes for route in solution.routes
    )
    assert solution.totals.stops_per_shift == round(
        solution.totals.stops_served / len(solution.routes), 1
    )


def test_solver_empty_problem_totals_are_zero() -> None:
    problem = make_problem([], count_available=1)
    solution = solve(problem)
    assert solution.status == "optimal"
    assert solution.totals.shift_minutes_used == 0
    assert solution.totals.stops_per_shift == 0.0


def test_routing_config_defaults_are_v4() -> None:
    """§4.2 v4 defaults, independent of the demo config module."""
    config = RoutingConfig(
        max_shift_minutes=480,
        densities_kg_per_litre={"brown": 0.4, "green": 0.4, "white": 0.4},
        detour_factor=1.4,
        avg_speed_kmh=30.0,
    )
    assert config.containers_per_series == 1
    assert config.frequency_days == 28
    with pytest.raises(RoutingSchemaError, match="containers_per_series"):
        RoutingConfig(
            max_shift_minutes=480,
            densities_kg_per_litre={"brown": 0.4, "green": 0.4, "white": 0.4},
            detour_factor=1.4,
            avg_speed_kmh=30.0,
            containers_per_series=0,
        )
