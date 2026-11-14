"""Tests for src.analytics.series_features — per-series accumulation features.

All fixtures are SYNTHETIC (tests/fixtures/, ids prefixed ``SYNTHETIC-`` per
the M4 isolation convention) and engineered so every feature value below is
hand-computable. No real data is read here; the real-CSV pins live in
tests/analytics/test_real_csv_aggregates.py.

Descriptive only: fill-rate proxies summarise observed consecutive numeric
readings; reading semantics are unresolved (docs/data_profile.md §13.1), so no
causal interpretation is asserted anywhere in this module or its tests.
"""

from datetime import date
from pathlib import Path

import pytest

from src.analytics.series_features import (
    AccumulationSummary,
    SeriesFeatures,
    compute_accumulation_summary,
    compute_series_features,
)
from src.data.loader import load_glass_fill_csv
from src.data.schema import Dataset

FIXTURES = Path("tests/fixtures")


def _load_fixture(name: str) -> Dataset:
    result = load_glass_fill_csv(FIXTURES / name)
    assert not result.errors, f"fixture {name} must load cleanly: {result.errors}"
    assert result.dataset.summary.n_rows > 0
    return result.dataset


class TestSyntheticFixtureFeatures:
    """Hand-computed expectations on tests/fixtures/synthetic_accumulation.csv.

    Fixture (SYNTHETIC):
    - SYNTHETIC-acc-1 / brown: 2026-01-01:10, 2026-01-11:40, 2026-01-21:70
      -> both pairs +30 pct over 10 days -> rate +3.0 pct/day.
    - SYNTHETIC-acc-2 / green: 2026-02-01:80, 2026-02-09:50, 2026-02-17:overfull
      -> pair (80->50) -30 pct over 8 days = -3.75 pct/day; overfull breaks pairs.
    - SYNTHETIC-acc-3 / white: single reading 2026-03-05:50 -> no gaps/pairs.
    - SYNTHETIC-acc-4 / brown: 2026-03-01:100, 2026-03-15:100 -> flat pair,
      rate 0.0, share_at_100 = 1.0.
    """

    @pytest.fixture()
    def features_by_key(self) -> dict[tuple[str, str], SeriesFeatures]:
        dataset = _load_fixture("synthetic_accumulation.csv")
        features = compute_series_features(dataset.readings)
        assert len(features) == 4
        return {(f.location_id, f.material_type): f for f in features}

    def test_constant_accumulation_series(
        self, features_by_key: dict[tuple[str, str], SeriesFeatures]
    ) -> None:
        f = features_by_key[("SYNTHETIC-acc-1", "brown")]
        assert f.n_readings == 3
        assert f.n_numeric == 3
        assert f.n_overfull == 0
        assert f.first_date == date(2026, 1, 1)
        assert f.last_date == date(2026, 1, 21)
        assert f.span_days == 20
        assert f.median_gap_days == 10.0
        assert f.mean_gap_days == 10.0
        assert f.mean_fill_pct == pytest.approx(40.0)
        assert f.mean_delta_pct == pytest.approx(30.0)
        assert f.median_rate_pct_per_day == pytest.approx(3.0)
        assert f.mean_positive_rate_pct_per_day == pytest.approx(3.0)
        assert f.mean_negative_rate_pct_per_day is None
        assert f.n_increase_pairs == 2
        assert f.n_decrease_events == 0
        assert f.overfull_share == pytest.approx(0.0)
        assert f.share_at_100 == pytest.approx(0.0)

    def test_decreasing_series_with_overfull_break(
        self, features_by_key: dict[tuple[str, str], SeriesFeatures]
    ) -> None:
        f = features_by_key[("SYNTHETIC-acc-2", "green")]
        assert f.n_readings == 3
        assert f.n_numeric == 2
        assert f.n_overfull == 1
        # Only the (80 -> 50) pair is numeric-numeric; overfull terminates it.
        assert f.mean_delta_pct == pytest.approx(-30.0)
        assert f.median_rate_pct_per_day == pytest.approx(-30.0 / 8)
        assert f.mean_positive_rate_pct_per_day is None
        assert f.mean_negative_rate_pct_per_day == pytest.approx(-30.0 / 8)
        assert f.n_increase_pairs == 0
        assert f.n_decrease_events == 1
        assert f.overfull_share == pytest.approx(1.0 / 3)
        assert f.share_at_100 == pytest.approx(0.0)
        assert f.mean_fill_pct == pytest.approx(65.0)
        assert f.median_gap_days == pytest.approx(8.0)  # gap to overfull still a gap

    def test_single_reading_series_has_no_gaps_or_pairs(
        self, features_by_key: dict[tuple[str, str], SeriesFeatures]
    ) -> None:
        f = features_by_key[("SYNTHETIC-acc-3", "white")]
        assert f.n_readings == 1
        assert f.median_gap_days is None
        assert f.mean_gap_days is None
        assert f.mean_delta_pct is None
        assert f.median_rate_pct_per_day is None
        assert f.span_days == 0
        assert f.mean_fill_pct == pytest.approx(50.0)

    def test_flat_full_series(
        self, features_by_key: dict[tuple[str, str], SeriesFeatures]
    ) -> None:
        f = features_by_key[("SYNTHETIC-acc-4", "brown")]
        assert f.n_readings == 2
        assert f.mean_delta_pct == pytest.approx(0.0)
        assert f.median_rate_pct_per_day == pytest.approx(0.0)
        assert f.share_at_100 == pytest.approx(1.0)
        assert f.overfull_share == pytest.approx(0.0)


class TestInputOrderIndependence:
    """Series features must not depend on source row order (loader preserves it)."""

    def test_shuffled_rows_same_features(self) -> None:
        dataset = _load_fixture("synthetic_accumulation.csv")
        base = compute_series_features(dataset.readings)
        shuffled = list(reversed(dataset.readings))
        assert compute_series_features(shuffled) == base


class TestEmptyDataset:
    def test_empty_readings_yield_empty_summary(self) -> None:
        assert compute_series_features([]) == []
        summary = compute_accumulation_summary([])
        assert summary == AccumulationSummary(
            n_pairs=0,
            n_series_with_pairs=0,
            share_increasing_pairs=0.0,
            share_decreasing_pairs=0.0,
            share_flat_pairs=0.0,
            mean_delta_pct=0.0,
            median_delta_pct=0.0,
            median_rate_pct_per_day=0.0,
            mean_positive_rate_pct_per_day=None,
            mean_negative_rate_pct_per_day=None,
        )
