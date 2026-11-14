"""GET /api/comparison + POST /api/datasets/demo — docs/contracts.md
§5.1/§5.2.2.

The comparison endpoint runs the real naive + OR-Tools pipeline (~seconds,
GLS wall-clock limit §4.4), so the shape assertions share one module-scoped
run on the synthetic VALID_CSV fixture. Demo-endpoint tests monkeypatch the
single server-side constant path (``services.DEMO_CSV_PATH``) for the
absent-file and invalid-file paths; the success path reads the real CSV.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import services
from src.api.main import app
from src.api.state import store
from tests.api.conftest import SMALL_CSV, upload_csv

AS_OF = "2026-09-30"
TARGET_DATE = "2026-10-28"  # as_of + horizon 28
DEMO_SOURCE_NAME = "demo:glass_fill_levels_anonymized_f.csv"

BAD_CSV = (
    "Location_id,material_type,date,fill_level_perc\n"
    "loc-a,brown,2026-01-05,20\n"
    "loc-x,brown,2026-03-01,abc\n"  # R5: neither int-in-range nor overfull
)


@pytest.fixture(scope="module")
def comparison_body() -> dict:
    """One solver-backed GET /api/comparison response for the whole module."""
    store.reset()
    client = TestClient(app)
    upload_csv(client)
    response = client.get("/api/comparison")
    assert response.status_code == 200, response.text
    return response.json()


class TestComparison:
    def test_comparison_404_without_dataset(self, client: TestClient) -> None:
        response = client.get("/api/comparison")
        assert response.status_code == 404
        assert "dataset" in response.json()["detail"].lower()

    def test_fixed_v1_defaults_are_echoed(self, comparison_body: dict) -> None:
        assert comparison_body["as_of_date"] == AS_OF
        assert comparison_body["horizon_days"] == 28
        assert comparison_body["target_date"] == TARGET_DATE
        assert comparison_body["method"] == "persistence"

    def test_scenarios_in_fixed_contract_order(self, comparison_body: dict) -> None:
        methods = [scenario["method"] for scenario in comparison_body["scenarios"]]
        assert methods == ["naive_sweep_all", "naive_sweep_selected", "ortools"]

    def test_sweep_all_scenario_shape(self, comparison_body: dict) -> None:
        sweep_all = comparison_body["scenarios"][0]
        assert sweep_all["status"] in {"complete", "incomplete"}
        assert sweep_all["stops_total"] == 5  # all VALID_CSV series, no policy filter
        assert sweep_all["stops_served"] + sweep_all["unserved_count"] == (sweep_all["stops_total"])
        assert sweep_all["vehicles_available"] == 3  # §4.6 demo_truck count
        assert sweep_all["vehicles_used"] >= 1
        assert sweep_all["distance_m"] >= 0
        assert sweep_all["duration_min"] >= 0
        assert sweep_all["collected_volume_litres"] > 0
        assert sweep_all["collected_weight_kg"] > 0
        assert sweep_all["recommended_trucks"] >= 1
        assert set(sweep_all["fleet_basis"]) == {"ceil_by_volume", "ceil_by_weight"}
        # §5.2.2: selection counts are not part of scenario rows at all.
        assert "selected_count" not in sweep_all
        assert "skipped_count" not in sweep_all

    def test_sweep_selected_matches_the_optimised_selection(self, comparison_body: dict) -> None:
        scenarios = comparison_body["scenarios"]
        sweep_selected, ortools = scenarios[1], scenarios[2]
        # Selection is deterministic: the median optimised run selected
        # loc-a brown/green/white fills 90/80/100 + the overfull green; only
        # loc-a white (40) is skipped below threshold 80 (§3.1 default).
        assert sweep_selected["stops_total"] == ortools["stops_total"] == 4
        assert (
            sweep_selected["stops_served"] + sweep_selected["unserved_count"]
            == (sweep_selected["stops_total"])
        )
        assert ortools["status"] in {"optimal", "feasible", "infeasible", "timeout"}
        assert ortools["stops_served"] + ortools["unserved_count"] == ortools["stops_total"]
        assert ortools["vehicles_available"] == 3

    def test_per_stop_and_per_kg_metrics_match_rows(self, comparison_body: dict) -> None:
        for scenario in comparison_body["scenarios"]:
            if scenario["stops_served"] > 0:
                assert scenario["distance_per_stop_m"] == round(
                    scenario["distance_m"] / scenario["stops_served"], 1
                )
            else:
                assert scenario["distance_per_stop_m"] is None  # never fabricated
            if scenario["collected_weight_kg"] > 0:
                assert scenario["distance_per_kg_m"] == round(
                    scenario["distance_m"] / scenario["collected_weight_kg"], 1
                )
            else:
                assert scenario["distance_per_kg_m"] is None

    def test_gains_decompose_the_scenario_distances(self, comparison_body: dict) -> None:
        sweep_all, sweep_selected, ortools = comparison_body["scenarios"]
        gains = comparison_body["gains"]
        assert gains["selection_gain_m"] == (sweep_all["distance_m"] - sweep_selected["distance_m"])
        if ortools["status"] in {"optimal", "feasible"}:
            assert gains["routing_gain_m"] == (sweep_selected["distance_m"] - ortools["distance_m"])
            assert gains["total_gain_m"] == (gains["selection_gain_m"] + gains["routing_gain_m"])
        else:
            # No usable optimised solution ⇒ null gains, never against 0 (§5.2.2).
            assert gains["routing_gain_m"] is None
            assert gains["total_gain_m"] is None

    def test_optimised_determinism_reports_the_protocol(self, comparison_body: dict) -> None:
        det = comparison_body["optimised_determinism"]
        assert det["runs"] == 5  # §4.7 [demo assumption]
        assert det["mode"] in {"identical", "median_of_runs"}
        assert det["distance_m_min"] <= det["distance_m_median"] <= det["distance_m_max"]
        if det["mode"] == "identical":
            assert det["distance_m_min"] == det["distance_m_max"]

    def test_provenance_and_assumption_labels(self, comparison_body: dict) -> None:
        assert comparison_body["distance_provenance"] == "haversine_straight_line_derived"
        assumptions = comparison_body["assumptions"]
        assert assumptions
        assert any("[demo assumption]" in label for label in assumptions)
        assert any("solution budget" in label for label in assumptions)  # §4.7 note
        assert any("area sweep" in label for label in assumptions)  # naive order
        assert any("lexicographic" in label for label in assumptions)  # within-cell order


class TestDemoDataset:
    def test_demo_upload_loads_fixed_server_csv(self, client: TestClient) -> None:
        if not services.DEMO_CSV_PATH.is_file():
            pytest.skip("server-side demo CSV not present (private data, gitignored) — skipped")
        response = client.post("/api/datasets/demo")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["source_name"] == DEMO_SOURCE_NAME  # "demo:" prefix (§5.2.2)
        assert body["n_rows"] == 11_701  # M2 real-CSV pins
        assert body["n_locations"] == 449
        assert body["n_series"] == 1_338
        assert body["n_errors"] == 0
        assert body["errors"] == []
        assert body["fill_stats"]["threshold_pct"] == 80
        summary = client.get("/api/summary")
        assert summary.json()["source_name"] == DEMO_SOURCE_NAME

    def test_demo_upload_replaces_active_dataset(self, client: TestClient) -> None:
        if not services.DEMO_CSV_PATH.is_file():
            pytest.skip("server-side demo CSV not present (private data, gitignored) — skipped")
        upload_csv(client, content=SMALL_CSV, name="small.csv")
        response = client.post("/api/datasets/demo")
        assert response.status_code == 200, response.text
        summary = client.get("/api/summary")
        assert summary.json()["n_rows"] == 11_701
        assert summary.json()["source_name"] == DEMO_SOURCE_NAME

    def test_demo_absent_file_404_and_dataset_unchanged(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        upload_csv(client, content=SMALL_CSV, name="small.csv")
        missing = tmp_path / "missing" / "demo.csv"
        monkeypatch.setattr(services, "DEMO_CSV_PATH", missing)
        response = client.post("/api/datasets/demo")
        assert response.status_code == 404
        assert "demo dataset" in response.json()["detail"].lower()
        summary = client.get("/api/summary")
        assert summary.json()["n_rows"] == 2  # active dataset untouched
        assert summary.json()["source_name"] == "small.csv"

    def test_demo_absent_file_404_friendly_operator_message(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Deployment brief task 3 §3: absent demo CSV -> a friendly 404 that
        tells the operator what to do instead (never a crash)."""
        upload_csv(client, content=SMALL_CSV, name="small.csv")
        missing = tmp_path / "missing" / "demo.csv"
        monkeypatch.setattr(services, "DEMO_CSV_PATH", missing)
        response = client.post("/api/datasets/demo")
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "not available in this deployment" in detail
        assert "POST /api/datasets" in detail  # actionable alternative
        assert str(missing) in detail  # which path is missing
        summary = client.get("/api/summary")
        assert summary.json()["n_rows"] == 2  # active dataset untouched

    def test_demo_invalid_csv_422_full_error_list_and_dataset_unchanged(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        upload_csv(client, content=SMALL_CSV, name="small.csv")
        invalid = tmp_path / "invalid_demo.csv"
        invalid.write_text(BAD_CSV, encoding="utf-8")
        monkeypatch.setattr(services, "DEMO_CSV_PATH", invalid)
        response = client.post("/api/datasets/demo")
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert len(detail["errors"]) == 1
        assert detail["errors"][0]["rule_id"] == "R5"
        summary = client.get("/api/summary")
        assert summary.json()["n_rows"] == 2  # §5.3: dataset not replaced
        assert summary.json()["source_name"] == "small.csv"
