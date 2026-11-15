"""POST /api/datasets, GET /api/summary, GET /api/containers, GET /api/config
— docs/contracts.md §5.1/§5.2/§5.3 (M10)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.routing.demo_config import DEMO_DENSITY_SOURCE_LABEL
from tests.api.conftest import SMALL_CSV, VALID_CSV, upload_csv


class TestUpload:
    def test_upload_valid_csv_returns_summary(self, client: TestClient) -> None:
        response = client.post(
            "/api/datasets",
            files={"file": ("glass.csv", VALID_CSV.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["n_rows"] == 10
        assert body["n_locations"] == 2
        assert body["n_series"] == 5
        assert body["date_min"] == "2026-01-05"
        assert body["date_max"] == "2026-02-02"
        assert body["rows_per_material"] == {"brown": 5, "green": 2, "white": 3}
        assert body["n_errors"] == 0
        assert body["n_warnings"] == 0
        assert body["source_name"] == "glass.csv"
        assert body["errors"] == []
        assert body["warnings"] == []

    def test_upload_r7_warning_is_listed(self, client: TestClient) -> None:
        csv = (
            "Location_id,material_type,date,fill_level_perc\n"
            "loc-a,brown,2026-01-05,45\n"  # not a decile -> R7 warning only
        )
        response = client.post(
            "/api/datasets",
            files={"file": ("decile.csv", csv.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["n_errors"] == 0
        assert body["n_warnings"] == 1
        assert body["warnings"][0]["rule_id"] == "R7"
        assert response.json()["errors"] == []

    def test_upload_invalid_csv_422_full_error_list(self, client: TestClient) -> None:
        csv = (
            "Location_id,material_type,date,fill_level_perc\n"
            "loc-a,brown,2026-01-05,20\n"
            "loc-x,brown,2026-03-01,abc\n"  # R5: neither int-in-range nor overfull
        )
        response = client.post(
            "/api/datasets",
            files={"file": ("bad.csv", csv.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert len(detail["errors"]) == 1
        error = detail["errors"][0]
        assert error["rule_id"] == "R5"
        assert error["row_number"] == 2
        assert error["value"] == "abc"

    def test_upload_invalid_csv_leaves_dataset_unchanged(self, client: TestClient) -> None:
        upload_csv(client, content=SMALL_CSV, name="first.csv")
        response = client.post(
            "/api/datasets",
            files={"file": ("bad.csv", b"wrong,header\n1,2\n")},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["errors"][0]["rule_id"] == "R1"
        summary = client.get("/api/summary")
        assert summary.status_code == 200
        assert summary.json()["source_name"] == "first.csv"
        assert summary.json()["n_rows"] == 2

    def test_upload_header_mismatch_reports_r1_row_zero(self, client: TestClient) -> None:
        response = client.post(
            "/api/datasets",
            files={"file": ("bad.csv", b"wrong,header\n1,2\n")},
        )
        assert response.status_code == 422
        error = response.json()["detail"]["errors"][0]
        assert error["rule_id"] == "R1"
        assert error["row_number"] == 0

    def test_upload_replaces_active_dataset(self, client: TestClient) -> None:
        upload_csv(client, content=SMALL_CSV, name="small.csv")
        upload_csv(client, content=VALID_CSV, name="big.csv")
        summary = client.get("/api/summary")
        assert summary.json()["n_rows"] == 10
        assert summary.json()["source_name"] == "big.csv"


# Fill-stats fixture (hand-computed, §5.2.2): 5 readings — numeric 0, 80, 100,
# 30 plus one literal "overfull" row. Threshold 80 (§3.1 default): 2 numeric
# rows >= 80 -> 40.0; overfull 1/5 -> 20.0; empty (numeric 0) 1/5 -> 20.0.
# The overfull row must NOT enter the numeric shares (coercion would make
# full_or_above 60.0).
FILL_STATS_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2026-01-05,0
loc-a,brown,2026-01-19,80
loc-a,green,2026-02-01,overfull
loc-a,white,2026-01-06,100
loc-b,brown,2026-01-07,30
"""

EXPECTED_FILL_STATS = {
    "share_readings_full_or_above_pct": 40.0,
    "share_readings_overfull_pct": 20.0,
    "share_readings_empty_pct": 20.0,
    "threshold_pct": 80,
}


class TestFillStats:
    def test_upload_response_contains_fill_stats(self, client: TestClient) -> None:
        response = client.post(
            "/api/datasets",
            files={"file": ("stats.csv", FILL_STATS_CSV.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["fill_stats"] == EXPECTED_FILL_STATS

    def test_summary_fill_stats_match_upload(self, client: TestClient) -> None:
        upload_csv(client, content=FILL_STATS_CSV, name="stats.csv")
        assert client.get("/api/summary").json()["fill_stats"] == EXPECTED_FILL_STATS

    def test_fill_stats_round_to_one_decimal(self, client: TestClient) -> None:
        csv = (
            "Location_id,material_type,date,fill_level_perc\n"
            "loc-a,brown,2026-01-05,10\n"
            "loc-a,brown,2026-01-19,100\n"  # 1/3 readings >= 80 -> 33.3
            "loc-a,green,2026-02-01,20\n"
        )
        upload_csv(client, content=csv, name="thirds.csv")
        body = client.get("/api/summary").json()["fill_stats"]
        assert body == {
            "share_readings_full_or_above_pct": 33.3,
            "share_readings_overfull_pct": 0.0,
            "share_readings_empty_pct": 0.0,
            "threshold_pct": 80,
        }

    def test_fill_stats_zero_row_dataset_is_all_zero(self, client: TestClient) -> None:
        upload_csv(
            client,
            content="Location_id,material_type,date,fill_level_perc\n",
            name="header-only.csv",
        )
        body = client.get("/api/summary").json()
        assert body["n_rows"] == 0
        assert body["fill_stats"] == {
            "share_readings_full_or_above_pct": 0.0,
            "share_readings_overfull_pct": 0.0,
            "share_readings_empty_pct": 0.0,
            "threshold_pct": 80,
        }


class TestSummaryAndContainers:
    def test_summary_404_without_dataset(self, client: TestClient) -> None:
        response = client.get("/api/summary")
        assert response.status_code == 404
        assert "dataset" in response.json()["detail"].lower()

    def test_containers_404_without_dataset(self, client: TestClient) -> None:
        response = client.get("/api/containers")
        assert response.status_code == 404

    def test_summary_after_upload(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.get("/api/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["n_rows"] == 10
        assert body["n_series"] == 5
        assert body["source_name"] == "glass.csv"

    def test_containers_list_series_with_last_reading(self, client: TestClient) -> None:
        upload_csv(client)
        response = client.get("/api/containers")
        assert response.status_code == 200
        containers = response.json()
        assert len(containers) == 5
        # Deterministic order: (location_id, material_type) ascending.
        keys = [(c["location_id"], c["material_type"]) for c in containers]
        assert keys == sorted(keys)
        green_a = next(c for c in containers if c["material_type"] == "green")
        assert green_a == {
            "location_id": "loc-a",
            "material_type": "green",
            "n_readings": 2,
            "last_date": "2026-02-01",
            "last_fill_pct": None,  # overfull token is never coerced (§1.1)
            "last_is_overfull": True,
        }
        brown_b = next(
            c for c in containers if (c["location_id"], c["material_type"]) == ("loc-b", "brown")
        )
        assert brown_b["last_fill_pct"] == 80
        assert brown_b["last_is_overfull"] is False


class TestConfig:
    def test_config_returns_v4_demo_defaults(self, client: TestClient) -> None:
        """§4.6 v4 defaults: densities are [literature] 0.4; the two new
        cycle knobs (containers_per_series, frequency_days) are [demo
        assumption] Q11/Q10; all other values unchanged from v3."""
        response = client.get("/api/config")
        assert response.status_code == 200
        body = response.json()
        assert body["policy"] == {
            "select_threshold_pct": 80,
            "uncertainty_buffer_pct": 0,
            "overfull_always_selected": True,
        }
        routing = body["routing"]
        assert routing["container_volume_litres"] == 3000  # [representative §4.6 v3]
        assert routing["densities_kg_per_litre"] == {
            "brown": 0.4,  # [literature §4.6 v4 — AVV 20 01 02]
            "green": 0.4,
            "white": 0.4,
        }
        assert routing["vehicle_volume_capacity_litres"] == 12_000
        assert routing["vehicle_weight_capacity_kg"] == 10_000
        assert routing["vehicle_count_available"] == 3
        assert routing["vehicle_compartment_volume_litres"] is None  # equal thirds
        assert routing["stop_service_minutes"] == 5  # [representative §4.6 v3]
        assert routing["disposal_service_minutes"] == 30
        assert routing["max_shift_minutes"] == 480  # [representative §4.6 v3]
        assert routing["travel_time_mode"] == "fixed_per_leg"  # [representative §4.6 v3]
        assert routing["fixed_travel_minutes"] == 10  # [representative §4.6 v3]
        assert routing["cost_per_truck_day_eur"] == 500.0  # [representative §4.6 v3]
        assert routing["operating_days_per_week"] == 5  # [representative §4.6 v3]
        assert routing["operating_days_per_year"] == 200  # [representative §4.6 v3]
        assert routing["geography_seed"] == 0  # current SHA-256 layout
        assert routing["geography_spread_km"] == 6.0  # current 1-6 km band
        assert routing["avg_speed_kmh"] == 30.0
        assert routing["detour_factor"] == 1.4
        assert routing["solver_solution_limit"] == 200  # §4.6 v2 primary stop
        assert routing["solver_time_limit_s"] == 30.0  # §4.6 v2 safety cap only
        assert routing["containers_per_series"] == 1  # §4.2/§4.6 v4 [demo assumption Q11]
        assert routing["frequency_days"] == 28  # §4.7/§5.2.4 cycle [demo assumption Q10]

    def test_config_sources_map_and_assumption_fields_match_v3(self, client: TestClient) -> None:
        """§4.6 v3/§5.2: every routing field carries a per-field source;
        ``assumption_fields`` lists exactly the demo-assumption fields —
        [representative] fields are identified via ``sources`` only."""
        body = client.get("/api/config").json()
        sources = body["sources"]
        routing_fields = set(body["routing"])
        policy_fields = set(body["policy"])
        assert routing_fields <= set(sources)
        assert policy_fields <= set(sources)
        assert sources["horizon_days"] == "demo assumption"
        representative = {name for name, source in sources.items() if source == "representative"}
        assert representative == {
            "container_volume_litres",
            "stop_service_minutes",
            "max_shift_minutes",
            "travel_time_mode",
            "fixed_travel_minutes",
            "cost_per_truck_day_eur",
            "operating_days_per_week",
            "operating_days_per_year",
        }
        labelled = set(body["assumption_fields"])
        # §4.6 v4: the density is literature-sourced — neither a demo
        # assumption nor a representative field, so it sits in neither set.
        literature = {name for name, source in sources.items() if source == "literature"}
        assert literature == {"densities_kg_per_litre"}
        assert sources["densities_kg_per_litre"] == "literature"
        assert body["source_labels"]["densities_kg_per_litre"] == DEMO_DENSITY_SOURCE_LABEL
        # Representative fields are NOT demo assumptions (contract §5.2 v3),
        # and literature fields are labelled verbatim via source_labels only.
        assert representative.isdisjoint(labelled)
        assert literature.isdisjoint(labelled)
        all_fields = policy_fields | {"horizon_days"} | routing_fields
        assert all_fields - representative - literature == labelled
