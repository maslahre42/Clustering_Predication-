"""Fleet recommendation tests — docs/contracts.md §4.3/§4.4 (brief §4: fleet
size from total weight and volume).

All capacities/totals in the fixtures are hand-picked [demo assumption] test
values; the pinning asserts the ceil math, not any real-world fleet.
"""

from __future__ import annotations

import pytest

from src.data.schema import MaterialType
from src.routing.demo_config import (
    DEMO_VEHICLE_ID,
    DEMO_VEHICLE_VOLUME_CAPACITY_LITRES,
    DEMO_VEHICLE_WEIGHT_CAPACITY_KG,
    demo_routing_config,
)
from src.routing.fleet import (
    FleetBasis,
    FleetRecommendation,
    fleet_recommendation,
    recommend_fleet_for_problem,
)
from src.routing.geography import build_travel_matrix, synthetic_stop_coordinates
from src.routing.schemas import (
    Depot,
    DisposalSite,
    RoutingSchemaError,
    Stop,
    VehicleType,
)

DEPOT = Depot(id="depot", name="Test Depot", lat=49.15, lon=9.22)
DISPOSAL = DisposalSite(
    id="disposal", name="Test Disposal", lat=49.17, lon=9.26, service_minutes=30
)


def make_vehicle_type(
    volume_capacity_litres: int = DEMO_VEHICLE_VOLUME_CAPACITY_LITRES,
    weight_capacity_kg: int = DEMO_VEHICLE_WEIGHT_CAPACITY_KG,
    vehicle_id: str = DEMO_VEHICLE_ID,
) -> VehicleType:
    return VehicleType(
        id=vehicle_id,
        name="Test Truck",
        volume_capacity_litres=volume_capacity_litres,
        weight_capacity_kg=weight_capacity_kg,
        count_available=3,
    )


# ---------------------------------------------------------------------------
# fleet_recommendation — the §4.4 ceil math
# ---------------------------------------------------------------------------


def test_volume_requires_two_vehicles_weight_only_one() -> None:
    vehicle = make_vehicle_type(volume_capacity_litres=12_000, weight_capacity_kg=10_000)
    recommendation = fleet_recommendation(24_000, 5_000, vehicle)
    assert recommendation == FleetRecommendation(
        vehicle_type_id=DEMO_VEHICLE_ID,
        count=2,
        basis=FleetBasis(ceil_by_volume=2, ceil_by_weight=1),
    )


def test_weight_requires_two_vehicles_volume_only_one() -> None:
    vehicle = make_vehicle_type(volume_capacity_litres=12_000, weight_capacity_kg=10_000)
    recommendation = fleet_recommendation(6_000, 15_000, vehicle)
    assert recommendation.count == 2
    assert recommendation.basis == FleetBasis(ceil_by_volume=1, ceil_by_weight=2)


def test_exact_multiples_do_not_round_up() -> None:
    vehicle = make_vehicle_type(volume_capacity_litres=12_000, weight_capacity_kg=10_000)
    recommendation = fleet_recommendation(12_000, 10_000, vehicle)
    assert recommendation.count == 1
    assert recommendation.basis == FleetBasis(ceil_by_volume=1, ceil_by_weight=1)


def test_ceil_rounds_up_partial_load() -> None:
    vehicle = make_vehicle_type(volume_capacity_litres=12_000, weight_capacity_kg=10_000)
    recommendation = fleet_recommendation(24_001, 10_001, vehicle)
    assert recommendation.basis == FleetBasis(ceil_by_volume=3, ceil_by_weight=2)
    assert recommendation.count == 3


def test_zero_totals_recommend_zero_vehicles() -> None:
    vehicle = make_vehicle_type()
    recommendation = fleet_recommendation(0, 0, vehicle)
    assert recommendation.count == 0
    assert recommendation.basis == FleetBasis(ceil_by_volume=0, ceil_by_weight=0)


@pytest.mark.parametrize(
    ("volume", "weight"),
    [(-1, 0), (0, -1), (1.5, 0), (0, True), (False, 0), (1_000.0, 10)],
)
def test_invalid_totals_raise(volume: int, weight: int) -> None:
    with pytest.raises(RoutingSchemaError):
        fleet_recommendation(volume, weight, make_vehicle_type())


# ---------------------------------------------------------------------------
# recommend_fleet_for_problem — totals over all stops (full demand)
# ---------------------------------------------------------------------------


def _make_problem(stops: list[Stop], vehicles: list[VehicleType]):
    from src.routing.schemas import RoutingProblem

    config = demo_routing_config()
    travel = build_travel_matrix(DEPOT, [DISPOSAL], stops, config)
    return RoutingProblem(
        depot=DEPOT,
        disposal_sites=[DISPOSAL],
        stops=stops,
        vehicle_types=vehicles,
        travel=travel,
        config=config,
    )


def _make_stop(location_id: str, fill_pct: float, material: MaterialType = "green") -> Stop:
    coordinates = synthetic_stop_coordinates([(location_id, material)], DEPOT)
    lat, lon = coordinates[(location_id, material)]
    return Stop(
        location_id=location_id,
        material_type=material,
        lat=lat,
        lon=lon,
        container_volume_litres=1900,
        predicted_fill_pct=fill_pct,
        service_minutes=10,
    )


def test_recommend_fleet_for_problem_sums_all_stops_with_density() -> None:
    # 3 stops x round(1900 * 90 / 100) = 1710 L -> 5130 L; density 0.5 -> 2565 kg.
    stops = [_make_stop("loc-1", 90.0), _make_stop("loc-2", 90.0), _make_stop("loc-3", 90.0)]
    problem = _make_problem(stops, [make_vehicle_type()])
    recommendation = recommend_fleet_for_problem(problem)
    assert recommendation.vehicle_type_id == DEMO_VEHICLE_ID
    assert recommendation.basis == FleetBasis(ceil_by_volume=1, ceil_by_weight=1)
    assert recommendation.count == 1


def test_recommend_fleet_for_problem_counts_unserved_demand_too() -> None:
    # Two full containers: 3800 L / 1900 kg vs one 2000 L / 1000 kg truck
    # -> fleet recommendation must exceed the single available unit.
    stops = [_make_stop("loc-1", 100.0), _make_stop("loc-2", 100.0)]
    vehicle = VehicleType(
        id="small_truck",
        name="Small Truck",
        volume_capacity_litres=2_000,
        weight_capacity_kg=1_000,
        count_available=1,
    )
    problem = _make_problem(stops, [vehicle])
    recommendation = recommend_fleet_for_problem(problem)
    assert recommendation.vehicle_type_id == "small_truck"
    assert recommendation.basis == FleetBasis(ceil_by_volume=2, ceil_by_weight=2)
    assert recommendation.count == 2  # required, even though only 1 is available


def test_recommend_fleet_for_problem_picks_type_with_min_count_tie_by_id() -> None:
    stops = [_make_stop("loc-1", 100.0)]
    big = VehicleType(
        id="zz_big",
        name="Big",
        volume_capacity_litres=4_000,
        weight_capacity_kg=4_000,
        count_available=2,
    )
    small = VehicleType(
        id="aa_small",
        name="Small",
        volume_capacity_litres=2_000,
        weight_capacity_kg=1_000,
        count_available=2,
    )
    problem = _make_problem(stops, [big, small])
    recommendation = recommend_fleet_for_problem(problem)
    # big: ceil(1900/4000)=1, ceil(950/4000)=1 -> 1; small: ceil(1900/2000)=1,
    # ceil(950/1000)=1 -> 1; tie broken by vehicle type id ascending.
    assert recommendation.vehicle_type_id == "aa_small"
    assert recommendation.count == 1


def test_recommend_fleet_for_problem_ties_in_count_choose_faster_type() -> None:
    stops = [_make_stop("loc-1", 100.0), _make_stop("loc-2", 100.0)]
    first = VehicleType(
        id="a_type",
        name="A",
        volume_capacity_litres=2_000,
        weight_capacity_kg=2_000,
        count_available=1,
    )
    second = VehicleType(
        id="b_type",
        name="B",
        volume_capacity_litres=1_900,
        weight_capacity_kg=2_000,
        count_available=1,
    )
    problem = _make_problem(stops, [second, first])
    recommendation = recommend_fleet_for_problem(problem)
    # a_type: ceil(3800/2000)=2; b_type: ceil(3800/1900)=2 -> tie -> id ascending.
    assert recommendation.vehicle_type_id == "a_type"
    assert recommendation.count == 2
