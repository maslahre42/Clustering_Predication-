"""Stop-selection policy (M7) — docs/contracts.md §3.

Turns one forecast batch (contract §2.2) plus the series universe into
candidate collection stops, explaining every selected and skipped container.
Nothing is silently dropped: every universe series appears exactly once in
``selected`` or ``skipped``; batch/universe inconsistencies and invalid config
are errors, never partial output (§3.4).

Selection rule (§3.2): selected iff
``predicted_state == "overfull" and overfull_always_selected``
or ``predicted_fill_pct + uncertainty_buffer_pct >= select_threshold_pct``.
When both rules select, ``overfull_state`` is the reported reason (the
override is the deciding cause); with the override off, an overfull series is
judged on its numeric fallback value only (the token itself is never coerced,
contract §1.1).

Every default in :class:`PolicyConfig` is a **[demo assumption]** — the
challenge brief names variable categories only, no values (contract §3).
Deterministic: same inputs + config ⇒ identical output; no randomness.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, TypeAlias

from src.data.schema import MaterialType
from src.forecasting.baseline import ForecastRecord, PredictedState
from src.forecasting.features import SeriesKey

__all__ = [
    "Candidate",
    "PolicyConfig",
    "PolicyConfigError",
    "PolicySelectionError",
    "ReasonCode",
    "SelectionResult",
    "Skip",
    "select_candidates",
]

ReasonCode: TypeAlias = Literal[
    "at_or_above_threshold",
    "overfull_state",
    "below_threshold",
    "no_forecast",
]

REASON_AT_OR_ABOVE_THRESHOLD: ReasonCode = "at_or_above_threshold"
REASON_OVERFULL_STATE: ReasonCode = "overfull_state"
REASON_BELOW_THRESHOLD: ReasonCode = "below_threshold"
REASON_NO_FORECAST: ReasonCode = "no_forecast"

# Percent bounds for select_threshold_pct / uncertainty_buffer_pct (§3.1).
PCT_MIN = 0  # percent, inclusive
PCT_MAX = 100  # percent, inclusive


class PolicyConfigError(ValueError):
    """Raised for out-of-range or non-integer policy configuration (§3.1)."""


class PolicySelectionError(ValueError):
    """Raised when the forecast batch and universe are inconsistent (§3.4)."""


@dataclass(frozen=True)
class PolicyConfig:
    """Selection thresholds — contract §3.1.

    All defaults are **[demo assumption]** (brief names categories only):
    ``select_threshold_pct`` aligns with the §2.4 state-metric default;
    the uncertainty buffer defaults to off; overfull containers default to
    always selected. Validated at construction; invalid values raise
    :class:`PolicyConfigError` before any selection can run.
    """

    select_threshold_pct: int = 80  # percent in [0, 100] [demo assumption]
    uncertainty_buffer_pct: int = 0  # percent in [0, 100] [demo assumption]
    overfull_always_selected: bool = True  # [demo assumption]

    def __post_init__(self) -> None:
        _validate_percent("select_threshold_pct", self.select_threshold_pct)
        _validate_percent("uncertainty_buffer_pct", self.uncertainty_buffer_pct)
        if not isinstance(self.overfull_always_selected, bool):
            raise PolicyConfigError(
                f"overfull_always_selected must be bool, "
                f"got {type(self.overfull_always_selected).__name__}"
            )


@dataclass(frozen=True)
class Candidate:
    """One selected stop — contract §3.3."""

    location_id: str
    material_type: MaterialType
    predicted_fill_pct: float  # percent
    predicted_state: PredictedState
    reason_code: ReasonCode
    detail: str  # deterministic, carries the deciding numbers


@dataclass(frozen=True)
class Skip:
    """One skipped container with an explanation — contract §3.3."""

    location_id: str
    material_type: MaterialType
    predicted_fill_pct: float | None  # None iff reason_code == "no_forecast"
    predicted_state: PredictedState | None
    reason_code: ReasonCode
    detail: str


@dataclass(frozen=True)
class SelectionResult:
    """Batch-level selection output — contract §3.3.

    ``as_of_date``/``target_date`` come from the batch; ``None`` iff the
    batch (and therefore the universe in normal use) is empty.
    """

    as_of_date: date | None
    target_date: date | None
    config: PolicyConfig
    selected: list[Candidate]  # predicted_fill_pct desc, ties by key
    skipped: list[Skip]  # (location_id, material_type) ascending


def select_candidates(
    universe: Iterable[SeriesKey],
    forecasts: Mapping[SeriesKey, ForecastRecord],
    config: PolicyConfig,
) -> SelectionResult:
    """Select candidate stops from one forecast batch (contract §3.2/§3.3)."""
    universe_keys = _validated_universe(universe)
    as_of_date, target_date = _validated_batch(forecasts, universe_keys)

    selected: list[Candidate] = []
    skipped: list[Skip] = []
    for key in sorted(universe_keys):
        forecast = forecasts.get(key)
        if forecast is None:
            skipped.append(_no_forecast_skip(key))
            continue
        entry = _decide(key, forecast, config)
        if isinstance(entry, Candidate):
            selected.append(entry)
        else:
            skipped.append(entry)

    selected.sort(key=_candidate_sort_key)
    skipped.sort(key=_skip_sort_key)
    return SelectionResult(
        as_of_date=as_of_date,
        target_date=target_date,
        config=config,
        selected=selected,
        skipped=skipped,
    )


# ---------------------------------------------------------------------------
# Validation helpers (errors before any selection output)
# ---------------------------------------------------------------------------


def _validate_percent(field_name: str, value: int) -> None:
    """Percent fields must be true ints (bool excluded) in [0, 100]."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise PolicyConfigError(f"{field_name} must be an int percent, got {type(value).__name__}")
    if not PCT_MIN <= value <= PCT_MAX:
        raise PolicyConfigError(
            f"{field_name} must be in [{PCT_MIN}, {PCT_MAX}] percent, got {value}"
        )


def _validated_universe(universe: Iterable[SeriesKey]) -> set[SeriesKey]:
    keys: set[SeriesKey] = set()
    for key in universe:
        if key in keys:
            raise PolicySelectionError(
                f"duplicate universe series {key}; "
                f"the exactly-once invariant (§3.4) requires unique keys"
            )
        keys.add(key)
    return keys


def _validated_batch(
    forecasts: Mapping[SeriesKey, ForecastRecord],
    universe_keys: set[SeriesKey],
) -> tuple[date | None, date | None]:
    """Check batch/universe consistency; return (as_of, target) or (None, None)."""
    for key, _forecast in forecasts.items():
        if key not in universe_keys:
            raise PolicySelectionError(
                f"forecast key {key} not in universe; no partial output is produced"
            )
    if not forecasts:
        return (None, None)
    as_of_dates = {forecast.as_of_date for forecast in forecasts.values()}
    target_dates = {forecast.target_date for forecast in forecasts.values()}
    if len(as_of_dates) > 1 or len(target_dates) > 1:
        raise PolicySelectionError(
            f"forecast batch must share one as_of_date and one target_date, "
            f"got as_of={sorted(as_of_dates)}, target={sorted(target_dates)}"
        )
    batch = next(iter(forecasts.values()))
    return (batch.as_of_date, batch.target_date)


# ---------------------------------------------------------------------------
# Decision helpers
# ---------------------------------------------------------------------------


def _decide(key: SeriesKey, forecast: ForecastRecord, config: PolicyConfig) -> Candidate | Skip:
    meets_threshold = (
        forecast.predicted_fill_pct + config.uncertainty_buffer_pct >= config.select_threshold_pct
    )
    overfull_rule = forecast.predicted_state == "overfull" and config.overfull_always_selected
    location_id, material_type = key

    if overfull_rule:
        return Candidate(
            location_id=location_id,
            material_type=material_type,
            predicted_fill_pct=forecast.predicted_fill_pct,
            predicted_state=forecast.predicted_state,
            reason_code=REASON_OVERFULL_STATE,
            detail=(
                f"predicted_state='overfull' and overfull_always_selected=True "
                f"(predicted {_format_pct(forecast.predicted_fill_pct)}, "
                f"threshold {config.select_threshold_pct} + buffer {config.uncertainty_buffer_pct})"
            ),
        )
    if meets_threshold:
        return Candidate(
            location_id=location_id,
            material_type=material_type,
            predicted_fill_pct=forecast.predicted_fill_pct,
            predicted_state=forecast.predicted_state,
            reason_code=REASON_AT_OR_ABOVE_THRESHOLD,
            detail=(
                f"predicted {_format_pct(forecast.predicted_fill_pct)} >= "
                f"threshold {config.select_threshold_pct} + buffer {config.uncertainty_buffer_pct}"
            ),
        )
    return Skip(
        location_id=location_id,
        material_type=material_type,
        predicted_fill_pct=forecast.predicted_fill_pct,
        predicted_state=forecast.predicted_state,
        reason_code=REASON_BELOW_THRESHOLD,
        detail=(
            f"predicted {_format_pct(forecast.predicted_fill_pct)} < "
            f"threshold {config.select_threshold_pct} + buffer {config.uncertainty_buffer_pct}"
        ),
    )


def _no_forecast_skip(key: SeriesKey) -> Skip:
    """Series in the universe without a forecast record (§3.4, e.g. an
    overfull-only history has no numeric fill to persist)."""
    location_id, material_type = key
    return Skip(
        location_id=location_id,
        material_type=material_type,
        predicted_fill_pct=None,
        predicted_state=None,
        reason_code=REASON_NO_FORECAST,
        detail="no forecast record for series (e.g. no numeric history to forecast from)",
    )


def _format_pct(value: float) -> str:
    """One decimal (contract detail example '92.0'); full precision kept when
    rounding would change the number."""
    one_decimal = f"{value:.1f}"
    if float(one_decimal) == value:
        return one_decimal
    return f"{value:.4f}"


def _candidate_sort_key(candidate: Candidate) -> tuple[float, str, MaterialType]:
    return (-candidate.predicted_fill_pct, candidate.location_id, candidate.material_type)


def _skip_sort_key(skip: Skip) -> tuple[str, MaterialType]:
    return (skip.location_id, skip.material_type)
