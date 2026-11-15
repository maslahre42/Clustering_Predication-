"""Compact M5 baseline report on the real challenge CSV (M5 entry point).

Usage:
    .venv/bin/python -m src.forecasting.report [CSV_PATH]

Loads the CSV through the canonical loader (contract §1), refuses synthetic
fixture ids (src.analytics.spatial.require_real_ids), builds evaluation
targets/features (contract §2.1/§2.2), evaluates both deterministic
baselines on the chronological splits (contract §2.4) and prints compact
one-line-per-cell metrics. No figures, no model fitting, no network.

Every number printed is OBSERVED from the loaded dataset, except the
full-or-overfull threshold, which is a **[demo assumption]** (80 percent
default, configurable via --threshold).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.analytics.spatial import require_real_ids
from src.data.loader import load_glass_fill_csv
from src.forecasting.evaluation import (
    DEFAULT_FULL_THRESHOLD_PCT,
    REPORT_SPLITS,
    SplitMetrics,
    assign_split,
    evaluate,
)
from src.forecasting.targets import build_evaluation_cases

DEFAULT_CSV = Path("data/raw/glass_fill_levels_anonymized_f.csv")


def main(argv: list[str] | None = None) -> int:
    """Run the M5 report; exit 0 on success, 1 on loader errors."""
    parser = argparse.ArgumentParser(description="M5 persistence/rate baseline report")
    parser.add_argument("csv_path", nargs="?", default=DEFAULT_CSV, type=Path)
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_FULL_THRESHOLD_PCT,
        help="full-or-overfull threshold in percent [demo assumption]",
    )
    args = parser.parse_args(argv)

    result = load_glass_fill_csv(args.csv_path)
    if result.errors:
        print(
            f"loader errors: {len(result.errors)} (first: {result.errors[0].message})",
            file=sys.stderr,
        )
        return 1
    dataset = result.dataset
    require_real_ids(dataset.readings)

    cases = build_evaluation_cases(dataset)
    by_split: dict[str, int] = {}
    for case in cases:
        by_split[assign_split(case.target_date)] = (
            by_split.get(assign_split(case.target_date), 0) + 1
        )
    metrics = evaluate(cases, threshold_pct=args.threshold)

    print(f"M5 baseline report — {args.csv_path}")
    print(
        f"cases: total={len(cases)}"
        f" train={by_split.get('train', 0)}"
        f" validation={by_split.get('validation', 0)}"
        f" test={by_split.get('test', 0)}"
    )
    for method in metrics:
        print(
            f"{method} skipped_no_prediction:"
            f" validation={metrics[method]['validation'].n_skipped_no_prediction}"
            f" test={metrics[method]['test'].n_skipped_no_prediction}"
        )
    for method in sorted(metrics):
        for split in REPORT_SPLITS:
            print(f"{method} | {split} | {_format_metrics(metrics[method][split])}")
    print(
        f"full-or-overfull threshold: {args.threshold}% [demo assumption];"
        " MAE/RMSE in percentage points on numeric truths only"
    )
    return 0


def _format_metrics(metrics: SplitMetrics) -> str:
    mae = "n/a" if metrics.mae_pct is None else f"{metrics.mae_pct:.3f}"
    rmse = "n/a" if metrics.rmse_pct is None else f"{metrics.rmse_pct:.3f}"
    c = metrics.confusion
    return (
        f"n_cases={metrics.n_cases}"
        f" numeric_truth={metrics.n_numeric_truth}"
        f" overfull_truth={metrics.n_overfull_truth}"
        f" overfull_truth_share={metrics.overfull_truth_share:.3f}"
        f" n_scored={metrics.n_scored_numeric}"
        f" mae_pct={mae}"
        f" rmse_pct={rmse}"
        f" tp={c.true_positive} fp={c.false_positive}"
        f" fn={c.false_negative} tn={c.true_negative}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
