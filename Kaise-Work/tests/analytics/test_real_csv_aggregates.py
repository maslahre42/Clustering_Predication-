"""Real-CSV aggregate pins for the M3/M4 analytics pipeline (regression).

Loads data/raw/glass_fill_levels_anonymized_f.csv ONCE through the canonical
loader and asserts only compact aggregates — every pin traces to
docs/data_profile.md (§6/§7/§8/§12/§14/§15/§16/§17). The raw file is never
printed or read whole; synthetic fixtures (SYNTHETIC- ids) are rejected here
by the require_real_ids guard, proving real/synthetic isolation on the
analysis path.
"""

import statistics
from datetime import date
from pathlib import Path

import pytest

from src.analytics.grouping import cluster_or_tier
from src.analytics.holidays import bw_holidays_in_range
from src.analytics.report import build_report
from src.analytics.seasonality import compute_seasonality
from src.analytics.series_features import (
    collect_gaps_days,
    collect_numeric_pairs,
    compute_accumulation_summary,
    compute_series_features,
)
from src.analytics.spatial import require_real_ids
from src.data.loader import load_glass_fill_csv
from tests.helpers import REAL_CSV_PATH, require_real_csv_path


@pytest.fixture(scope="module")
def dataset():
    result = load_glass_fill_csv(require_real_csv_path())
    assert not result.errors, f"real CSV must load cleanly, got: {result.errors[:3]}"
    return result.dataset


class TestLoaderPins:
    def test_summary(self, dataset) -> None:
        s = dataset.summary
        assert s.n_rows == 11701  # profile §17
        assert s.n_locations == 449
        assert s.n_series == 1338
        assert s.date_min == date(2025, 10, 17)  # profile §6
        assert s.date_max == date(2026, 9, 30)
        assert s.rows_per_material == {"brown": 3100, "green": 4169, "white": 4432}  # §15

    def test_no_synthetic_ids_in_real_data(self, dataset) -> None:
        require_real_ids(dataset.readings)  # must not raise


class TestSeriesFeaturePins:
    def test_series_level_facts(self, dataset) -> None:
        features = compute_series_features(dataset.readings)
        assert len(features) == 1338  # §7
        single = sum(1 for f in features if f.n_readings == 1)
        assert single == 34  # §12.3
        med_gaps = [f.median_gap_days for f in features if f.median_gap_days is not None]
        assert len(med_gaps) == 1338 - 34
        assert statistics.median(med_gaps) == 35.0  # §14 per-series median gap median
        assert max(med_gaps) == 265.0  # §14
        assert min(med_gaps) == 7.0  # §14
        n_numeric_total = sum(f.n_numeric for f in features)
        n_overfull_total = sum(f.n_overfull for f in features)
        assert n_numeric_total == 10509  # §8
        assert n_overfull_total == 1192  # §8


class TestAccumulationPins:
    def test_gaps_and_pairs(self, dataset) -> None:
        gaps = collect_gaps_days(dataset.readings)
        assert len(gaps) == 11701 - 1338  # §14: 10,363 gaps
        assert max(gaps) == 272  # §12.2
        assert statistics.median(gaps) == 28  # §14
        pairs = collect_numeric_pairs(dataset.readings)
        assert 0 < len(pairs) <= len(gaps)
        summary = compute_accumulation_summary(dataset.readings)
        assert summary.n_pairs == len(pairs)
        assert (
            abs(
                summary.share_increasing_pairs
                + summary.share_decreasing_pairs
                + summary.share_flat_pairs
                - 1.0
            )
            < 1e-9
        )


class TestSeasonalityPins:
    def test_monthly_counts_match_profile(self, dataset) -> None:
        report = compute_seasonality(dataset.readings)
        counts = {m.month: m.n_readings for m in report.months}
        assert counts == {  # profile §16
            "2025-10": 741,
            "2025-11": 656,
            "2025-12": 1357,
            "2026-01": 783,
            "2026-02": 657,
            "2026-03": 776,
            "2026-04": 896,
            "2026-05": 951,
            "2026-06": 1501,
            "2026-07": 1310,
            "2026-08": 1215,
            "2026-09": 858,
        }

    def test_holiday_calendar_in_dataset_span(self, dataset) -> None:
        report = compute_seasonality(dataset.readings)
        cmp = report.holiday_comparison
        assert cmp.n_holidays == 11  # external calendar fact (test_holidays.py)
        assert date(2025, 12, 25) in {d.date for d in cmp.holidays}
        assert date(2026, 6, 4) in {d.date for d in cmp.holidays}
        dec = next(m for m in report.months if m.month == "2025-12")
        assert dec.n_bw_holidays == 2
        aug = next(m for m in report.months if m.month == "2026-08")
        assert aug.n_bw_holidays == 0  # summer peak is NOT holiday-driven


class TestGroupingPins:
    def test_grouping_covers_all_series(self, dataset) -> None:
        features = compute_series_features(dataset.readings)
        result = cluster_or_tier(features)
        assert result.method in {"kmeans", "rule_tiers"}
        assert len(result.labels) == 1338  # every series labelled, none dropped
        if result.method == "kmeans":
            assert result.chosen_k in (2, 3, 4)
            assert all(result.gate.values())
        else:
            assert result.chosen_k is None
        assert result.n_eligible + result.n_excluded_insufficient == 1338


class TestFullReportRun:
    def test_real_report_builds_with_figures(self, dataset, tmp_path: Path) -> None:
        text = build_report(REAL_CSV_PATH, tmp_path, require_real=True)
        assert text.startswith(f"FILE: {REAL_CSV_PATH}")
        assert "ROWS: 11701 rows" in text
        assert len(list(tmp_path.glob("*.png"))) == 6
        # BW holidays in span are exactly the 11 external-calendar dates.
        expected = sorted(
            h.date for h in bw_holidays_in_range(date(2025, 10, 17), date(2026, 9, 30))
        )
        assert len(expected) == 11
