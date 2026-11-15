"""Feature tests — hand-computed, leakage-checked on the synthetic fixture.

Feature norm (contract §2.2): only records with date <= as_of_date may be
used; the target record must not influence any feature. v4 semantics (§1.5):
``fill_at_emptying_rate_pct_per_day`` is the median fill-at-emptying rate
(never a Δfill/Δdays velocity); ``median_interval_days`` is date-based, so
overfull records participate in intervals but never in the numeric rate.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.forecasting.features import (
    build_feature_row,
    collect_fill_at_emptying_rates_pct_per_day,
    collect_positive_interval_days,
    collect_rate_candidates,
    group_by_series,
)


def series_readings(forecast_dataset, location_id: str, material: str):
    return group_by_series(forecast_dataset.readings)[(location_id, material)]


class TestBuildFeatureRow:
    def test_hand_computed_row_with_overfull_in_history(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-a", "brown")
        row = build_feature_row(readings, date(2026, 2, 5))
        assert row is not None
        # history <= as_of: 01-10:40, 02-05:overfull
        assert row.n_readings == 2
        assert row.last_numeric_fill_pct == 40
        assert row.last_reading_is_overfull is True
        assert row.days_since_last_reading == 0
        assert row.mean_numeric_fill_pct == 40.0
        assert row.max_numeric_fill_pct == 40
        assert row.overfull_share == 0.5
        assert row.month_of_as_of == 2
        # interval 01-10 -> 02-05 = 26 d (date-based; overfull participates)
        assert row.median_interval_days == 26.0
        # the only candidate is the overfull record → no numeric rate
        assert row.fill_at_emptying_rate_pct_per_day is None

    def test_row_includes_readings_up_to_as_of(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-a", "brown")
        row = build_feature_row(readings, date(2026, 3, 1))
        assert row is not None
        # history <= as_of: 01-10:40, 02-05:overfull, 03-01:60 (inclusive)
        assert row.n_readings == 3
        assert row.last_numeric_fill_pct == 60
        assert row.last_reading_is_overfull is False
        assert row.mean_numeric_fill_pct == 50.0
        assert row.max_numeric_fill_pct == 60
        assert row.overfull_share == 1 / 3
        assert row.month_of_as_of == 3
        # intervals 26 d and 24 d → median 25.0; rate candidates: only 60/24
        assert row.median_interval_days == 25.0
        assert row.fill_at_emptying_rate_pct_per_day == 60 / 24

    def test_single_reading_history(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-a", "brown")
        row = build_feature_row(readings, date(2026, 1, 10))
        assert row is not None
        assert row.n_readings == 1
        assert row.last_numeric_fill_pct == 40
        assert row.last_reading_is_overfull is False
        assert row.mean_numeric_fill_pct == 40.0
        assert row.max_numeric_fill_pct == 40
        assert row.overfull_share == 0.0
        assert row.month_of_as_of == 1
        assert row.fill_at_emptying_rate_pct_per_day is None
        assert row.median_interval_days is None

    def test_no_leakage_from_later_readings(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-a", "brown")
        row = build_feature_row(readings, date(2026, 1, 10))
        assert row is not None
        # later readings (overfull, 60, 80) must not leak into the row
        assert row.max_numeric_fill_pct == 40
        assert row.mean_numeric_fill_pct == 40.0
        assert row.overfull_share == 0.0
        assert row.last_reading_is_overfull is False

    def test_insufficient_history_returns_none(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-d", "brown")
        assert build_feature_row(readings, date(2026, 1, 1)) is None
        assert build_feature_row(readings, date(2026, 5, 2)) is not None

    def test_overfull_only_history_has_no_numeric_features(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-c", "white")
        row = build_feature_row(readings, date(2026, 2, 1))
        assert row is not None
        assert row.last_numeric_fill_pct is None  # token never coerced (§1.1)
        assert row.mean_numeric_fill_pct is None
        assert row.max_numeric_fill_pct is None
        assert row.overfull_share == 1.0

    def test_overfull_only_history_still_has_intervals(self, forecast_dataset) -> None:
        # Both records are the overfull token: the interval is date-based (28 d),
        # but no numeric rate candidate exists (§1.5: never coerced).
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-c", "white")
        row = build_feature_row(readings, date(2026, 3, 1))
        assert row is not None
        assert row.median_interval_days == 28.0
        assert row.fill_at_emptying_rate_pct_per_day is None

    def test_rate_uses_date_intervals_not_index(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-b", "green")
        row = build_feature_row(readings, date(2026, 3, 15))
        assert row is not None
        # single candidate: 90 / 59 d
        assert row.fill_at_emptying_rate_pct_per_day == 90 / 59
        assert row.median_interval_days == 59.0
        assert row.days_since_last_reading == 0


class TestRateHelpers:
    def test_candidates_include_overfull_records(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-a", "brown")
        history = sorted((r for r in readings if r.date <= date(2026, 4, 20)), key=lambda r: r.date)
        candidates = collect_rate_candidates(history)
        # pairs: (40->overfull, 26 d), (overfull->60, 24 d), (60->80, 50 d)
        assert [record.is_overfull for record, _days in candidates] == [True, False, False]
        assert [days for _record, days in candidates] == [26, 24, 50]
        # only numeric candidates contribute rates: 60/24 and 80/50
        assert collect_fill_at_emptying_rates_pct_per_day(history) == pytest.approx(
            [60 / 24, 80 / 50]
        )
        assert collect_positive_interval_days(history) == [26, 24, 50]

    def test_deterministic_regardless_of_input_order(self, forecast_dataset) -> None:
        readings = series_readings(forecast_dataset, "SYNTHETIC-f-a", "brown")
        assert collect_fill_at_emptying_rates_pct_per_day(
            sorted(readings, key=lambda r: r.date)
        ) == collect_fill_at_emptying_rates_pct_per_day(list(reversed(readings)))
        assert collect_positive_interval_days(sorted(readings, key=lambda r: r.date)) == (
            collect_positive_interval_days(list(reversed(readings)))
        )
