"""Per-series accumulation features (M3) — descriptive statistics only.

Builds behavioural features per glass-fill series (`Location_id` x
`material_type`) from the canonical readings (docs/contracts.md §1):

- gaps: day counts between consecutive readings of a series (any kind);
- fill deltas and a *fill-rate proxy* (percentage points per day) only over
  consecutive numeric-numeric reading pairs; `overfull` (fill None) breaks a
  pair and is never coerced to a number (contract §1.1 non-decision);
- reading semantics are unresolved (docs/data_profile.md §13.1): whether an
  increase means accumulation and a decrease means a collection is a
  *hypothesis*, not a fact. Everything here is descriptive; no causal claim is
  made anywhere in this module.

Deterministic and order-independent: readings are sorted by series key and
date internally, so results do not depend on source row order.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

from integrations.kaise.data.schema import MaterialType, ReadingRecord

FULL_FILL_PCT = 100  # percent; numeric value, distinct from the "overfull" token


@dataclass(frozen=True)
class SeriesFeatures:
    """Descriptive behavioural features of one series.

    Units: fills/means/deltas in percent or percentage points; gaps/span in
    days; rates in percentage points per day. Shares are fractions in [0, 1]
    with denominator n_readings (all readings, overfull included).
    """

    location_id: str
    material_type: MaterialType
    n_readings: int
    n_numeric: int
    n_overfull: int
    first_date: date
    last_date: date
    span_days: int
    median_gap_days: float | None  # None for single-reading series
    mean_gap_days: float | None
    mean_fill_pct: float | None  # numeric readings only
    overfull_share: float
    share_at_100: float
    mean_delta_pct: float | None  # percentage points per numeric pair
    median_rate_pct_per_day: float | None
    mean_positive_rate_pct_per_day: float | None
    mean_negative_rate_pct_per_day: float | None
    n_increase_pairs: int
    n_decrease_events: int


@dataclass(frozen=True)
class AccumulationSummary:
    """Dataset-level aggregates over all numeric-numeric consecutive pairs.

    Zero-denominator cases return 0.0 shares/means; the positive/negative mean
    rates are None when no pair of that sign exists.
    """

    n_pairs: int
    n_series_with_pairs: int
    share_increasing_pairs: float
    share_decreasing_pairs: float
    share_flat_pairs: float
    mean_delta_pct: float
    median_delta_pct: float
    median_rate_pct_per_day: float
    mean_positive_rate_pct_per_day: float | None
    mean_negative_rate_pct_per_day: float | None


def _series_key(reading: ReadingRecord) -> tuple[str, MaterialType]:
    return (reading.location_id, reading.material_type)


def compute_series_features(readings: list[ReadingRecord]) -> list[SeriesFeatures]:
    """One SeriesFeatures per series, sorted by (location_id, material_type)."""
    grouped: dict[tuple[str, MaterialType], list[ReadingRecord]] = {}
    for reading in readings:
        grouped.setdefault(_series_key(reading), []).append(reading)
    features = [
        _features_for_series(key[0], key[1], sorted(rows, key=lambda r: r.date))
        for key, rows in sorted(grouped.items())
    ]
    return features


def _features_for_series(
    location_id: str, material_type: MaterialType, ordered: list[ReadingRecord]
) -> SeriesFeatures:
    n_readings = len(ordered)
    fills_numeric = [r.fill_level_pct for r in ordered if r.fill_level_pct is not None]
    n_overfull = sum(1 for r in ordered if r.is_overfull)
    first_date, last_date = ordered[0].date, ordered[-1].date

    gap_days = [(later.date - earlier.date).days for earlier, later in pairwise(ordered)]
    # Numeric-numeric consecutive pairs only; overfull readings break pairs.
    pairs = _series_pairs(ordered)
    deltas_pct = [delta for delta, _ in pairs]
    rates_pct_per_day = [rate for _, rate in pairs]

    return SeriesFeatures(
        location_id=location_id,
        material_type=material_type,
        n_readings=n_readings,
        n_numeric=len(fills_numeric),
        n_overfull=n_overfull,
        first_date=first_date,
        last_date=last_date,
        span_days=(last_date - first_date).days,
        median_gap_days=float(statistics.median(gap_days)) if gap_days else None,
        mean_gap_days=float(statistics.mean(gap_days)) if gap_days else None,
        mean_fill_pct=float(statistics.mean(fills_numeric)) if fills_numeric else None,
        overfull_share=n_overfull / n_readings,
        share_at_100=sum(1 for v in fills_numeric if v == FULL_FILL_PCT) / n_readings,
        mean_delta_pct=float(statistics.mean(deltas_pct)) if deltas_pct else None,
        median_rate_pct_per_day=(
            float(statistics.median(rates_pct_per_day)) if rates_pct_per_day else None
        ),
        mean_positive_rate_pct_per_day=_mean_of_sign(rates_pct_per_day, positive=True),
        mean_negative_rate_pct_per_day=_mean_of_sign(rates_pct_per_day, positive=False),
        n_increase_pairs=sum(1 for d in deltas_pct if d > 0),
        n_decrease_events=sum(1 for d in deltas_pct if d < 0),
    )


def _mean_of_sign(values: list[float], positive: bool) -> float | None:
    selected = [v for v in values if (v > 0 if positive else v < 0)]
    return float(statistics.mean(selected)) if selected else None


def compute_accumulation_summary(readings: list[ReadingRecord]) -> AccumulationSummary:
    """Aggregate all numeric-numeric consecutive pairs across the dataset."""
    ordered_by_series: dict[tuple[str, str], list[ReadingRecord]] = {}
    for reading in readings:
        ordered_by_series.setdefault(_series_key(reading), []).append(reading)
    deltas: list[float] = []
    rates: list[float] = []
    series_with_pairs = 0
    for rows in ordered_by_series.values():
        series_deltas = _series_pairs(sorted(rows, key=lambda r: r.date))
        if series_deltas:
            series_with_pairs += 1
            deltas.extend(d for d, _ in series_deltas)
            rates.extend(r for _, r in series_deltas)

    n_pairs = len(deltas)
    if n_pairs == 0:
        return AccumulationSummary(
            n_pairs=0,
            n_series_with_pairs=0,
            share_increasing_pairs=0.0,
            share_decreasing_pairs=0.0,
            share_flat_pairs=0.0,
            mean_delta_pct=0.0,
            median_delta_pct=0.0,
            median_rate_pct_per_day=0.0,
            mean_positive_rate_pct_per_day=None,
            mean_negative_rate_pct_per_day=None,
        )
    positive = [r for r in rates if r > 0]
    negative = [r for r in rates if r < 0]
    return AccumulationSummary(
        n_pairs=n_pairs,
        n_series_with_pairs=series_with_pairs,
        share_increasing_pairs=sum(1 for d in deltas if d > 0) / n_pairs,
        share_decreasing_pairs=sum(1 for d in deltas if d < 0) / n_pairs,
        share_flat_pairs=sum(1 for d in deltas if d == 0) / n_pairs,
        mean_delta_pct=float(statistics.mean(deltas)),
        median_delta_pct=float(statistics.median(deltas)),
        median_rate_pct_per_day=float(statistics.median(rates)),
        mean_positive_rate_pct_per_day=float(statistics.mean(positive)) if positive else None,
        mean_negative_rate_pct_per_day=float(statistics.mean(negative)) if negative else None,
    )


def _series_pairs(ordered: list[ReadingRecord]) -> list[tuple[float, float]]:
    """(delta_pct, rate_pct_per_day) of one date-ordered series; overfull breaks pairs."""
    pairs: list[tuple[float, float]] = []
    for earlier, later in pairwise(ordered):
        if earlier.fill_level_pct is None or later.fill_level_pct is None:
            continue
        days = (later.date - earlier.date).days
        delta = float(later.fill_level_pct - earlier.fill_level_pct)
        pairs.append((delta, delta / days))
    return pairs


def collect_numeric_pairs(readings: list[ReadingRecord]) -> list[tuple[int, float, float]]:
    """All numeric-numeric consecutive pairs dataset-wide: (gap_days, delta_pct, rate).

    Descriptive only — see module docstring on unresolved reading semantics.
    """
    ordered_by_series: dict[tuple[str, MaterialType], list[ReadingRecord]] = {}
    for reading in readings:
        ordered_by_series.setdefault(_series_key(reading), []).append(reading)
    collected: list[tuple[int, float, float]] = []
    for rows in ordered_by_series.values():
        for earlier, later in pairwise(sorted(rows, key=lambda r: r.date)):
            if earlier.fill_level_pct is None or later.fill_level_pct is None:
                continue
            days = (later.date - earlier.date).days
            delta = float(later.fill_level_pct - earlier.fill_level_pct)
            collected.append((days, delta, delta / days))
    return collected


def collect_gaps_days(readings: list[ReadingRecord]) -> list[int]:
    """Day gaps between consecutive readings (any kind) per series, sorted by date."""
    ordered_by_series: dict[tuple[str, MaterialType], list[ReadingRecord]] = {}
    for reading in readings:
        ordered_by_series.setdefault(_series_key(reading), []).append(reading)
    gaps: list[int] = []
    for rows in ordered_by_series.values():
        gaps.extend((later.date - earlier.date).days for earlier, later in pairwise(rows))
    return gaps
