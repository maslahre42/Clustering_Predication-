"""Chronological evaluation protocol (M5) — docs/contracts.md §2.4.

Split (normative, chronological only — never random row splits): train
``target_date < 2026-05-01``, validation ``2026-05-01..2026-07-31``, test
``>= 2026-08-01``. Cases are assigned by ``target_date`` (the date of the
truth being scored) — see the report note on split assignment.

Numeric metrics: MAE/RMSE in percentage points, computed **only where the
truth is numeric AND a prediction exists**; rows whose truth is the
``overfull`` token are excluded from numeric metrics and never coerced
(§2.4). Coverage honesty: every split reports the share of truths that are
overfull and the number of cases the baseline could not forecast
(persistence: overfull-only history; rate v4: additionally no usable rate —
§2.3 returns no numeric prediction then).

State confusion: "full-or-overfull vs rest" at a configurable threshold
(default 80 percent — **[demo assumption]**, not from the brief). Positive:
truth = token ``overfull`` or numeric truth >= threshold; prediction =
``overfull`` state or numeric prediction >= threshold. Cases without a
prediction (no numeric history) are counted as skipped and excluded from
both metric subsets. Deterministic throughout.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

from src.forecasting.baseline import METHOD_PERSISTENCE, METHOD_RATE, BaselineMethod, forecast
from src.forecasting.targets import EvaluationCase

__all__ = [
    "DEFAULT_FULL_THRESHOLD_PCT",
    "REPORT_SPLITS",
    "ConfusionCounts",
    "Split",
    "SplitMetrics",
    "assign_split",
    "evaluate",
    "evaluate_split",
]

DEFAULT_FULL_THRESHOLD_PCT = 80  # percent [demo assumption, contract §2.4]

TRAIN_LAST_DATE = date(2026, 4, 30)  # train: target_date <= this day
VALIDATION_FIRST_DATE = date(2026, 5, 1)
VALIDATION_LAST_DATE = date(2026, 7, 31)
TEST_FIRST_DATE = date(2026, 8, 1)

Split: TypeAlias = Literal["train", "validation", "test"]
SPLITS: tuple[Split, ...] = ("train", "validation", "test")
DEFAULT_METHODS: tuple[BaselineMethod, ...] = (METHOD_PERSISTENCE, METHOD_RATE)
# Splits printed by the report CLI (contract §2.4); train is evaluated too.
REPORT_SPLITS: tuple[Split, ...] = ("validation", "test")


@dataclass(frozen=True)
class ConfusionCounts:
    """Full-or-overfull vs rest confusion at one threshold (contract §2.4)."""

    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.false_negative + self.true_negative


@dataclass(frozen=True)
class SplitMetrics:
    """One method evaluated on one chronological split (percent units).

    ``mae_pct``/``rmse_pct`` are ``None`` when no numeric-truth case has a
    prediction. ``n_skipped_no_numeric_history`` keeps coverage honest.
    """

    split: Split
    n_cases: int
    n_numeric_truth: int
    n_overfull_truth: int
    overfull_truth_share: float  # n_overfull_truth / n_cases (0.0 when empty)
    n_skipped_no_prediction: int
    n_scored_numeric: int  # numeric truth AND prediction available
    mae_pct: float | None
    rmse_pct: float | None
    confusion: ConfusionCounts


def assign_split(target_date: date) -> Split:
    """Chronological split assignment by target date (contract §2.4)."""
    if target_date <= TRAIN_LAST_DATE:
        return "train"
    if target_date <= VALIDATION_LAST_DATE:
        return "validation"
    return "test"


def evaluate(
    cases: list[EvaluationCase],
    methods: tuple[BaselineMethod, ...] = DEFAULT_METHODS,
    threshold_pct: int = DEFAULT_FULL_THRESHOLD_PCT,
) -> dict[BaselineMethod, dict[Split, SplitMetrics]]:
    """Evaluate every method on every split (deterministic output order)."""
    return {
        method: {split: evaluate_split(cases, method, split, threshold_pct) for split in SPLITS}
        for method in methods
    }


def evaluate_split(
    cases: list[EvaluationCase],
    method: BaselineMethod,
    split: Split,
    threshold_pct: int = DEFAULT_FULL_THRESHOLD_PCT,
) -> SplitMetrics:
    """Evaluate one method on one split of evaluation cases (§2.4)."""
    split_cases = [case for case in cases if assign_split(case.target_date) == split]
    absolute_errors_pct: list[float] = []
    squared_errors_pct: list[float] = []
    n_numeric_truth = 0
    n_overfull_truth = 0
    n_skipped = 0
    confusion = ConfusionCounts(
        true_positive=0, false_positive=0, false_negative=0, true_negative=0
    )

    for case in split_cases:
        if case.truth_is_overfull:
            n_overfull_truth += 1
        else:
            n_numeric_truth += 1
        record = forecast(case, method)
        if record is None:
            n_skipped += 1
            continue
        if not case.truth_is_overfull and case.truth_fill_pct is not None:
            error_pct = record.predicted_fill_pct - case.truth_fill_pct
            absolute_errors_pct.append(abs(error_pct))
            squared_errors_pct.append(error_pct * error_pct)
        truth_positive = case.truth_is_overfull or (
            case.truth_fill_pct is not None and case.truth_fill_pct >= threshold_pct
        )
        predicted_positive = (
            record.predicted_state == "overfull" or record.predicted_fill_pct >= threshold_pct
        )
        confusion = _tally(confusion, truth_positive, predicted_positive)

    return SplitMetrics(
        split=split,
        n_cases=len(split_cases),
        n_numeric_truth=n_numeric_truth,
        n_overfull_truth=n_overfull_truth,
        overfull_truth_share=(n_overfull_truth / len(split_cases)) if split_cases else 0.0,
        n_skipped_no_prediction=n_skipped,
        n_scored_numeric=len(absolute_errors_pct),
        mae_pct=statistics.fmean(absolute_errors_pct) if absolute_errors_pct else None,
        rmse_pct=(math.sqrt(statistics.fmean(squared_errors_pct)) if squared_errors_pct else None),
        confusion=confusion,
    )


def _tally(
    confusion: ConfusionCounts,
    truth_positive: bool,
    predicted_positive: bool,
) -> ConfusionCounts:
    if truth_positive and predicted_positive:
        return ConfusionCounts(
            true_positive=confusion.true_positive + 1,
            false_positive=confusion.false_positive,
            false_negative=confusion.false_negative,
            true_negative=confusion.true_negative,
        )
    if predicted_positive:
        return ConfusionCounts(
            true_positive=confusion.true_positive,
            false_positive=confusion.false_positive + 1,
            false_negative=confusion.false_negative,
            true_negative=confusion.true_negative,
        )
    if truth_positive:
        return ConfusionCounts(
            true_positive=confusion.true_positive,
            false_positive=confusion.false_positive,
            false_negative=confusion.false_negative + 1,
            true_negative=confusion.true_negative,
        )
    return ConfusionCounts(
        true_positive=confusion.true_positive,
        false_positive=confusion.false_positive,
        false_negative=confusion.false_negative,
        true_negative=confusion.true_negative + 1,
    )
