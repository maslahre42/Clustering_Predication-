"""GET /api/days-to-full — docs/contracts.md §5.1/§5.2.3 (v2, M16/v4).

The estimates come from ``src.forecasting.days_to_full.build_days_to_full``
(emptying-record semantics §1.5; no business logic in the API layer). The
hand-computed pins below walk the §5.2.3 v2 rules on the synthetic VALID_CSV
fixture (``loc-``-prefixed ids, never real data — M4 rule):

- loc-a brown 20→50→90 (14 d steps): rates 50/14 and 90/14 pp/day, median
  5.0; days_to_full = 90/5.0 = 18.0; predicted_full_date = 2026-02-02+18 =
  2026-02-20.
- loc-a green 10 then overfull: candidates exist but none numeric ⇒
  ``no_numeric_fill``, ``is_lower_bound`` (overfull candidate, §1.5);
  median interval 27 d is still date-based.
- loc-a white: single record ⇒ ``not_enough_records``.
- loc-b brown 30→80: rate 80/14 pp/day; days = round(90/(80/14), 1) = 15.8;
  predicted_full_date = 2026-01-21+16 = 2026-02-06.
- loc-b white 60→100: contributing fill 100 is a censored lower bound ⇒
  ``is_lower_bound``; rate 100/14; days = round(90/(100/14), 1) = 12.6;
  predicted_full_date = 2026-01-21+13 = 2026-02-03.

Stats cover series with an estimate only ({18.0, 15.8, 12.6}): median 15.8,
mean 46.4/3, min 12.6, max 18.0, lower-bound share 1/3 → 33.3 %.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.api.conftest import upload_csv


def _days_body(client: TestClient) -> dict:
    response = client.get("/api/days-to-full")
    assert response.status_code == 200, response.text
    return response.json()


class TestDaysToFull:
    def test_days_to_full_404_without_dataset(self, client: TestClient) -> None:
        response = client.get("/api/days-to-full")
        assert response.status_code == 404
        assert "dataset" in response.json()["detail"].lower()

    def test_method_and_shape(self, client: TestClient) -> None:
        upload_csv(client)
        body = _days_body(client)
        assert body["method"] == "fill_at_emptying_rate"
        assert body["target_pct"] == 90  # [demo assumption — slide mockup]
        assert set(body["stats"]) == {
            "series_total",
            "series_with_estimate",
            "median_days",
            "mean_days",
            "min_days",
            "max_days",
            "lower_bound_share_pct",
        }
        assert set(body["stats_by_material"]) == {"brown", "green", "white"}
        assert len(body["series"]) == 5  # all VALID_CSV series, exactly once
        keys = [(row["location_id"], row["material_type"]) for row in body["series"]]
        assert keys == sorted(keys)
        per_row_keys = {
            "location_id",
            "material_type",
            "last_emptying_date",
            "last_fill_pct",
            "last_is_overfull",
            "rate_pct_per_day",
            "median_interval_days",
            "days_to_full",
            "predicted_full_date",
            "is_lower_bound",
            "reason",
        }
        assert all(set(row) == per_row_keys for row in body["series"])
        assert any("not how fast it would have filled" in label for label in body["assumptions"])
        assert any("target fill 90%" in label for label in body["assumptions"])

    def test_estimated_series_hand_check(self, client: TestClient) -> None:
        upload_csv(client)
        body = _days_body(client)
        by_key = {(r["location_id"], r["material_type"]): r for r in body["series"]}

        brown_a = by_key[("loc-a", "brown")]
        assert brown_a["last_emptying_date"] == "2026-02-02"
        assert brown_a["last_fill_pct"] == 90
        assert brown_a["last_is_overfull"] is False
        assert brown_a["rate_pct_per_day"] == 5.0  # median(50/14, 90/14)
        assert brown_a["median_interval_days"] == 14.0
        assert brown_a["days_to_full"] == 18.0  # 90 / 5.0
        assert brown_a["predicted_full_date"] == "2026-02-20"  # last + round(18.0)
        assert brown_a["is_lower_bound"] is False
        assert brown_a["reason"] is None  # estimate present ⇒ no reason

        brown_b = by_key[("loc-b", "brown")]
        assert brown_b["rate_pct_per_day"] == 80 / 14
        assert brown_b["days_to_full"] == 15.8  # round(90/(80/14), 1)
        assert brown_b["predicted_full_date"] == "2026-02-06"  # 2026-01-21 + 16
        assert brown_b["is_lower_bound"] is False
        assert brown_b["reason"] is None

    def test_no_data_cases_never_fabricated(self, client: TestClient) -> None:
        upload_csv(client)
        body = _days_body(client)
        by_key = {(r["location_id"], r["material_type"]): r for r in body["series"]}

        # Overfull candidates: no numeric fill among them — never fabricated.
        green_a = by_key[("loc-a", "green")]
        assert green_a["last_fill_pct"] is None  # token never coerced (§1.1)
        assert green_a["last_is_overfull"] is True
        assert green_a["rate_pct_per_day"] is None
        assert green_a["median_interval_days"] == 27.0  # intervals are date-based
        assert green_a["days_to_full"] is None
        assert green_a["predicted_full_date"] is None
        assert green_a["is_lower_bound"] is True  # overfull candidate (§1.5)
        assert green_a["reason"] == "no_numeric_fill"

        # Single record: not enough history.
        white_a = by_key[("loc-a", "white")]
        assert white_a["rate_pct_per_day"] is None
        assert white_a["median_interval_days"] is None
        assert white_a["days_to_full"] is None
        assert white_a["predicted_full_date"] is None
        assert white_a["reason"] == "not_enough_records"

    def test_lower_bound_pin(self, client: TestClient) -> None:
        upload_csv(client)
        body = _days_body(client)
        by_key = {(r["location_id"], r["material_type"]): r for r in body["series"]}
        white_b = by_key[("loc-b", "white")]
        # Contributing numeric 100 is a censored lower bound (§1.5): the value
        # still enters the rate median, but the estimate is flagged.
        assert white_b["last_fill_pct"] == 100
        assert white_b["rate_pct_per_day"] == 100 / 14
        assert white_b["days_to_full"] == 12.6  # round(90/(100/14), 1)
        assert white_b["predicted_full_date"] == "2026-02-03"  # 2026-01-21 + 13
        assert white_b["is_lower_bound"] is True
        assert white_b["reason"] is None

    def test_aggregate_stats_cover_estimates_only(self, client: TestClient) -> None:
        upload_csv(client)
        stats = _days_body(client)["stats"]
        assert stats["series_total"] == 5
        assert stats["series_with_estimate"] == 3
        assert stats["min_days"] == 12.6
        assert stats["max_days"] == 18.0
        assert stats["median_days"] == 15.8  # median({18.0, 15.8, 12.6})
        assert stats["mean_days"] == (18.0 + 15.8 + 12.6) / 3
        assert stats["lower_bound_share_pct"] == 33.3  # 1 of 3 estimates flagged

    def test_stats_by_material(self, client: TestClient) -> None:
        upload_csv(client)
        by_material = _days_body(client)["stats_by_material"]
        brown = by_material["brown"]
        assert brown["series_total"] == 2
        assert brown["series_with_estimate"] == 2
        assert brown["median_days"] == 16.9  # median({18.0, 15.8})
        assert brown["lower_bound_share_pct"] == 0.0
        green = by_material["green"]
        assert green["series_total"] == 1
        assert green["series_with_estimate"] == 0
        assert green["median_days"] is None
        assert green["lower_bound_share_pct"] is None
        white = by_material["white"]
        assert white["series_with_estimate"] == 1
        assert white["median_days"] == 12.6
        assert white["lower_bound_share_pct"] == 100.0
