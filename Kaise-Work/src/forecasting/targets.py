"""Evaluation targets (M5) — docs/contracts.md §2.1.

Operational question (contract §2.1): *what will the fill level of a series
be at its next observed reading after the prediction date?* Readings exist
only on observation dates [observed, profile §14], so evaluation happens at
observed readings: for every reading of a series with at least one prior
reading, ``as_of_date`` is the previous reading's date, ``target_date`` is
the reading itself and the truth is its observed value/state.

``as_of_date`` = previous reading date keeps the feature norm exact (§2.2):
all readings ``<= as_of_date`` are usable, the target reading is strictly
after it, so no target information can leak. Series need >= 1 prior reading;
first readings are skipped. Overfull truths stay ``(fill=None, overfull)``
— never coerced to a number (§2.4).

Output is deterministic: cases are sorted by (location_id, material_type,
target_date).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from src.data.schema import Dataset, MaterialType
from src.forecasting.features import FeatureRow, build_feature_row, group_by_series

__all__ = ["EvaluationCase", "build_evaluation_cases"]


@dataclass(frozen=True)
class EvaluationCase:
    """One evaluation target with its prediction-time features (contract §2.1).

    ``truth_fill_pct`` is percent or ``None``; ``None`` exactly when
    ``truth_is_overfull`` is True (the token is preserved, §1.1/§2.4).
    ``horizon_days = (target_date - as_of_date).days >= 1``.
    """

    location_id: str
    material_type: MaterialType
    as_of_date: date
    target_date: date
    horizon_days: int
    truth_fill_pct: int | None
    truth_is_overfull: bool
    features: FeatureRow


def build_evaluation_cases(dataset: Dataset) -> list[EvaluationCase]:
    """Build all evaluation cases of a dataset (one per reading with a prior).

    Deterministic order; empty dataset yields an empty list. Cases whose
    history contains no numeric reading are kept (they are still valid
    overfull-truth coverage) — baselines report them as unforecastable and
    evaluation counts them separately (evaluation.py).
    """
    cases: list[EvaluationCase] = []
    for (location_id, material_type), readings in sorted(group_by_series(dataset.readings).items()):
        ordered = sorted(readings, key=lambda reading: reading.date)
        for previous, target in pairwise(ordered):
            features = build_feature_row(ordered, previous.date)
            if features is None:  # unreachable: previous is itself <= previous.date
                continue
            cases.append(
                EvaluationCase(
                    location_id=location_id,
                    material_type=material_type,
                    as_of_date=previous.date,
                    target_date=target.date,
                    horizon_days=(target.date - previous.date).days,
                    truth_fill_pct=target.fill_level_pct,
                    truth_is_overfull=target.is_overfull,
                    features=features,
                )
            )
    cases.sort(key=lambda case: (case.location_id, case.material_type, case.target_date))
    return cases
