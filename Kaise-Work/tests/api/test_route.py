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
        assert all("[demo assumption]" in label for label in assumptions)
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
