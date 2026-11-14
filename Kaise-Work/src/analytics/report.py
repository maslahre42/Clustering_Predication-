"""Reproducible EDA report entry point (M3/M4).

Usage:
    .venv/bin/python -m src.analytics.report [CSV_PATH] [FIGURES_DIR]

Loads the real challenge CSV through the canonical loader
(src.data.loader.load_glass_fill_csv), refuses synthetic fixture ids
(src.analytics.spatial.require_real_ids), computes all M3 aggregates
(accumulation, seasonality, grouping) plus the M4 coordinate finding, prints
compact one-fact-per-line output, and writes the figures of
docs/figures/ (titles carry units + time period). Raw files are never written;
only docs/figures/*.png is produced.

Every number printed here is OBSERVED from the loaded dataset (or EXTERNAL
CALENDAR INPUT for holiday counts); interpretation lives in docs/eda_report.md,
not in this module's output.
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.analytics.figures import write_figures
from src.analytics.grouping import GROUPING_FEATURES, GroupingResult, cluster_or_tier
from src.analytics.holidays import bw_holidays_in_range
from src.analytics.seasonality import SeasonalityReport, compute_seasonality
from src.analytics.series_features import (
    SeriesFeatures,
    collect_gaps_days,
    collect_numeric_pairs,
    compute_accumulation_summary,
    compute_series_features,
)
from src.analytics.spatial import describe_coordinate_availability, require_real_ids
from src.data.loader import load_glass_fill_csv
from src.data.schema import Dataset, MaterialType, ReadingRecord

DEFAULT_CSV = Path("data/raw/glass_fill_levels_anonymized_f.csv")
DEFAULT_FIGURES_DIR = Path("docs/figures")


@dataclass(frozen=True)
class AnalysisBundle:
    """All computed M3/M4 aggregates for one dataset (no raw rows retained)."""

    dataset: Dataset
    readings: list[ReadingRecord]
    features: list[SeriesFeatures]
    numeric_pairs: list[tuple[int, float, float]]
    gaps_days: list[int]
    seasonality: SeasonalityReport
    grouping: GroupingResult
    holiday_dates: list[date]


def compute_bundle(dataset: Dataset) -> AnalysisBundle:
    """Run all M3 aggregations; deterministic, order-independent."""
    readings = dataset.readings
    features = compute_series_features(readings)
    return AnalysisBundle(
        dataset=dataset,
        readings=readings,
        features=features,
        numeric_pairs=collect_numeric_pairs(readings),
        gaps_days=collect_gaps_days(readings),
        seasonality=compute_seasonality(readings),
        grouping=cluster_or_tier(features),
        holiday_dates=[
            h.date
            for h in bw_holidays_in_range(
                min(r.date for r in readings), max(r.date for r in readings)
            )
        ],
    )


def build_report(
    csv_path: Path = DEFAULT_CSV,
    figures_dir: Path = DEFAULT_FIGURES_DIR,
    require_real: bool = True,
) -> str:
    """Load, analyse, write figures, and return the compact report text."""
    result = load_glass_fill_csv(csv_path)
    if result.errors:
        raise ValueError(f"{csv_path} failed validation: {len(result.errors)} errors")
    dataset = result.dataset
    if require_real:
        require_real_ids(dataset.readings)
    bundle = compute_bundle(dataset)
    figure_paths = write_figures(
        out_dir=figures_dir,
        seasonality=bundle.seasonality,
        readings=dataset.readings,
        gaps_days=bundle.gaps_days,
        numeric_pairs=bundle.numeric_pairs,
        grouping=bundle.grouping,
    )
    return format_report(csv_path, dataset.summary.rows_per_material, bundle, figure_paths)


def format_report(
    csv_path: Path,
    rows_per_material: dict[MaterialType, int],
    bundle: AnalysisBundle,
    figure_paths: list[Path],
) -> str:
    """Render compact one-fact-per-line text (aggregates only, no rows)."""
    readings = bundle.readings
    summary = f"{len(readings)} rows, {rows_per_material}"
    dates = (min(r.date for r in readings), max(r.date for r in readings))
    med_gaps = [f.median_gap_days for f in bundle.features if f.median_gap_days is not None]
    mean_fills = [f.mean_fill_pct for f in bundle.features if f.mean_fill_pct is not None]
    single = sum(1 for f in bundle.features if f.n_readings == 1)
    accumulation = compute_accumulation_summary(readings)
    seasonality = bundle.seasonality
    grouping = bundle.grouping
    tier_counts: dict[str, int] = {}
    for label in grouping.labels.values():
        tier_counts[label] = tier_counts.get(label, 0) + 1
    sil_text = ", ".join(f"{k}:{v:.3f}" for k, v in sorted(grouping.silhouette_by_k.items()))
    label_counts_text = "; ".join(f"{k}={v}" for k, v in sorted(tier_counts.items()))
    lines = [
        f"FILE: {csv_path}",
        f"ROWS: {summary} (units: fill percent 0-100 + literal overfull; loader contract)",
        f"SPAN: {dates[0].isoformat()} .. {dates[1].isoformat()}",
        f"COORDINATES: {describe_coordinate_availability(bundle.dataset).statement}",
        (
            f"SERIES: n={len(bundle.features)} single_reading={single} "
            f"median_of_median_gap_days={statistics.median(med_gaps):.1f} "
            f"median_of_mean_fill_pct={statistics.median(mean_fills):.1f}"
        ),
        (
            f"ACCUMULATION numeric_pairs={accumulation.n_pairs} "
            f"share_increasing={accumulation.share_increasing_pairs:.3f} "
            f"share_decreasing={accumulation.share_decreasing_pairs:.3f} "
            f"share_flat={accumulation.share_flat_pairs:.3f} "
            f"mean_delta_pct={accumulation.mean_delta_pct:.2f} "
            f"median_rate_pct_per_day={accumulation.median_rate_pct_per_day:.4f} "
            f"mean_positive_rate={_fmt(accumulation.mean_positive_rate_pct_per_day)} "
            f"mean_negative_rate={_fmt(accumulation.mean_negative_rate_pct_per_day)}"
        ),
        f"GAPS days: n={len(bundle.gaps_days)} max={max(bundle.gaps_days)} "
        f"median={statistics.median(bundle.gaps_days):.1f}",
        (
            "MONTHS (count | mean_fill_pct | overfull_share | BW holidays): "
            + "; ".join(
                f"{m.month}={m.n_readings}|{_fmt(m.mean_fill_pct)}|"
                f"{m.overfull_share:.3f}|{m.n_bw_holidays}"
                for m in seasonality.months
            )
        ),
        (
            "SEASONS: "
            + "; ".join(
                f"{s.season}={s.n_readings}|{_fmt(s.mean_fill_pct)}|{s.overfull_share:.3f}"
                for s in seasonality.seasons
            )
        ),
        (
            "WEEKDAYS (count/day): "
            + "; ".join(f"{w.weekday}={w.readings_per_day:.2f}" for w in seasonality.weekdays)
        ),
        (
            f"HOLIDAYS(BW, EXTERNAL CALENDAR INPUT): "
            f"n={seasonality.holiday_comparison.n_holidays} "
            f"readings_per_day_on="
            f"{seasonality.holiday_comparison.readings_per_day_on_holidays:.3f} "
            f"readings_per_day_off="
            f"{seasonality.holiday_comparison.readings_per_day_on_non_holidays:.3f} "
            f"weekday_matched_ratio="
            f"{seasonality.holiday_comparison.weekday_matched_ratio:.2f}"
        ),
        f"HOLIDAY_DATES: {','.join(d.isoformat() for d in bundle.holiday_dates)}",
        (
            f"GROUPING: method={grouping.method} chosen_k={grouping.chosen_k} "
            f"gate={grouping.gate} silhouettes={{{sil_text}}} "
            f"eligible={grouping.n_eligible} insufficient={grouping.n_excluded_insufficient}"
        ),
        ("GROUPING label_counts: " + label_counts_text),
        (
            "GROUPING profiles: "
            + "; ".join(
                f"{p.label}[n={p.n_series}] "
                + ",".join(f"{name}={p.feature_medians[name]:.3f}" for name in GROUPING_FEATURES)
                for p in grouping.profiles
            )
        ),
        "FIGURES: " + ", ".join(str(p) for p in figure_paths),
    ]
    return "\n".join(lines)


def _fmt(value: float | None, digits: int = 2) -> str:
    return "None" if value is None else f"{value:.{digits}f}"


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    csv_path = Path(args[0]) if args else DEFAULT_CSV
    figures_dir = Path(args[1]) if len(args) > 1 else DEFAULT_FIGURES_DIR
    print(build_report(csv_path, figures_dir))


if __name__ == "__main__":
    main()
