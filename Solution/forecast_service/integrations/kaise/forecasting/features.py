"""Leakage-safe prediction-time features (M5) — docs/contracts.md §2.2/§2.4.

Feature norm (contract §2.2): a feature row for ``as_of_date`` may use only
readings of the same series ``(location_id, material_type)`` with
``date <= as_of_date``. The target reading (strictly after ``as_of_date``)
can therefore never enter a feature.

Overfull readings keep their token semantics: they count towards
``n_readings`` and ``overfull_share`` and set ``last_reading_is_overfull``,
but never contribute to numeric statistics (no coercion — contract §1.1
non-decision). ``median_rate_pct_per_day`` is the per-series median fill
change over numeric consecutive pairs (both readings numeric) divided by the
gap in days; it is the quantity the "rate" baseline (contract §2.3) consumes.

Series histories are irregular (median gap 28 d, profile §14/§18): gaps are
measured in days between actual reading dates, never assumed regular.
Deterministic: readings are sorted by date internally, so results do not
depend on source row order (dates are unique within a series per invariant I1).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import TypeAlias

from integrations.kaise.data.schema import MaterialType, ReadingRecord

__all__ = ["FeatureRow", "build_feature_row", "collect_numeric_rates_pct_per_day"]

SeriesKey: TypeAlias = tuple[str, MaterialType]


@dataclass(frozen=True)
class FeatureRow:
    """Prediction-time features of one series at ``as_of_date`` (contract §2.2).

    Units: fills/means/max in percent, ``median_rate_pct_per_day`` in
    percentage points per day, ``days_since_last_reading`` in days,
    ``month_of_as_of`` is 1-12. ``None`` numeric statistics mean "no numeric
    reading available yet" (overfull-only history) — an explicit state, never
    an imputed number.
    """

    location_id: str
    material_type: MaterialType
    as_of_date: date
    month_of_as_of: int  # 1-12 (calendar month of as_of_date)
    n_readings: int  # readings with date <= as_of_date (overfull included)
    last_numeric_fill_pct: int | None  # percent; None if history has no numeric reading
    last_reading_is_overfull: bool  # most recent reading <= as_of is the overfull token
    days_since_last_reading: int  # days from last reading date to as_of_date
    mean_numeric_fill_pct: float | None  # percent, numeric readings only
    max_numeric_fill_pct: int | None  # percent, numeric readings only
    overfull_share: float  # n_overfull / n_readings, fraction in [0, 1]
    median_rate_pct_per_day: float | None  # pp/day over numeric pairs; None if no pair


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
    """Build one series' feature row from readings available at ``as_of_date``.

    Returns ``None`` when the series has no reading with ``date <= as_of_date``
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
    rates = collect_numeric_rates_pct_per_day(history)
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
        median_rate_pct_per_day=(statistics.median(rates) if rates else None),
    )


def collect_numeric_rates_pct_per_day(history: list[ReadingRecord]) -> list[float]:
    """Daily fill-change rates (pp/day) over numeric consecutive pairs.

    A pair is two consecutive readings of the series in date order where both
    are numeric; an overfull reading breaks the pair and is never coerced.
    The history is sorted internally, so any input order yields the same
    rates. Gap is the day difference (>= 1: one reading per series per day,
    invariant I1); a non-positive gap is skipped defensively.
    """
    rates: list[float] = []
    ordered = sorted(history, key=lambda reading: reading.date)
    for previous, current in pairwise(ordered):
        gap_days = (current.date - previous.date).days
        if previous.fill_level_pct is None or current.fill_level_pct is None or gap_days <= 0:
            continue
        rates.append((current.fill_level_pct - previous.fill_level_pct) / gap_days)
    return rates
