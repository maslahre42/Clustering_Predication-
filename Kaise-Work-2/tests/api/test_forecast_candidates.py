"""POST /api/forecasts and POST /api/candidates — docs/contracts.md §5.1/§5.2
(§2 ForecastRecord, §3 SelectionResult echoes)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import upload_csv


class TestForecasts:
    def test_forecasts_404_without_dataset(self, client: TestClient) -> None:
        response = client.post("/api/forecasts", json={"as_of_date": "2026-02-15"})
        assert response.status_code == 404

    def test_forecasts_persistence_happy_path(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post("/api/forecasts", json={"as_of_date": "2026-02-15"})
        assert response.status_code == 200, response.text
        body = response.json()
        # Defaults: method "persistence", horizon_days 28 [demo assumption §5.1].
        assert body["method"] == "persistence"
        assert body["as_of_date"] == "2026-02-15"
        assert body["target_date"] == "2026-03-15"
        records = {(f["location_id"], f["material_type"]): f for f in body["forecasts"]}
        assert set(records) == {
            ("loc-a", "brown"),
            ("loc-a", "green"),
            ("loc-a", "white"),
            ("loc-b", "brown"),
            ("loc-b", "white"),
        }
        brown_a = records[("loc-a", "brown")]
        assert brown_a["predicted_fill_pct"] == 90.0  # last numeric reading
        assert brown_a["predicted_state"] == "normal"
        assert brown_a["horizon_days"] == 28
        assert brown_a["method"] == "persistence"
        # Overfull token is preserved as a state, numeric falls back (§2.3).
        green_a = records[("loc-a", "green")]
        assert green_a["predicted_state"] == "overfull"
        assert green_a["predicted_fill_pct"] == 10.0
        # Numeric 100 is the distinct "full" state (§2.2).
        white_b = records[("loc-b", "white")]
        assert white_b["predicted_state"] == "full"
        assert white_b["predicted_fill_pct"] == 100.0

    def test_forecasts_rate_method_projected_and_clipped(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/forecasts",
            json={"as_of_date": "2026-02-15", "method": "rate"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["method"] == "rate"
        brown_a = next(
            f
            for f in body["forecasts"]
            if (f["location_id"], f["material_type"]) == ("loc-a", "brown")
        )
        # §2.3 v2: rate candidates 50/14 and 90/14 (fill/interval over the
        # two 14-day gaps) -> median rate 5.0 pp/day x median interval
        # 14 d = 70.0, within [0,100] (§2.3; no clipping needed).
        assert brown_a["predicted_fill_pct"] == 70.0
        assert brown_a["predicted_state"] == "normal"

    def test_forecasts_explicit_horizon_sets_target_date(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/forecasts",
            json={"as_of_date": "2026-02-15", "horizon_days": 7},
        )
        assert response.status_code == 200
        assert response.json()["target_date"] == "2026-02-22"

    def test_forecasts_before_any_history_yields_empty_batch(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post("/api/forecasts", json={"as_of_date": "2025-01-01"})
        assert response.status_code == 200
        assert response.json()["forecasts"] == []

    def test_forecasts_rejects_invalid_horizon(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/forecasts",
            json={"as_of_date": "2026-02-15", "horizon_days": 0},
        )
        assert response.status_code == 422

    def test_forecasts_rejects_unknown_method(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/forecasts",
            json={"as_of_date": "2026-02-15", "method": "linear"},
        )
        assert response.status_code == 422


class TestCandidates:
    def test_candidates_404_without_dataset(self, client: TestClient) -> None:
        response = client.post("/api/candidates", json={"as_of_date": "2026-02-15"})
        assert response.status_code == 404

    def test_candidates_happy_path_explains_every_series(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post("/api/candidates", json={"as_of_date": "2026-02-15"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["as_of_date"] == "2026-02-15"
        assert body["target_date"] == "2026-03-15"
        # Exactly-once invariant (§3.4): selected + skipped covers the universe.
        selected_keys = [(c["location_id"], c["material_type"]) for c in body["selected"]]
        skipped_keys = [(s["location_id"], s["material_type"]) for s in body["skipped"]]
        assert len(selected_keys) + len(skipped_keys) == 5
        assert not set(selected_keys) & set(skipped_keys)
        # Defaults: 90/100/80/overfull >= 80 -> 4 selected, 40 < 80 -> 1 skipped.
        assert set(selected_keys) == {
            ("loc-a", "brown"),
            ("loc-a", "green"),
            ("loc-b", "brown"),
            ("loc-b", "white"),
        }
        assert skipped_keys == [("loc-a", "white")]
        reasons = {c["reason_code"] for c in body["selected"]}
        assert "overfull_state" in reasons
        assert "at_or_above_threshold" in reasons
        assert body["skipped"][0]["reason_code"] == "below_threshold"
        assert body["skipped"][0]["detail"]  # deterministic explanation present
        # Effective policy config echoed (§5.3).
        assert body["config"] == {
            "select_threshold_pct": 80,
            "uncertainty_buffer_pct": 0,
            "overfull_always_selected": True,
        }

    def test_candidates_selected_sorted_by_fill_desc(self, client: TestClient) -> None:
        upload_csv(client)
        body = client.post("/api/candidates", json={"as_of_date": "2026-02-15"}).json()
        fills = [c["predicted_fill_pct"] for c in body["selected"]]
        assert fills == sorted(fills, reverse=True)

    def test_candidates_override_echoed_and_applied(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/candidates",
            json={
                "as_of_date": "2026-02-15",
                "policy_config": {"select_threshold_pct": 30},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["config"]["select_threshold_pct"] == 30
        assert body["config"]["uncertainty_buffer_pct"] == 0  # non-overridden default
        # Threshold 30 now selects loc-a/white (predicted 40) as well.
        assert len(body["selected"]) == 5
        assert body["skipped"] == []

    def test_candidates_invalid_override_422_with_domain_message(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.post(
            "/api/candidates",
            json={
                "as_of_date": "2026-02-15",
                "policy_config": {"select_threshold_pct": 150},
            },
        )
        assert response.status_code == 422
        assert "select_threshold_pct" in response.json()["detail"]

    def test_candidates_before_history_all_no_forecast_skips(self, client: TestClient) -> None:
        upload_csv(client)
        body = client.post("/api/candidates", json={"as_of_date": "2025-01-01"}).json()
        assert body["selected"] == []
        assert len(body["skipped"]) == 5
        assert all(s["reason_code"] == "no_forecast" for s in body["skipped"])
        assert body["as_of_date"] is None  # empty batch -> None dates (§3.4)
        assert body["target_date"] is None
