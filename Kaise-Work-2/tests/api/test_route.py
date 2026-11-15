"""POST /api/route end-to-end pipeline and OpenAPI surface — contracts §5.

The route chain (forecast -> select_candidates -> synthetic_stop_coordinates
-> build_travel_matrix -> build_routing_problem -> solve) is exercised through
the API only; solver internals belong to tests/routing (M9).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import upload_csv

AS_OF = "2026-02-15"
ALL_ENDPOINTS = {
    "/health",
    "/api/health",
    "/api/datasets",
    "/api/datasets/demo",
    "/api/summary",
    "/api/containers",
    "/api/config",
    "/api/forecasts",
    "/api/candidates",
    "/api/route",
    "/api/comparison",
    "/api/days-to-full",
}


class TestRoute:
    def test_route_404_without_dataset(self, client: TestClient) -> None:
        response = client.post("/api/route", json={"as_of_date": AS_OF})
        assert response.status_code == 404

    def test_route_happy_path_selection_and_solution(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"solver_time_limit_s": 0.5},
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # Always selection + solution, never a bare error (§5.3).
        assert len(body["selection"]["selected"]) == 4
        solution = body["solution"]
        assert solution["status"] in {"optimal", "feasible"}
        assert solution["distance_provenance"] == "haversine_straight_line_derived"
        totals = solution["totals"]
        assert totals["stops_total"] == 4
        assert totals["stops_served"] + len(solution["unserved"]) == totals["stops_total"]
        assert solution["fleet_recommendation"]["vehicle_type_id"] == "demo_truck"
        assert solution["fleet_recommendation"]["count"] >= 1
        assert solution["fleet_recommendation"]["basis"]["ceil_by_volume"] >= 1
        assert solution["fleet_recommendation"]["basis"]["ceil_by_weight"] >= 1
        for route in solution["routes"]:
            assert route["vehicle_type_id"] == "demo_truck"
            assert route["sequence"][0]["node_type"] == "depot"
            assert route["sequence"][-1]["node_type"] == "depot"
            for volume_kg, weight_kg in route["load_progression"]:
                assert volume_kg >= 0 and weight_kg >= 0

    def test_route_assumptions_labelled(self, client: TestClient) -> None:
        upload_csv(client)
        body = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"solver_time_limit_s": 0.5},
            },
        ).json()
        assumptions = body["assumptions"]
        assert assumptions
        # Every label carries its §4.6 v3 source: [demo assumption] or
        # [representative] (deployment-setting labels only with env knobs).
        assert all(
            "[demo assumption]" in label or "[representative]" in label or "[literature]" in label
            for label in assumptions
        )
        joined = "\n".join(assumptions)
        assert "synthetic" in joined.lower()  # synthetic geography labelled
        assert "not road distance" in joined.lower()  # provenance labelled

    def test_route_container_volume_override_reaches_stops(self, client: TestClient) -> None:
        upload_csv(client)
        body = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {
                    "solver_time_limit_s": 0.5,
                    "container_volume_litres": 5000,
                },
            },
        ).json()
        stop_nodes = [
            node
            for route in body["solution"]["routes"]
            for node in route["sequence"]
            if node["node_type"] == "stop"
        ]
        assert stop_nodes
        assert all(node["container_volume_litres"] == 5000 for node in stop_nodes)

    def test_route_invalid_routing_override_422(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"avg_speed_kmh": 0},
            },
        )
        assert response.status_code == 422
        assert "avg_speed_kmh" in response.json()["detail"]

    def test_route_partial_densities_rejected(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"densities_kg_per_litre": {"brown": 0.5}},
            },
        )
        assert response.status_code == 422
        assert "densities_kg_per_litre" in response.json()["detail"]

    def test_route_v3_cost_override_echoed_in_cost_block(self, client: TestClient) -> None:
        """§4.6 v3/§4.3: cost_per_truck_day_eur override rides the
        RoutingConfig constructor and the derived cost block echoes it."""
        upload_csv(client)
        body = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {
                    "solver_time_limit_s": 0.5,
                    "cost_per_truck_day_eur": 750.0,
                    "operating_days_per_year": 100,
                },
            },
        ).json()
        cost = body["solution"]["cost"]
        vehicles_used = len(body["solution"]["routes"])
        assert cost["vehicles_used"] == vehicles_used
        assert cost["cost_eur_per_day"] == vehicles_used * 750.0
        assert cost["cost_eur_per_year"] == vehicles_used * 750.0 * 100
        fleet_cost = cost["fleet_cost"]
        assert fleet_cost["trucks"] == body["solution"]["fleet_recommendation"]["count"]
        assert fleet_cost["cost_eur_per_day"] == fleet_cost["trucks"] * 750.0
        assert fleet_cost["cost_eur_per_year"] == fleet_cost["cost_eur_per_day"] * 100

    def test_route_travel_time_mode_override_echoed(self, client: TestClient) -> None:
        """§4.6 v3: travel_time_mode selects the matrix duration derivation;
        the solution echoes the effective mode."""
        upload_csv(client)
        body = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {
                    "solver_time_limit_s": 0.5,
                    "travel_time_mode": "haversine_derived",
                },
            },
        ).json()
        assert body["solution"]["travel_time_mode"] == "haversine_derived"
        # Default mode is fixed_per_leg with 10-minute legs (§4.6 v3).
        default = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"solver_time_limit_s": 0.5},
            },
        ).json()
        assert default["solution"]["travel_time_mode"] == "fixed_per_leg"

    def test_route_compartment_override_reaches_solution_totals(self, client: TestClient) -> None:
        """§4.2/§4.3 v3: an explicit compartment layout (validated by the
        VehicleType constructor, sum == volume capacity) surfaces via
        totals.collected_volume_by_material."""
        upload_csv(client)
        body = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {
                    "solver_time_limit_s": 0.5,
                    "vehicle_compartment_volume_litres": {
                        "brown": 6000,
                        "green": 4000,
                        "white": 2000,
                    },
                },
            },
        ).json()
        assert body["solution"]["status"] in {"optimal", "feasible"}
        by_material = body["solution"]["totals"]["collected_volume_by_material"]
        assert set(by_material) == {"brown", "green", "white"}
        assert sum(by_material.values()) == body["solution"]["totals"]["collected_volume_litres"]

    def test_route_totals_shift_derivations(self, client: TestClient) -> None:
        """§4.3 v4 [predicted] derived passthrough (solver.derive_shift_totals):
        shift_minutes_used is the busiest route's duration (max over routes;
        0 when no route exists) and stops_per_shift is
        round(stops_served / vehicles_used, 1) with one route per used
        vehicle."""
        upload_csv(client)
        body = client.post("/api/route", json={"as_of_date": AS_OF}).json()
        solution = body["solution"]
        routes = solution["routes"]
        totals = solution["totals"]
        if routes:
            assert totals["shift_minutes_used"] == max(
                route["duration_minutes"] for route in routes
            )
            assert totals["stops_per_shift"] == round(totals["stops_served"] / len(routes), 1)
        else:
            assert totals["shift_minutes_used"] == 0
            assert totals["stops_per_shift"] == 0.0

    def test_route_containers_per_series_override_doubles_volume(self, client: TestClient) -> None:
        """§4.2 v4: containers_per_series=2 doubles the collected litres
        (per-container volume x 2; the predicted fill % is the series
        aggregate and unchanged). The doubled load still fits one truck by
        also doubling the vehicle capacities (compartments must sum to the
        volume capacity, §4.2), so the served set is identical."""
        upload_csv(client)
        base = client.post("/api/route", json={"as_of_date": AS_OF}).json()
        doubled = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {
                    "containers_per_series": 2,
                    "vehicle_volume_capacity_litres": 24_000,
                    "vehicle_compartment_volume_litres": {
                        "brown": 8000,
                        "green": 8000,
                        "white": 8000,
                    },
                },
            },
        ).json()
        assert doubled["solution"]["status"] in {"optimal", "feasible"}
        base_volume = base["solution"]["totals"]["collected_volume_litres"]
        doubled_volume = doubled["solution"]["totals"]["collected_volume_litres"]
        assert base_volume > 0
        assert doubled_volume == 2 * base_volume
        assert (
            doubled["solution"]["totals"]["stops_served"]
            == base["solution"]["totals"]["stops_served"]
        )

    def test_route_frequency_days_zero_422(self, client: TestClient) -> None:
        """§4.2 v4: frequency_days must be an int >= 1 — the RoutingConfig
        constructor message surfaces on 422 (§5.3)."""
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={"as_of_date": AS_OF, "routing_config": {"frequency_days": 0}},
        )
        assert response.status_code == 422
        assert "frequency_days" in response.json()["detail"]

    def test_route_compartment_sum_mismatch_422(self, client: TestClient) -> None:
        """§4.2: compartments must sum to the volume capacity — the domain
        VehicleType message surfaces on 422 (§5.3)."""
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {
                    "vehicle_compartment_volume_litres": {
                        "brown": 5000,
                        "green": 5000,
                        "white": 5000,
                    },
                },
            },
        )
        assert response.status_code == 422
        assert "compartment" in response.json()["detail"]

    def test_route_invalid_travel_time_mode_422(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"travel_time_mode": "teleport"},
            },
        )
        assert response.status_code == 422  # Pydantic Literal rejects at the boundary

    def test_route_invalid_fixed_travel_minutes_422(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/route",
            json={
                "as_of_date": AS_OF,
                "routing_config": {"fixed_travel_minutes": 0},
            },
        )
        assert response.status_code == 422
        assert "fixed_travel_minutes" in response.json()["detail"]

    def test_route_zero_selected_still_returns_both_parts(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post("/api/route", json={"as_of_date": "2025-01-01"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["selection"]["selected"] == []
        assert len(body["selection"]["skipped"]) == 5
        solution = body["solution"]
        assert solution["status"] == "optimal"
        assert solution["routes"] == []
        assert solution["totals"]["stops_total"] == 0
        assert solution["unserved"] == []


class TestOpenApi:
    def test_openapi_lists_all_contract_endpoints(self, client: TestClient) -> None:
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert set(response.json()["paths"]) >= ALL_ENDPOINTS

    def test_health_root_and_api_prefix(self, client: TestClient) -> None:
        root = client.get("/health")
        assert root.status_code == 200
        assert root.json() == {"status": "ok", "service": "wasterouting-api"}
        prefixed = client.get("/api/health")
        assert prefixed.status_code == 200
        assert prefixed.json() == root.json()
