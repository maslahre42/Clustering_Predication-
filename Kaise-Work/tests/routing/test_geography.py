"""Geography/travel-matrix/build_routing_problem tests — contracts §4.2/§4.4.

Coordinates are deterministic synthetic demo fixtures [demo assumption — no
real coordinates exist, contract §4.5]; distances are haversine x detour
factor with provenance "haversine_straight_line_derived" (never "road").
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from src.collection.policy import Candidate
from src.data.schema import MaterialType
from src.routing.demo_config import (
    DEMO_CONTAINER_VOLUME_LITRES,
    DEMO_DETOUR_FACTOR,
    DEMO_STOP_SERVICE_MINUTES,
    demo_depot,
    demo_disposal_site,
    demo_routing_config,
    demo_vehicle_type,
)
from src.routing.geography import (
    EARTH_RADIUS_M,
    build_routing_problem,
    build_travel_matrix,
    haversine_distance_m,
    synthetic_stop_coordinates,
)
from src.routing.schemas import (
    Depot,
    RoutingConfig,
    RoutingProblem,
    RoutingSchemaError,
    Stop,
    TravelMatrix,
    VehicleType,
    stop_point_id,
)

DEPOT = demo_depot()
DISPOSAL = demo_disposal_site()
CONFIG = demo_routing_config()
VEHICLES: list[VehicleType] = [demo_vehicle_type()]


def make_candidate(
    location_id: str,
    material_type: MaterialType,
    predicted_fill_pct: float,
) -> Candidate:
    return Candidate(
        location_id=location_id,
        material_type=material_type,
        predicted_fill_pct=predicted_fill_pct,
        predicted_state="full" if predicted_fill_pct >= 100.0 else "normal",
        reason_code="at_or_above_threshold",
        detail="test fixture",
    )


def make_stops(
    keys: Sequence[tuple[str, MaterialType]],
    container_volume_litres: int = DEMO_CONTAINER_VOLUME_LITRES,
) -> list[Stop]:
    coordinates = synthetic_stop_coordinates(keys, DEPOT)
    return [
        Stop(
            location_id=location_id,
            material_type=material,
            lat=coordinates[(location_id, material)][0],
            lon=coordinates[(location_id, material)][1],
            container_volume_litres=container_volume_litres,
            predicted_fill_pct=90.0,
            service_minutes=DEMO_STOP_SERVICE_MINUTES,
        )
        for location_id, material in keys
    ]


# ---------------------------------------------------------------------------
# haversine
# ---------------------------------------------------------------------------


def test_haversine_zero_for_same_point() -> None:
    assert haversine_distance_m(49.15, 9.22, 49.15, 9.22) == 0.0


def test_haversine_symmetry() -> None:
    a = haversine_distance_m(49.15, 9.22, 49.17, 9.26)
    b = haversine_distance_m(49.17, 9.26, 49.15, 9.22)
    assert math.isclose(a, b)


def test_haversine_demo_depot_to_disposal_is_plausible() -> None:
    """Demo depot (49.15, 9.22) -> disposal (49.17, 9.26): dlat 0.02 deg
    (~2.22 km) and dlon 0.04 deg (~2.91 km at this latitude) give roughly
    3.7 km straight line — bounded check, not the same formula."""
    distance_m = haversine_distance_m(DEPOT.lat, DEPOT.lon, DISPOSAL.lat, DISPOSAL.lon)
    assert 3400.0 <= distance_m <= 4000.0


def test_haversine_uses_standard_mean_earth_radius() -> None:
    """Documented constant, not a tuned knob."""
    assert EARTH_RADIUS_M == 6_371_000.0


# ---------------------------------------------------------------------------
# Synthetic coordinates (deterministic, seeded, stable across runs)
# ---------------------------------------------------------------------------


def test_synthetic_coordinates_deterministic_across_calls() -> None:
    keys = [("loc-a", "brown"), ("loc-b", "green"), ("loc-c", "white")]
    first = synthetic_stop_coordinates(keys, DEPOT)
    second = synthetic_stop_coordinates(keys, DEPOT)
    assert first == second


def test_synthetic_coordinates_cover_every_key() -> None:
    keys = [("loc-a", "brown"), ("loc-a", "green"), ("loc-b", "white")]
    coordinates = synthetic_stop_coordinates(keys, DEPOT)
    assert set(coordinates) == set(keys)
    for lat, lon in coordinates.values():
        assert -90.0 <= lat <= 90.0
        assert -180.0 <= lon <= 180.0


def test_synthetic_coordinates_spread_within_demo_radius() -> None:
    """All synthetic stops stay within the 1-6 km demo spread around the
    depot (great-circle, before detour) [demo assumption]."""
    keys = [(f"loc-{i}", "brown") for i in range(12)]
    coordinates = synthetic_stop_coordinates(keys, DEPOT)
    for lat, lon in coordinates.values():
        distance_m = haversine_distance_m(DEPOT.lat, DEPOT.lon, lat, lon)
        assert 1_000.0 <= distance_m <= 6_000.0


# ---------------------------------------------------------------------------
# build_travel_matrix
# ---------------------------------------------------------------------------


def test_matrix_point_order_is_depot_disposal_then_sorted_stops() -> None:
    stops = make_stops([("loc-b", "green"), ("loc-a", "brown")])
    matrix = build_travel_matrix(DEPOT, [DISPOSAL], stops, CONFIG)
    assert matrix.point_ids == [
        "demo_depot",
        "demo_disposal_1",
        "loc-a:brown",
        "loc-b:green",
    ]


def test_matrix_distances_apply_detour_factor_and_are_ints() -> None:
    stop = make_stops([("loc-a", "brown")])[0]
    matrix = build_travel_matrix(DEPOT, [DISPOSAL], [stop], CONFIG)
    straight_m = haversine_distance_m(DEPOT.lat, DEPOT.lon, stop.lat, stop.lon)
    expected = round(straight_m * DEMO_DETOUR_FACTOR)
    i = matrix.point_ids.index("demo_depot")
    j = matrix.point_ids.index(stop_point_id(stop))
    assert matrix.distance_m[i][j] == expected
    assert isinstance(matrix.distance_m[i][j], int)


def test_matrix_durations_derive_from_speed() -> None:
    """duration_min = round(distance_m / (speed_kmh * 1000 / 60)) — at 30 km/h
    that is 500 m per minute."""
    stop = make_stops([("loc-a", "brown")])[0]
    matrix = build_travel_matrix(DEPOT, [DISPOSAL], [stop], CONFIG)
    i = matrix.point_ids.index("demo_depot")
    j = matrix.point_ids.index(stop_point_id(stop))
    expected = round(matrix.distance_m[i][j] / (CONFIG.avg_speed_kmh * 1000.0 / 60.0))
    assert matrix.duration_min[i][j] == expected


def test_matrix_is_symmetric_with_zero_diagonal() -> None:
    stops = make_stops([("loc-a", "brown"), ("loc-b", "green")])
    matrix = build_travel_matrix(DEPOT, [DISPOSAL], stops, CONFIG)
    n = len(matrix.point_ids)
    for i in range(n):
        assert matrix.distance_m[i][i] == 0
        assert matrix.duration_min[i][i] == 0
        for j in range(n):
            assert matrix.distance_m[i][j] == matrix.distance_m[j][i]
            assert matrix.duration_min[i][j] == matrix.duration_min[j][i]


def test_matrix_provenance_is_straight_line_derived_never_road() -> None:
    stops = make_stops([("loc-a", "brown")])
    matrix = build_travel_matrix(DEPOT, [DISPOSAL], stops, CONFIG)
    assert matrix.provenance == "haversine_straight_line_derived"
    assert "road" not in matrix.provenance


def test_matrix_is_deterministic_for_shuffled_input_order() -> None:
    stops_a = make_stops([("loc-a", "brown"), ("loc-b", "green"), ("loc-c", "white")])
    stops_b = list(reversed(stops_a))
    matrix_a = build_travel_matrix(DEPOT, [DISPOSAL], stops_a, CONFIG)
    matrix_b = build_travel_matrix(DEPOT, [DISPOSAL], stops_b, CONFIG)
    assert matrix_a == matrix_b


def test_matrix_deterministic_across_repeated_calls() -> None:
    stops = make_stops([("loc-a", "brown"), ("loc-b", "green")])
    assert build_travel_matrix(DEPOT, [DISPOSAL], stops, CONFIG) == build_travel_matrix(
        DEPOT, [DISPOSAL], stops, CONFIG
    )


# ---------------------------------------------------------------------------
# build_routing_problem
# ---------------------------------------------------------------------------


def _problem(
    candidates: list[Candidate],
    container_volume_litres: int = DEMO_CONTAINER_VOLUME_LITRES,
    config: RoutingConfig | None = None,
) -> RoutingProblem:
    stops = make_stops(
        [(c.location_id, c.material_type) for c in candidates],
        container_volume_litres=container_volume_litres,
    )
    travel = build_travel_matrix(DEPOT, [DISPOSAL], stops, CONFIG)
    return build_routing_problem(
        selected_candidates=candidates,
        depot=DEPOT,
        disposal_sites=[DISPOSAL],
        vehicle_types=VEHICLES,
        container_volume_litres=container_volume_litres,
        config=config or CONFIG,
        coordinates=synthetic_stop_coordinates(
            [(c.location_id, c.material_type) for c in candidates], DEPOT
        ),
        travel=travel,
    )


def test_problem_from_candidates_builds_stops_with_demo_defaults() -> None:
    candidates = [make_candidate("loc-a", "brown", 90.0)]
    problem = _problem(candidates)
    stops = problem.stops
    assert len(stops) == 1
    assert stops[0].container_volume_litres == DEMO_CONTAINER_VOLUME_LITRES
    assert stops[0].service_minutes == DEMO_STOP_SERVICE_MINUTES
    assert stops[0].predicted_fill_pct == 90.0


def test_collected_volume_is_fill_pct_times_container_volume() -> None:
    """collected_volume_litres = round(container_volume_litres * pct / 100):
    1900 L at 90 % = 1710 L exactly."""
    candidates = [make_candidate("loc-a", "brown", 90.0)]
    problem = _problem(candidates)
    stop = problem.stops[0]
    assert stop.collected_volume_litres == 1710


def test_collected_weight_is_volume_times_density() -> None:
    """weight_kg = round(collected_volume_litres * density): 1710 L x
    0.5 kg/L = 855 kg with the uniform demo density."""
    candidates = [make_candidate("loc-a", "brown", 90.0)]
    problem = _problem(candidates)
    stop = problem.stops[0]
    assert stop.collected_weight_kg(CONFIG.densities_kg_per_litre["brown"]) == 855


def test_full_container_collects_full_volume_and_half_weight() -> None:
    candidates = [make_candidate("loc-a", "white", 100.0)]
    problem = _problem(candidates)
    stop = problem.stops[0]
    assert stop.collected_volume_litres == 1900
    assert stop.collected_weight_kg(0.5) == 950


def test_rounding_is_nearest_with_bankers_ties() -> None:
    """Rounding is documented as Python round() (half-to-even, nearest):
    1000 L x 0.85 % = 8.5 L -> 8 L (tie rounds to even); 8 L x 0.5 = 4 kg."""
    candidates = [make_candidate("loc-a", "brown", 0.85)]
    problem = _problem(candidates, container_volume_litres=1000)
    stop = problem.stops[0]
    assert stop.collected_volume_litres == 8
    assert stop.collected_weight_kg(0.5) == 4


def test_problem_stops_sorted_deterministically() -> None:
    candidates = [
        make_candidate("loc-c", "white", 95.0),
        make_candidate("loc-a", "green", 99.0),
        make_candidate("loc-b", "brown", 97.0),
    ]
    problem = _problem(candidates)
    keys = [(s.location_id, s.material_type) for s in problem.stops]
    assert keys == [("loc-a", "green"), ("loc-b", "brown"), ("loc-c", "white")]


def test_problem_travel_covers_all_point_ids() -> None:
    candidates = [make_candidate("loc-a", "brown", 90.0), make_candidate("loc-b", "green", 85.0)]
    problem = _problem(candidates)
    expected = {"demo_depot", "demo_disposal_1"} | {stop_point_id(s) for s in problem.stops}
    assert set(problem.travel.point_ids) == expected


def test_problem_rejects_duplicate_candidate_keys() -> None:
    candidates = [make_candidate("loc-a", "brown", 90.0), make_candidate("loc-a", "brown", 95.0)]
    with pytest.raises(RoutingSchemaError):
        _problem(candidates)


def test_problem_rejects_travel_missing_a_stop() -> None:
    candidates = [make_candidate("loc-a", "brown", 90.0), make_candidate("loc-b", "green", 85.0)]
    stops = make_stops([(c.location_id, c.material_type) for c in candidates])
    travel = build_travel_matrix(DEPOT, [DISPOSAL], stops[:1], CONFIG)  # missing loc-b
    with pytest.raises(RoutingSchemaError):
        build_routing_problem(
            selected_candidates=candidates,
            depot=DEPOT,
            disposal_sites=[DISPOSAL],
            vehicle_types=VEHICLES,
            container_volume_litres=DEMO_CONTAINER_VOLUME_LITRES,
            config=CONFIG,
            coordinates=synthetic_stop_coordinates(
                [(c.location_id, c.material_type) for c in candidates], DEPOT
            ),
            travel=travel,
        )


def test_problem_is_deterministic_for_equal_inputs() -> None:
    candidates = [make_candidate("loc-a", "brown", 90.0), make_candidate("loc-b", "green", 80.0)]
    assert _problem(candidates) == _problem(list(reversed(candidates)))


def test_synthetic_depot_helper_types_are_stable() -> None:
    """Depot type flows unchanged through the demo config helpers."""
    assert isinstance(DEPOT, Depot)
    assert isinstance(CONFIG, RoutingConfig)
    assert isinstance(VEHICLES[0], VehicleType)
    assert isinstance(
        build_travel_matrix(DEPOT, [DISPOSAL], make_stops([("loc-a", "brown")]), CONFIG),
        TravelMatrix,
    )
