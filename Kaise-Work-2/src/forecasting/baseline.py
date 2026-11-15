"""Persistence and rate baselines (M5, v4 rate semantics) — contracts §2.2/§2.3/§1.5.

- **persistence**: numeric prediction = last observed numeric fill <= as_of.
  If the most recent record is the ``overfull`` token, ``predicted_state``
  is ``overfull`` and the numeric prediction falls back to the last numeric
  fill (the token itself is never coerced to a number, contract §1.1).
- **rate** (v4 redefinition, §2.3; wire enum value unchanged): expected fill
  at the next emptying = per-series accumulation rate per §1.5 (median of
  ``fill_at_emptying / interval_days``, intervals > 0, numeric records only)
  x the series' median observed interval, clipped to [0, 100] percent. The
  prediction therefore does not depend on ``horizon_days`` — it estimates the
  fill at the *next* emptying, which history places about one median interval
  ahead. Fill deltas between consecutive records are never used as velocity
  [representative-stated §1.5]. No usable rate (no numeric rate candidate or
  no positive interval) ⇒ **no numeric prediction** — ``None``, never a
  persistence fallback and never a default rate (§2.3).

State rule (both methods, from contract §2.2): ``overfull`` iff the most
recent record <= as_of is the token; else ``full`` iff the numeric
prediction equals 100; else ``normal``. ``full`` stays the numeric-100 state
and never merges with the overfull token (§1.1 non-decision).

Unforecastable cases (no numeric history for persistence; no usable rate for
rate) return ``None`` instead of a fabricated number; evaluation counts them
explicitly. Deterministic, no ML, no randomness (M5 scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

from src.data.schema import MaterialType
from src.forecasting.features import FeatureRow
from src.forecasting.targets import EvaluationCase

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
    """Rate baseline (§2.3 v4): rate x median interval, clipped; ``None`` if unusable."""
    features = case.features
    rate = features.fill_at_emptying_rate_pct_per_day
    median_interval = features.median_interval_days
    if rate is None or median_interval is None:
        return None  # no usable rate ⇒ no numeric prediction (§2.3), never a default
    projected = rate * median_interval
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
