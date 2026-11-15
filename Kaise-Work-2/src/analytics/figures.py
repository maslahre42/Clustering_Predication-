"""EDA figures (M3) — matplotlib Agg backend, PNG output.

Every figure title states the quantity, its unit and the time period covered.
Input data are the aggregates computed by the other analytics modules (all
observed from the challenge CSV via the canonical loader) plus the EXTERNAL
CALENDAR INPUT holiday counts. Nothing here is a model output.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from src.analytics.grouping import GroupingResult
from src.analytics.seasonality import SeasonalityReport
from src.data.schema import ReadingRecord

matplotlib.use("Agg")  # headless rendering (no display available)

_FILL_BINS_EDGES = list(range(0, 101, 10))  # observed decile values, percent
_MPL_NEGATIVE_COLOR = "#cc3311"
_MPL_POSITIVE_COLOR = "#4477aa"


def _period_text(seasonality: SeasonalityReport) -> str:
    return f"{seasonality.date_min.isoformat()} to {seasonality.date_max.isoformat()}"


def _save(fig: Figure, out_dir: Path, name: str) -> Path:
    path = out_dir / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def write_figures(
    out_dir: Path,
    seasonality: SeasonalityReport,
    readings: list[ReadingRecord],
    gaps_days: list[int],
    numeric_pairs: list[tuple[int, float, float]],
    grouping: GroupingResult,
) -> list[Path]:
    """Render all EDA figures into ``out_dir``; returns written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    period = _period_text(seasonality)
    paths = [
        _monthly_figures(out_dir, seasonality, period),
        _fill_distribution(out_dir, readings, period),
        _gap_distribution(out_dir, gaps_days, period),
        _delta_vs_gap_scatter(out_dir, numeric_pairs, period),
        _weekday_figures(out_dir, seasonality, period),
        _grouping_profiles(out_dir, grouping, period),
    ]
    return paths


def _monthly_figures(out_dir: Path, seasonality: SeasonalityReport, period: str) -> Path:
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    months = [m.month for m in seasonality.months]
    ax.bar(months, [m.n_readings for m in seasonality.months], color=_MPL_POSITIVE_COLOR)
    ax.set_ylabel("readings (count)")
    ax.set_title(
        f"Glass fill readings per month (count of readings), {period}, "
        f"n={seasonality.n_readings} rows"
    )
    ax2.step(
        months,
        [m.n_bw_holidays for m in seasonality.months],
        where="mid",
        color=_MPL_NEGATIVE_COLOR,
    )
    ax2.set_ylabel("BW public holidays (days)")
    ax2.set_title("EXTERNAL CALENDAR INPUT: BW public holidays per month (days)")
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    return _save(fig, out_dir, "fig_monthly_readings_holidays.png")


def _fill_distribution(out_dir: Path, readings: list[ReadingRecord], period: str) -> Path:
    numeric = [r.fill_level_pct for r in readings if r.fill_level_pct is not None]
    n_overfull = sum(1 for r in readings if r.is_overfull)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(numeric, bins=_FILL_BINS_EDGES, color=_MPL_POSITIVE_COLOR, edgecolor="white")
    ax.set_xlabel("fill level (percent, numeric readings only)")
    ax.set_ylabel("readings (count)")
    ax.set_title(
        f"Numeric fill-level distribution (percent), {period}; numeric n={len(numeric)}, "
        f"literal 'overfull' rows (not shown, never coerced): {n_overfull}"
    )
    return _save(fig, out_dir, "fig_fill_value_distribution.png")


def _gap_distribution(out_dir: Path, gaps_days: list[int], period: str) -> Path:
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(gaps_days, bins=40, color=_MPL_POSITIVE_COLOR, edgecolor="white")
    ax.set_xlabel("gap between consecutive readings (days)")
    ax.set_ylabel("gap count")
    ax.set_title(f"Consecutive-reading gap distribution (days), {period}, n={len(gaps_days)} gaps")
    return _save(fig, out_dir, "fig_gap_days_distribution.png")


def _delta_vs_gap_scatter(
    out_dir: Path, numeric_pairs: list[tuple[int, float, float]], period: str
) -> Path:
    days = [p[0] for p in numeric_pairs]
    deltas = [p[1] for p in numeric_pairs]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(days, deltas, s=6, alpha=0.35, color=_MPL_POSITIVE_COLOR)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("gap (days)")
    ax.set_ylabel("fill delta (percentage points)")
    ax.set_title(
        f"Numeric fill delta (percentage points) vs gap (days), {period}, "
        f"n={len(numeric_pairs)} pairs; reading semantics unresolved (no causal claim)"
    )
    return _save(fig, out_dir, "fig_delta_vs_gap_scatter.png")


def _weekday_figures(out_dir: Path, seasonality: SeasonalityReport, period: str) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4))
    names = [w.weekday for w in seasonality.weekdays]
    rates = [w.readings_per_day for w in seasonality.weekdays]
    ax.bar(names, rates, color=_MPL_POSITIVE_COLOR)
    ax.set_xlabel("weekday")
    ax.set_ylabel("readings per calendar day (count/day)")
    ax.set_title(f"Reading activity by weekday (count/day), {period}")
    return _save(fig, out_dir, "fig_weekday_rates.png")


def _grouping_profiles(out_dir: Path, grouping: GroupingResult, period: str) -> Path:
    labels = [p.label for p in grouping.profiles]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax.bar(labels, [p.feature_medians["mean_fill_pct"] for p in grouping.profiles])
    ax.set_ylabel("median of series mean fill (percent)")
    ax.set_title("Profile medians: mean fill (percent)")
    ax2.bar(labels, [p.feature_medians["overfull_share"] for p in grouping.profiles])
    ax2.set_ylabel("median overfull share (fraction of readings)")
    ax2.set_title("Profile medians: overfull share (fraction)")
    fig.suptitle(
        f"Grouping profiles ({grouping.method}, "
        + (f"k={grouping.chosen_k}" if grouping.chosen_k is not None else "rule tiers")
        + f"), period {period}"
    )
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return _save(fig, out_dir, "fig_grouping_profiles.png")
