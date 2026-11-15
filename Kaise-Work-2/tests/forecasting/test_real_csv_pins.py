"""Real-CSV pins for M5 targets/features + v4 baselines (regression; aggregates only).

Every pin is derivable from docs/data_profile.md observations or from
``src.forecasting.report`` / ``evaluate`` output (aggregate counts, no raw
rows). The raw file is never printed; synthetic ids are rejected on this path.
"""

from __future__ import annotations

import pytest

from src.analytics.spatial import require_real_ids
from src.data.loader import load_glass_fill_csv
from src.forecasting.evaluation import assign_split, evaluate
from src.forecasting.features import FeatureRow
from src.forecasting.targets import EvaluationCase, build_evaluation_cases
from tests.helpers import require_real_csv_path


@pytest.fixture(scope="module")
def cases() -> list[EvaluationCase]:
    result = load_glass_fill_csv(require_real_csv_path())
    assert not result.errors, f"real CSV must load cleanly: {result.errors[:3]}"
    require_real_ids(result.dataset.readings)
    return build_evaluation_cases(result.dataset)


class TestRealCsvPins:
    def test_total_cases_equal_rows_minus_series(self, cases) -> None:
        assert len(cases) == 10_363  # 11,701 rows - 1,338 series (profile §6/§7)

    def test_overfull_truth_cases(self, cases) -> None:
        overfull_cases = [c for c in cases if c.truth_is_overfull]
        assert len(overfull_cases) == 1_157  # overfull rows that have a prior reading

    def test_split_case_counts(self, cases) -> None:
        counts = {"train": 0, "validation": 0, "test": 0}
        for case in cases:
            counts[assign_split(case.target_date)] += 1
        assert counts == {"train": 4_571, "validation": 3_722, "test": 2_070}

    def test_unforecastable_cases_overfull_only_history(self, cases) -> None:
        skipped = [c for c in cases if c.features.last_numeric_fill_pct is None]
        assert len(skipped) == 31  # histories with no numeric reading yet

    def test_truth_token_never_coerced(self, cases) -> None:
        assert all((c.truth_fill_pct is None) == c.truth_is_overfull for c in cases)

    def test_horizons_positive_and_features_attached(self, cases) -> None:
        assert all(c.horizon_days >= 1 for c in cases)
        assert all(isinstance(c.features, FeatureRow) for c in cases)


class TestV4BaselinePins:
    """Chronological-split headline pins, v4 rate method (§2.3).

    Produced 2026-11-14 by ``evaluate`` on the real CSV (threshold 80,
    numeric truths only); recorded in docs/model_card.md. Persistence is
    unchanged from M5; rate (v4) now beats it on both splits.
    """

    def test_test_split_headline(self, cases) -> None:
        by_method = evaluate(cases)
        persistence = by_method["persistence"]["test"]
        assert persistence.n_scored_numeric == 1_943
        assert round(persistence.mae_pct, 3) == 22.764
        assert round(persistence.rmse_pct, 3) == 30.475
        rate = by_method["rate"]["test"]
        assert rate.n_scored_numeric == 1_930
        assert rate.n_skipped_no_prediction == 15
        assert round(rate.mae_pct, 3) == 20.146
        assert round(rate.rmse_pct, 3) == 25.857

    def test_validation_split_headline(self, cases) -> None:
        by_method = evaluate(cases)
        assert round(by_method["persistence"]["validation"].mae_pct, 3) == 27.658
        assert round(by_method["rate"]["validation"].mae_pct, 3) == 25.391

    def test_v4_rate_beats_persistence_on_test_mae(self, cases) -> None:
        by_method = evaluate(cases)
        assert by_method["rate"]["test"].mae_pct < by_method["persistence"]["test"].mae_pct
