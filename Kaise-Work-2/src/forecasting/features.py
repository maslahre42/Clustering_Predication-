"""Leakage-safe prediction-time features (M5, v4 semantics) — contracts §2.2/§2.3/§1.5.

Feature norm (contract §2.2): a feature row for ``as_of_date`` may use only
readings of the same series ``(location_id, material_type)`` with
``date <= as_of_date``. The target reading (strictly after ``as_of_date``)
can therefore never enter a feature.

v4 record semantics (contract §1.5, [representative-stated]): one row is one
**emptying event**; ``fill_level_pct`` is the fill observed at that emptying.
Consequences implemented here:

- Per-series accumulation rate = median over records ``r_i`` (i >= 2) with a
  positive interval ``date_i - date_{i-1}`` and numeric ``fill_i`` of
  ``fill_i / interval_days`` (``fill_at_emptying_rate_pct_per_day``). Fill
  deltas between consecutive records are NEVER used as velocity (§2.3).
- ``median_interval_days`` is the median over consecutive record intervals
  > 0; intervals are date-based, so overfull records participate (gaps do not
  depend on fill values), while they never enter the numeric rate median.

Overfull readings keep their token semantics: they count towards
``n_readings`` and ``overfull_share`` and set ``last_reading_is_overfull``,
but never contribute to numeric statistics (no coercion — contract §1.1
non-decision).

Series histories are irregular (median gap 28 d, profile §14/§18): gaps are
measured in days between actual record dates, never assumed regular.
Deterministic: readings are sorted by date internally, so results do not
depend on source row order (dates are unique within a series per invariant
I1).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import TypeAlias

from src.data.schema import MaterialType, ReadingRecord

__all__ = [
    "FeatureRow",
    "build_feature_row",
    "collect_fill_at_emptying_rates_pct_per_day",
    "collect_positive_interval_days",
    "collect_rate_candidates",
    "group_by_series",
]

SeriesKey: TypeAlias = tuple[str, MaterialType]


@dataclass(frozen=True)
class FeatureRow:
    """Prediction-time features of one series at ``as_of_date`` (contract §2.2).

    Units: fills/means/max in percent, ``fill_at_emptying_rate_pct_per_day``
    in percentage points per day, ``median_interval_days``/``days_since_last_
    reading`` in days, ``month_of_as_of`` is 1-12. ``None`` numeric statistics
    mean "not derivable from the history yet" — an explicit state, never an
    imputed number.
    """

    location_id: str
    material_type: MaterialType
    as_of_date: date
    month_of_as_of: int  # 1-12 (calendar month of as_of_date)
    n_readings: int  # emptying records with date <= as_of_date (overfull included)
    last_numeric_fill_pct: int | None  # percent; None if history has no numeric reading
    last_reading_is_overfull: bool  # most recent record <= as_of is the overfull token
    days_since_last_reading: int  # days from last record date to as_of_date
    mean_numeric_fill_pct: float | None  # percent, numeric records only
    max_numeric_fill_pct: int | None  # percent, numeric records only
    overfull_share: float  # n_overfull / n_readings, fraction in [0, 1]
    fill_at_emptying_rate_pct_per_day: float | None  # §1.5 median; None if no numeric candidate
    median_interval_days: float | None  # median consecutive interval > 0, days


def group_by_series(
    readings: list[ReadingRecord],
) -> dict[SeriesKey, list[ReadingRecord]]:
    """Group readings by ``(location_id, material_type)``, preserving row order."""
    grouped: dict[SeriesKey, list[ReadingRecord]] = {}
    for reading in readings:
        grouped.setdefault((reading.location_id, reading.material_type), []).append(reading)
    return grouped


def build_feature_row(
    series_readings: list[ReadingRecord],
    as_of_date: date,
) -> FeatureRow | None:
    """Build one series' feature row from records available at ``as_of_date``.

    Returns ``None`` when the series has no record with ``date <= as_of_date``
    (insufficient history — callers must skip the case explicitly).
    """
    history = sorted(
        (reading for reading in series_readings if reading.date <= as_of_date),
        key=lambda reading: reading.date,
    )
    if not history:
        return None

    numeric = [reading.fill_level_pct for reading in history if reading.fill_level_pct is not None]
    n_overfull = sum(1 for reading in history if reading.is_overfull)
    last = history[-1]
    rates = collect_fill_at_emptying_rates_pct_per_day(history)
    intervals = collect_positive_interval_days(history)
    return FeatureRow(
        location_id=last.location_id,
        material_type=last.material_type,
        as_of_date=as_of_date,
        month_of_as_of=as_of_date.month,
        n_readings=len(history),
        last_numeric_fill_pct=numeric[-1] if numeric else None,
        last_reading_is_overfull=last.is_overfull,
        days_since_last_reading=(as_of_date - last.date).days,
        mean_numeric_fill_pct=(statistics.fmean(numeric) if numeric else None),
        max_numeric_fill_pct=max(numeric) if numeric else None,
        overfull_share=n_overfull / len(history),
        fill_at_emptying_rate_pct_per_day=(statistics.median(rates) if rates else None),
        median_interval_days=(statistics.median(intervals) if intervals else None),
    )


def collect_rate_candidates(
    history: list[ReadingRecord],
) -> list[tuple[ReadingRecord, int]]:
    """Rate candidates (§5.2.3): records ``r_i`` (i >= 2) with ``interval_days > 0``.

    Returns ``(record, interval_days)`` pairs in date order. Overfull records
    ARE candidates (their dates matter for intervals, §5.2.3) but contribute
    no numeric rate value. The history is sorted internally, so any input
    order yields the same candidates.
    """
    ordered = sorted(history, key=lambda reading: reading.date)
    return [
        (current, (current.date - previous.date).days)
        for previous, current in pairwise(ordered)
        if current.date > previous.date
    ]


def collect_fill_at_emptying_rates_pct_per_day(history: list[ReadingRecord]) -> list[float]:
    """Per-record accumulation rates (§1.5): ``fill_i / interval_days``.

    Only candidates (``collect_rate_candidates``) with a numeric ``fill_i``
    contribute; overfull records are never coerced into the median. Interval
    is measured in days between the record and its predecessor, so a
    non-positive gap can never divide by zero.
    """
    return [
        record.fill_level_pct / interval_days
        for record, interval_days in collect_rate_candidates(history)
        if record.fill_level_pct is not None
    ]


def collect_positive_interval_days(history: list[ReadingRecord]) -> list[int]:
    """Consecutive record intervals > 0 in days, in date order (§5.2.3).

    Date-based: overfull records participate (a gap does not depend on fill
    values). Non-positive gaps (unreachable per invariant I1 — one record per
    series per day) are skipped defensively.
    """
    return [interval_days for _record, interval_days in collect_rate_candidates(history)]
