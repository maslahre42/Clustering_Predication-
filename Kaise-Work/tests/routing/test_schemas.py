"""Routing input schema tests — docs/contracts.md §4.1/§4.2/§4.4.

All coordinates and ids used here are synthetic demo fixtures (contract §4.5:
no real coordinates exist in the data) and are never presented as road
distance — provenance strings are pinned in tests.
"""

from __future__ import annotations

import pytest

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

DEPOT = Depot(id="depot_1", name="Depot One", lat=49.15, lon=9.22)
DISPOSAL = DisposalSite(
    id="disposal_1", name="Disposal One", lat=49.17, lon=9.26, service_minutes=30
)
STOP = Stop(
    location_id="loc-1",
    material_type="brown",
    lat=49.16,
    lon=9.23,
    container_volume_litres=1900,
    predicted_fill_pct=90.0,
    service_minutes=10,
)
VEHICLE = VehicleType(
    id="truck_1",
    name="Truck One",
    volume_capacity_litres=12000,
    weight_capacity_kg=10000,
    count_available=3,
)
CONFIG = RoutingConfig(
    max_shift_minutes=480,
    densities_kg_per_litre={"brown": 0.5, "green": 0.5, "white": 0.5},
    detour_factor=1.4,
    avg_speed_kmh=30.0,
    solver_time_limit_s=30.0,
)


def identity_matrix(point_ids: list[str]) -> TravelMatrix:
    n = len(point_ids)
    return TravelMatrix(
        point_ids=point_ids,
        distance_m=[[0] * n for _ in range(n)],
        duration_min=[[0] * n for _ in range(n)],
        provenance="haversine_straight_line_derived",
    )


# ---------------------------------------------------------------------------
# Valid construction
# ---------------------------------------------------------------------------


def test_stop_holds_contract_fields() -> None:
    stop = Stop(
        location_id="loc-2",
        material_type="green",
        lat=49.0,
        lon=9.0,
        container_volume_litres=1900,  # [demo assumption] §4.6
        predicted_fill_pct=85.0,
        service_minutes=10,  # [demo assumption] §4.6
    )
    assert stop.location_id == "loc-2"
    assert stop.material_type == "green"
    assert stop.container_volume_litres == 1900
    assert stop.service_minutes == 10


def test_depot_and_disposal_and_vehicle_construct() -> None:
    assert DEPOT.id == "depot_1"
    assert DISPOSAL.service_minutes == 30
    assert VEHICLE.count_available == 3


def test_travel_matrix_valid_square_construction() -> None:
    matrix = identity_matrix(["depot_1", "disposal_1", "loc-1:brown"])
    assert matrix.point_ids == ["depot_1", "disposal_1", "loc-1:brown"]
    assert matrix.provenance == "haversine_straight_line_derived"


def test_routing_problem_valid_construction() -> None:
    problem = RoutingProblem(
        depot=DEPOT,
        disposal_sites=[DISPOSAL],
        stops=[STOP],
        vehicle_types=[VEHICLE],
        travel=identity_matrix(["depot_1", "disposal_1", stop_point_id(STOP)]),
        config=CONFIG,
    )
    assert problem.stops == [STOP]
    assert problem.config.detour_factor == 1.4


# ---------------------------------------------------------------------------
# Stop validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_volume", [0, -1900])
def test_stop_container_volume_must_be_positive_int(bad_volume: int) -> None:
    with pytest.raises(RoutingSchemaError):
        Stop(
            location_id="loc-1",
            material_type="brown",
            lat=49.0,
            lon=9.0,
            container_volume_litres=bad_volume,
            predicted_fill_pct=90.0,
            service_minutes=10,
        )


@pytest.mark.parametrize("bad_value", ["1900", 1900.0, True, None])
def test_stop_container_volume_non_integer_raises(bad_value: object) -> None:
    """bool excluded explicitly (True is an int subclass, not a litre count)."""
    with pytest.raises(RoutingSchemaError):
        Stop(
            location_id="loc-1",
            material_type="brown",
            lat=49.0,
            lon=9.0,
            container_volume_litres=bad_value,  # type: ignore[arg-type]
            predicted_fill_pct=90.0,
            service_minutes=10,
        )


@pytest.mark.parametrize("bad_minutes", [0, -10])
def test_stop_service_minutes_must_be_positive(bad_minutes: int) -> None:
    with pytest.raises(RoutingSchemaError):
        Stop(
            location_id="loc-1",
            material_type="brown",
            lat=49.0,
            lon=9.0,
            container_volume_litres=1900,
            predicted_fill_pct=90.0,
            service_minutes=bad_minutes,
        )


@pytest.mark.parametrize("bad_fill", [-0.1, 100.1])
def test_stop_predicted_fill_must_be_within_0_100(bad_fill: float) -> None:
    with pytest.raises(RoutingSchemaError):
        Stop(
            location_id="loc-1",
            material_type="brown",
            lat=49.0,
            lon=9.0,
            container_volume_litres=1900,
            predicted_fill_pct=bad_fill,
            service_minutes=10,
        )


@pytest.mark.parametrize("bad_lat", [-90.1, 90.1])
@pytest.mark.parametrize("bad_lon", [-180.1, 180.1])
def test_stop_coordinates_out_of_wgs84_range_raise(bad_lat: float, bad_lon: float) -> None:
    with pytest.raises(RoutingSchemaError):
        Stop(
            location_id="loc-1",
            material_type="brown",
            lat=bad_lat,
            lon=bad_lon,
            container_volume_litres=1900,
            predicted_fill_pct=90.0,
            service_minutes=10,
        )


def test_stop_empty_location_id_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        Stop(
            location_id="",
            material_type="brown",
            lat=49.0,
            lon=9.0,
            container_volume_litres=1900,
            predicted_fill_pct=90.0,
            service_minutes=10,
        )


# ---------------------------------------------------------------------------
# Depot / DisposalSite / VehicleType validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_lat", [-90.1, 90.1])
def test_depot_lat_out_of_range_raises(bad_lat: float) -> None:
    with pytest.raises(RoutingSchemaError):
        Depot(id="d", name="n", lat=bad_lat, lon=9.22)


@pytest.mark.parametrize("bad_lon", [-180.1, 180.1])
def test_depot_lon_out_of_range_raises(bad_lon: float) -> None:
    with pytest.raises(RoutingSchemaError):
        Depot(id="d", name="n", lat=49.15, lon=bad_lon)


@pytest.mark.parametrize("bad_minutes", [0, -30])
def test_disposal_service_minutes_must_be_positive(bad_minutes: int) -> None:
    with pytest.raises(RoutingSchemaError):
        DisposalSite(id="x", name="n", lat=49.0, lon=9.0, service_minutes=bad_minutes)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("volume_capacity_litres", 0),
        ("volume_capacity_litres", -1),
        ("weight_capacity_kg", 0),
        ("weight_capacity_kg", -1),
        ("count_available", 0),
    ],
)
def test_vehicle_non_positive_fields_raise(field_name: str, bad_value: int) -> None:
    kwargs: dict[str, object] = {
        "id": "t",
        "name": "n",
        "volume_capacity_litres": 12000,
        "weight_capacity_kg": 10000,
        "count_available": 3,
        field_name: bad_value,
    }
    with pytest.raises(RoutingSchemaError):
        VehicleType(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_count", ["3", 3.0, True])
def test_vehicle_count_must_be_true_int(bad_count: object) -> None:
    with pytest.raises(RoutingSchemaError):
        VehicleType(
            id="t",
            name="n",
            volume_capacity_litres=12000,
            weight_capacity_kg=10000,
            count_available=bad_count,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# RoutingConfig validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_shift", [0, -480])
def test_config_shift_minutes_must_be_positive(bad_shift: int) -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingConfig(
            max_shift_minutes=bad_shift,
            densities_kg_per_litre={"brown": 0.5, "green": 0.5, "white": 0.5},
            detour_factor=1.4,
            avg_speed_kmh=30.0,
            solver_time_limit_s=30.0,
        )


@pytest.mark.parametrize(
    "bad_densities",
    [
        {"brown": 0.5, "green": 0.5},  # missing white
        {"brown": 0.5, "green": 0.5, "white": 0.5, "blue": 0.5},  # unknown material
        {"brown": 0.0, "green": 0.5, "white": 0.5},  # zero density
        {"brown": -0.5, "green": 0.5, "white": 0.5},  # negative density
    ],
)
def test_config_densities_must_cover_all_materials_positive(
    bad_densities: dict[str, float],
) -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingConfig(
            max_shift_minutes=480,
            densities_kg_per_litre=bad_densities,  # type: ignore[arg-type]
            detour_factor=1.4,
            avg_speed_kmh=30.0,
            solver_time_limit_s=30.0,
        )


@pytest.mark.parametrize("bad_detour", [0.9, 0.0, -1.0])
def test_config_detour_factor_must_be_at_least_one(bad_detour: float) -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingConfig(
            max_shift_minutes=480,
            densities_kg_per_litre={"brown": 0.5, "green": 0.5, "white": 0.5},
            detour_factor=bad_detour,
            avg_speed_kmh=30.0,
            solver_time_limit_s=30.0,
        )


@pytest.mark.parametrize("bad_speed", [0.0, -30.0])
def test_config_speed_must_be_positive(bad_speed: float) -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingConfig(
            max_shift_minutes=480,
            densities_kg_per_litre={"brown": 0.5, "green": 0.5, "white": 0.5},
            detour_factor=1.4,
            avg_speed_kmh=bad_speed,
            solver_time_limit_s=30.0,
        )


@pytest.mark.parametrize("bad_limit", [0.0, -5.0])
def test_config_solver_time_limit_must_be_positive(bad_limit: float) -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingConfig(
            max_shift_minutes=480,
            densities_kg_per_litre={"brown": 0.5, "green": 0.5, "white": 0.5},
            detour_factor=1.4,
            avg_speed_kmh=30.0,
            solver_time_limit_s=bad_limit,
        )


# ---------------------------------------------------------------------------
# TravelMatrix validation (contract §4.2: square, consistent, zero diagonal,
# symmetric; provenance never "road")
# ---------------------------------------------------------------------------


def test_matrix_row_length_mismatch_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0, 1, 2], [1, 0, 1]],
            duration_min=[[0, 1], [1, 0]],
            provenance="external",
        )


def test_matrix_non_square_distance_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0, 1], [1, 0], [0, 0]],
            duration_min=[[0, 1], [1, 0]],
            provenance="external",
        )


def test_matrix_duration_row_mismatch_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0, 1], [1, 0]],
            duration_min=[[0, 1, 2], [1, 0]],
            provenance="external",
        )


def test_matrix_dimension_mismatch_with_point_ids_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0]],
            duration_min=[[0]],
            provenance="external",
        )


def test_matrix_nonzero_diagonal_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[5, 1], [1, 0]],
            duration_min=[[0, 1], [1, 0]],
            provenance="external",
        )


def test_matrix_asymmetric_distance_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0, 100], [200, 0]],
            duration_min=[[0, 1], [1, 0]],
            provenance="external",
        )


def test_matrix_asymmetric_duration_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0, 100], [100, 0]],
            duration_min=[[0, 1], [5, 0]],
            provenance="external",
        )


def test_matrix_negative_distance_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a", "b"],
            distance_m=[[0, -1], [-1, 0]],
            duration_min=[[0, 1], [1, 0]],
            provenance="external",
        )


def test_matrix_duplicate_point_ids_raise() -> None:
    with pytest.raises(RoutingSchemaError):
        identity_matrix(["a", "a"])


def test_matrix_empty_point_ids_raise() -> None:
    with pytest.raises(RoutingSchemaError):
        identity_matrix([])


def test_matrix_provenance_must_be_known_value() -> None:
    """Only contract §4.2 provenance values allowed — 'road' is never valid
    because no road data exists [observed, contract §4.5]."""
    with pytest.raises(RoutingSchemaError):
        TravelMatrix(
            point_ids=["a"],
            distance_m=[[0]],
            duration_min=[[0]],
            provenance="road_distance",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# RoutingProblem validation (contract §4.2/§4.4)
# ---------------------------------------------------------------------------


def test_problem_without_disposal_site_raises() -> None:
    """Contract §4.2: >=1 disposal site required."""
    with pytest.raises(RoutingSchemaError):
        RoutingProblem(
            depot=DEPOT,
            disposal_sites=[],
            stops=[STOP],
            vehicle_types=[VEHICLE],
            travel=identity_matrix(["depot_1", stop_point_id(STOP)]),
            config=CONFIG,
        )


def test_problem_without_vehicle_type_raises() -> None:
    """No vehicle can serve any route, so the problem is invalid input, not an
    infeasible solution (infeasibility is surfaced at M9)."""
    with pytest.raises(RoutingSchemaError):
        RoutingProblem(
            depot=DEPOT,
            disposal_sites=[DISPOSAL],
            stops=[STOP],
            vehicle_types=[],
            travel=identity_matrix(["depot_1", "disposal_1", stop_point_id(STOP)]),
            config=CONFIG,
        )


def test_problem_travel_missing_stop_point_id_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingProblem(
            depot=DEPOT,
            disposal_sites=[DISPOSAL],
            stops=[STOP],
            vehicle_types=[VEHICLE],
            travel=identity_matrix(["depot_1", "disposal_1"]),  # stop id missing
            config=CONFIG,
        )


def test_problem_travel_extra_point_id_raises() -> None:
    with pytest.raises(RoutingSchemaError):
        RoutingProblem(
            depot=DEPOT,
            disposal_sites=[DISPOSAL],
            stops=[STOP],
            vehicle_types=[VEHICLE],
            travel=identity_matrix(["depot_1", "disposal_1", stop_point_id(STOP), "ghost"]),
            config=CONFIG,
        )


def test_problem_duplicate_disposal_ids_raise() -> None:
    other = DisposalSite(id="disposal_1", name="Dup", lat=49.18, lon=9.27, service_minutes=30)
    with pytest.raises(RoutingSchemaError):
        RoutingProblem(
            depot=DEPOT,
            disposal_sites=[DISPOSAL, other],
            stops=[STOP],
            vehicle_types=[VEHICLE],
            travel=identity_matrix(["depot_1", "disposal_1", stop_point_id(STOP)]),
            config=CONFIG,
        )


def test_stop_point_id_format_is_deterministic() -> None:
    """location_ids are UUIDs without ':' [observed]; material has no ':' —
    the separator is unambiguous."""
    assert stop_point_id(STOP) == "loc-1:brown"
