"""Persistence and rate baselines (M5) — docs/contracts.md §2.2/§2.3.

- **persistence**: numeric prediction = last observed numeric fill <= as_of.
  If the most recent reading is the ``overfull`` token, ``predicted_state``
  is ``overfull`` and the numeric prediction falls back to the last numeric
  fill (the token itself is never coerced to a number, contract §1.1).
- **rate**: last numeric fill + per-series median daily rate over numeric
  consecutive pairs (features.median_rate_pct_per_day) x ``horizon_days``,
  clipped to [0, 100] percent. When the series has no numeric pair yet
  (median rate ``None``) the rate baseline **falls back to persistence** —
  documented behaviour, chosen over inventing a global default rate.

State rule (both methods, from contract §2.2): ``overfull`` iff the most
recent reading <= as_of is the token; else ``full`` iff the numeric
prediction equals 100; else ``normal``. ``full`` stays the numeric-100 state
and never merges with the overfull token (§1.1 non-decision).

Unforecastable cases (history contains no numeric reading at all) return
``None`` instead of a fabricated number; evaluation counts them explicitly.
Deterministic, no ML, no randomness (M5 scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

from integrations.kaise.data.schema import MaterialType
from integrations.kaise.forecasting.features import FeatureRow
from integrations.kaise.forecasting.targets import EvaluationCase

__all__ = [
    "METHOD_PERSISTENCE",
    "METHOD_RATE",
    "BaselineMethod",
    "ForecastRecord",
    "PredictedState",
    "forecast",
    "forecast_persistence",
    "forecast_rate",
]

METHOD_PERSISTENCE: Literal["persistence"] = "persistence"
METHOD_RATE: Literal["rate"] = "rate"
BaselineMethod: TypeAlias = Literal["persistence", "rate"]
PredictedState: TypeAlias = Literal["normal", "full", "overfull"]

FULL_FILL_PCT = 100  # percent; numeric value, distinct from the "overfull" token
FILL_MIN_PCT = 0  # percent
FILL_MAX_PCT = 100  # percent


@dataclass(frozen=True)
class ForecastRecord:
    """One baseline forecast — contract §2.2 (percent units, clipped)."""

    location_id: str
    material_type: MaterialType
    as_of_date: date
    target_date: date
    predicted_fill_pct: float  # percent, always clipped to [0, 100]
    predicted_state: PredictedState  # "full" := numeric 100; "overfull" := token
    method: BaselineMethod
    horizon_days: int  # days as_of -> target


def forecast(case: EvaluationCase, method: BaselineMethod) -> ForecastRecord | None:
    """Forecast one evaluation case with the named M5 baseline (§2.3)."""
    if method == METHOD_RATE:
        return forecast_rate(case)
    return forecast_persistence(case)


def forecast_persistence(case: EvaluationCase) -> ForecastRecord | None:
    """Persistence baseline (§2.3): last numeric fill, overfull state preserved."""
    features = case.features
    numeric = features.last_numeric_fill_pct
    if numeric is None:
        return None  # overfull-only history: no number to persist, never coerce
    return _record(case, METHOD_PERSISTENCE, float(numeric), features)


def forecast_rate(case: EvaluationCase) -> ForecastRecord | None:
    """Rate baseline (§2.3); falls back to persistence without a numeric pair."""
    features = case.features
    numeric = features.last_numeric_fill_pct
    if numeric is None:
        return None  # shared unforecastable path with persistence
    median_rate = features.median_rate_pct_per_day
    if median_rate is None:
        return _record(case, METHOD_RATE, float(numeric), features)
    projected = numeric + median_rate * case.horizon_days
    return _record(case, METHOD_RATE, _clip_pct(projected), features)


def _record(
    case: EvaluationCase,
    method: BaselineMethod,
    predicted_fill_pct: float,
    features: FeatureRow,
) -> ForecastRecord:
    return ForecastRecord(
        location_id=case.location_id,
        material_type=case.material_type,
        as_of_date=case.as_of_date,
        target_date=case.target_date,
        predicted_fill_pct=predicted_fill_pct,
        predicted_state=_predicted_state(features, predicted_fill_pct),
        method=method,
        horizon_days=case.horizon_days,
    )


def _clip_pct(value: float) -> float:
    """Clip a percent-valued prediction to the observed range [0, 100]."""
    return min(max(value, FILL_MIN_PCT), FILL_MAX_PCT)


def _predicted_state(features: FeatureRow, predicted_fill_pct: float) -> PredictedState:
    if features.last_reading_is_overfull:
        return "overfull"
    if predicted_fill_pct >= FULL_FILL_PCT:
        return "full"
    return "normal"
