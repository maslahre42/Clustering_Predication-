"""Days-to-full estimates v2 (M16) — docs/contracts.md §5.2.3, semantics §1.5.

One row is one **emptying event** [representative-stated, §1.5]; every
estimate below is derived from emptying records only. For every series
``(location_id, material_type)``:

- ``rate_pct_per_day`` is the §1.5 accumulation rate: the median over
  records ``r_i`` (i >= 2) with ``interval_days = date_i - date_{i-1} > 0``
  and numeric ``fill_i`` of ``fill_i / interval_days`` — never a
  ``Δfill/Δdays`` velocity between records. Overfull records never enter
  the numeric median.
- ``median_interval_days`` is the median over consecutive record intervals
  > 0 (date-based; overfull records participate).
- ``days_to_full = target_pct / rate`` (1 d.p.). Model assumption: the
  container refills from 0 after each emptying — echoed in ``assumptions``.
- ``predicted_full_date = last_emptying_date + round(days_to_full)`` —
  never clamped, so it may lie in the past ("overdue").
- ``is_lower_bound`` is True iff any rate candidate (record ``r_i``, i >= 2,
  interval > 0) is the overfull token or numeric ``fill_i >= 100`` (§1.5:
  censored lower bounds — true demand >= observed; never coerced). A
  numeric-100 or overfull record with a zero preceding interval is not a
  candidate and does not flag the estimate.

Reason codes — no estimate is ever fabricated; ``days_to_full`` is
``None`` exactly when ``reason`` is not ``None``:

- ``not_enough_records``: fewer than 2 records in the series.
- ``zero_interval_only``: >= 2 records but no positive interval.
- ``no_numeric_fill``: candidates exist but none has a numeric fill.
- ``zero_rate``: the numeric candidates' median rate is exactly 0 pp/day
  (all contributing fills are 0) — ``target_pct / rate`` is undefined, so
  no finite estimate exists. Fourth reason beyond the §5.2.3 v2 three:
  architect-approved addendum (2026-11-14), recorded in contracts §5.2.3;
  a number is never fabricated.

Aggregate ``stats``/``stats_by_material`` cover only series with an
estimate; ``lower_bound_share_pct`` is the share of estimates flagged
``is_lower_bound`` (1 d.p.); all days fields and the share are ``None``
when no series has an estimate. All three material keys are always present
(same convention as ``rows_per_material``, §1.3).

Deterministic: records are sorted by date internally (stable sort; I1
guarantees unique dates within a series) and series are ordered by
``(location_id, material_type)``. Same input + ``target_pct`` ⇒ identical
output.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, TypeAlias

from src.data.schema import Dataset, MaterialType, ReadingRecord
from src.forecasting.features import (
    collect_fill_at_emptying_rates_pct_per_day,
    collect_positive_interval_days,
    collect_rate_candidates,
    group_by_series,
)

__all__ = [
    "DEFAULT_TARGET_PCT",
    "DaysToFullReason",
    "DaysToFullResult",
    "DaysToFullStats",
    "SeriesDaysToFull",
    "build_days_to_full",
]

METHOD: Literal["fill_at_emptying_rate"] = "fill_at_emptying_rate"

DEFAULT_TARGET_PCT = 90  # percent [demo assumption — slide mockup]; parameter 1..100
FULL_FILL_PCT = 100  # percent; numeric 100 is a censored lower bound (§1.5)
MATERIALS: tuple[MaterialType, ...] = ("brown", "green", "white")

DaysToFullReason: TypeAlias = Literal[
    "not_enough_records",
    "zero_interval_only",
    "no_numeric_fill",
    "zero_rate",
]

REASON_NOT_ENOUGH_RECORDS: DaysToFullReason = "not_enough_records"
REASON_ZERO_INTERVAL_ONLY: DaysToFullReason = "zero_interval_only"
REASON_NO_NUMERIC_FILL: DaysToFullReason = "no_numeric_fill"
REASON_ZERO_RATE: DaysToFullReason = "zero_rate"


@dataclass(frozen=True)
class SeriesDaysToFull:
    """Days-to-full estimate of one series (contract §5.2.3 v2).

    Units: ``last_fill_pct``/``rate_pct_per_day`` in percent and percentage
    points per day, ``median_interval_days``/``days_to_full`` in days (1 d.p.
    for ``days_to_full``). ``last_fill_pct`` is ``None`` exactly when
    ``last_is_overfull`` (invariant I3). ``days_to_full``/``predicted_full_
    date`` are ``None`` exactly when ``reason`` is set.
    """

    location_id: str
    material_type: MaterialType
    last_emptying_date: date  # latest record date of the series
    last_fill_pct: int | None  # percent; None iff the last record is the overfull token
    last_is_overfull: bool
    rate_pct_per_day: float | None  # §1.5 median fill-at-emptying rate; None if no candidate
    median_interval_days: float | None  # median consecutive interval > 0; None if none
    days_to_full: float | None  # days = target_pct / rate, 1 d.p.; None iff reason set
    predicted_full_date: date | None  # last_emptying_date + round(days_to_full); never clamped
    is_lower_bound: bool  # any rate candidate >= 100 or overfull (§1.5 censored)
    reason: DaysToFullReason | None  # None iff days_to_full present


@dataclass(frozen=True)
class DaysToFullStats:
    """Aggregate stats over series with an estimate only (§5.2.3 v2).

    Days fields are exact aggregates (not re-rounded) of the per-series
    1-d.p. values; ``lower_bound_share_pct`` is rounded to 1 d.p.; all five
    estimate fields are ``None`` when no series has a value.
    """

    series_total: int
    series_with_estimate: int
    median_days: float | None
    mean_days: float | None
    min_days: float | None
    max_days: float | None
    lower_bound_share_pct: float | None  # % of estimates flagged is_lower_bound, 1 d.p.


@dataclass(frozen=True)
class DaysToFullResult:
    """Full days-to-full output (contract §5.2.3 v2).

    ``method``/``target_pct`` are the contract values; ``assumptions`` carries
    the mandatory §1.5 caveat plus the model/labelling assumptions.
    """

    method: Literal["fill_at_emptying_rate"]
    target_pct: int
    stats: DaysToFullStats
    stats_by_material: dict[MaterialType, DaysToFullStats]
    series: list[SeriesDaysToFull]
    assumptions: list[str]


def build_days_to_full(dataset: Dataset, target_pct: int = DEFAULT_TARGET_PCT) -> DaysToFullResult:
    """Days-to-full for every series of a dataset (contract §5.2.3 v2).

    ``target_pct`` must lie in 1..100 percent (validated). Deterministic
    order and values; an empty dataset yields ``series_total`` 0 with all
    estimate fields ``None``.
    """
    if not 1 <= target_pct <= 100:
        raise ValueError(f"target_pct must be in 1..100 percent, got {target_pct}")
    series = [
        _estimate_series(location_id, material_type, readings, target_pct)
        for (location_id, material_type), readings in sorted(
            group_by_series(dataset.readings).items()
        )
    ]
    return DaysToFullResult(
        method=METHOD,
        target_pct=target_pct,
        stats=_build_stats(series),
        stats_by_material={
            material: _build_stats([row for row in series if row.material_type == material])
            for material in MATERIALS
        },
        series=series,
        assumptions=_build_assumptions(target_pct),
    )


def _estimate_series(
    location_id: str,
    material_type: MaterialType,
    readings: list[ReadingRecord],
    target_pct: int,
) -> SeriesDaysToFull:
    """One series' days-to-full row with contract §5.2.3 reason precedence."""
    ordered = sorted(readings, key=lambda reading: reading.date)
    last = ordered[-1]
    candidates = collect_rate_candidates(ordered)
    rates = collect_fill_at_emptying_rates_pct_per_day(ordered)
    intervals = collect_positive_interval_days(ordered)
    is_lower_bound = _is_lower_bound(candidates)
    rate = statistics.median(rates) if rates else None
    median_interval = statistics.median(intervals) if intervals else None

    reason: DaysToFullReason | None
    days_to_full: float | None
    predicted_full_date: date | None
    if len(ordered) < 2:
        reason, days_to_full, predicted_full_date = REASON_NOT_ENOUGH_RECORDS, None, None
    elif not candidates:
        reason, days_to_full, predicted_full_date = REASON_ZERO_INTERVAL_ONLY, None, None
    elif rate is None:
        reason, days_to_full, predicted_full_date = REASON_NO_NUMERIC_FILL, None, None
    elif rate == 0:
        # target_pct / 0 undefined — never fabricate a finite estimate.
        reason, days_to_full, predicted_full_date = REASON_ZERO_RATE, None, None
    else:
        reason = None
        days_to_full = round(target_pct / rate, 1)
        predicted_full_date = last.date + timedelta(days=round(days_to_full))

    return SeriesDaysToFull(
        location_id=location_id,
        material_type=material_type,
        last_emptying_date=last.date,
        last_fill_pct=last.fill_level_pct,
        last_is_overfull=last.is_overfull,
        rate_pct_per_day=rate,
        median_interval_days=median_interval,
        days_to_full=days_to_full,
        predicted_full_date=predicted_full_date,
        is_lower_bound=is_lower_bound,
        reason=reason,
    )


def _is_lower_bound(candidates: list[tuple[ReadingRecord, int]]) -> bool:
    """True iff any rate candidate is overfull or numeric fill >= 100 (§1.5)."""
    return any(
        record.is_overfull
        or (record.fill_level_pct is not None and record.fill_level_pct >= FULL_FILL_PCT)
        for record, _interval_days in candidates
    )


def _build_stats(rows: list[SeriesDaysToFull]) -> DaysToFullStats:
    """Aggregate over series with an estimate only; nulls when none exist."""
    estimates = [row.days_to_full for row in rows if row.days_to_full is not None]
    flagged = sum(1 for row in rows if row.days_to_full is not None and row.is_lower_bound)
    return DaysToFullStats(
        series_total=len(rows),
        series_with_estimate=len(estimates),
        median_days=float(statistics.median(estimates)) if estimates else None,
        mean_days=statistics.fmean(estimates) if estimates else None,
        min_days=min(estimates) if estimates else None,
        max_days=max(estimates) if estimates else None,
        lower_bound_share_pct=(round(100 * flagged / len(estimates), 1) if estimates else None),
    )


def _build_assumptions(target_pct: int) -> list[str]:
    """Contract caveats: the mandatory §1.5 sentence plus model/labelling labels."""
    return [
        "fill at emptying shows how full the container was when the schedule "
        "reached it — not how fast it would have filled [representative-stated §1.5]",
        "rates additionally assume no unobserved emptying between records [assumption]",
        "days_to_full assumes the container refills from 0 after each emptying [model assumption]",
        f"target fill {target_pct}% [demo assumption — slide mockup]",
    ]
