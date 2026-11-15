"""Evaluation tests — split boundaries, metrics, confusion (contract §2.4).

Hand-built scenario at the default threshold 80 (persistence == rate here,
since median_rate is None -> documented persistence fallback):

- case1 truth 60 pred 70        -> err +10, truth neg / pred neg -> tn
- case2 truth 80 pred 80        -> err 0,   truth pos / pred pos -> tp
- case3 truth overfull pred 40 (state overfull) -> excluded from numeric, tp
- case4 truth 50 pred 100       -> err +50, truth neg / pred pos -> fp
"""

from __future__ import annotations

import math
from datetime import date

from src.forecasting.baseline import forecast
from src.forecasting.evaluation import ConfusionCounts, assign_split, evaluate, evaluate_split
from src.forecasting.features import FeatureRow
from src.forecasting.targets import EvaluationCase, build_evaluation_cases

SCENARIO_ABS_ERRORS = [10.0, 0.0, 50.0]
SCENARIO_TP, SCENARIO_FP, SCENARIO_FN, SCENARIO_TN = 2, 1, 0, 1


def _case(
    truth_fill_pct: int | None, last_numeric: int | None, last_overfull: bool
) -> EvaluationCase:
    features = FeatureRow(
        location_id="SYNTHETIC-f-x",
        material_type="brown",
        as_of_date=date(2026, 6, 1),
        month_of_as_of=6,
        n_readings=2,
        last_numeric_fill_pct=last_numeric,
        last_reading_is_overfull=last_overfull,
        days_since_last_reading=0,
        mean_numeric_fill_pct=float(last_numeric) if last_numeric is not None else None,
        max_numeric_fill_pct=last_numeric,
        overfull_share=0.5 if last_overfull else 0.0,
        median_rate_pct_per_day=None,  # rate falls back to persistence
    )
    return EvaluationCase(
        location_id=features.location_id,
        material_type=features.material_type,
        as_of_date=features.as_of_date,
        target_date=date(2026, 6, 15),
        horizon_days=14,
        truth_fill_pct=truth_fill_pct,
        truth_is_overfull=truth_fill_pct is None,
        features=features,
    )


def scenario_cases() -> list[EvaluationCase]:
    return [
        _case(60, 70, False),
        _case(80, 80, False),
        _case(None, 40, True),
        _case(50, 100, False),
    ]


class TestAssignSplit:
    def test_boundaries(self) -> None:
        assert assign_split(date(2025, 10, 17)) == "train"
        assert assign_split(date(2026, 4, 30)) == "train"
        assert assign_split(date(2026, 5, 1)) == "validation"
        assert assign_split(date(2026, 7, 31)) == "validation"
        assert assign_split(date(2026, 8, 1)) == "test"


class TestEvaluateSplit:
    def test_hand_computed_metrics_and_confusion(self) -> None:
        metrics = evaluate_split(scenario_cases(), "persistence", "validation")
        assert metrics.n_cases == 4
        assert metrics.n_numeric_truth == 3
        assert metrics.n_overfull_truth == 1
        assert metrics.overfull_truth_share == 0.25
        assert metrics.n_skipped_no_numeric_history == 0
        assert metrics.n_scored_numeric == 3
        assert metrics.mae_pct == sum(SCENARIO_ABS_ERRORS) / 3
        assert metrics.rmse_pct == math.sqrt(sum(e * e for e in SCENARIO_ABS_ERRORS) / 3)
        assert metrics.confusion == ConfusionCounts(
            true_positive=SCENARIO_TP,
            false_positive=SCENARIO_FP,
            false_negative=SCENARIO_FN,
            true_negative=SCENARIO_TN,
        )

    def test_threshold_is_configurable(self) -> None:
        # threshold 100: truth/pred 80 become negative (extra tn); pred 100 stays fp
        metrics = evaluate_split(scenario_cases(), "persistence", "validation", threshold_pct=100)
        assert metrics.confusion == ConfusionCounts(
            true_positive=1, false_positive=1, false_negative=0, true_negative=2
        )

    def test_skipped_cases_counted_not_scored(self) -> None:
        cases = [*scenario_cases(), _case(30, None, True)]  # overfull-only history
        metrics = evaluate_split(cases, "persistence", "validation")
        assert metrics.n_cases == 5
        assert metrics.n_skipped_no_numeric_history == 1
        assert metrics.n_scored_numeric == 3  # numeric subset unchanged

    def test_rate_equals_persistence_for_its_fallback_cases(self) -> None:
        persistence = evaluate_split(scenario_cases(), "persistence", "validation")
        rate = evaluate_split(scenario_cases(), "rate", "validation")
        assert rate.mae_pct == persistence.mae_pct
        assert rate.rmse_pct == persistence.rmse_pct

    def test_empty_split_yields_zeroed_metrics(self) -> None:
        metrics = evaluate_split([], "rate", "test")
        assert metrics.n_cases == 0
        assert metrics.overfull_truth_share == 0.0
        assert metrics.mae_pct is None
        assert metrics.rmse_pct is None
        assert metrics.confusion.total == 0

    def test_predictions_stay_in_range_and_match_target(self, forecast_dataset) -> None:
        for case in build_evaluation_cases(forecast_dataset):
            record = forecast(case, "rate")
            if record is not None:
                assert record.target_date == case.target_date
                assert 0.0 <= record.predicted_fill_pct <= 100.0


class TestEvaluate:
    def test_all_methods_and_splits_present(self, forecast_dataset) -> None:
        metrics = evaluate(build_evaluation_cases(forecast_dataset))
        assert set(metrics) == {"persistence", "rate"}
        for method in metrics:
            assert set(metrics[method]) == {"train", "validation", "test"}

    def test_fixture_split_assignment(self, forecast_dataset) -> None:
        metrics = evaluate(build_evaluation_cases(forecast_dataset))
        persistence = metrics["persistence"]
        # fixture targets 02-05..04-20 all precede 2026-05-01 -> all train
        assert persistence["train"].n_cases == 5
        assert persistence["validation"].n_cases == 0
        assert persistence["test"].n_cases == 0
        # train overfull truths: targets 2026-02-05 (a) and 2026-03-01 (c)
        assert persistence["train"].n_overfull_truth == 2
