"""Tests for src.analytics.figures — Agg rendering on SYNTHETIC data only.

Figures for the real dataset are produced by `python -m src.analytics.report`
(docs/figures/); tests here never touch that directory.
"""

from pathlib import Path

from src.analytics.figures import write_figures
from src.analytics.grouping import cluster_or_tier
from src.analytics.seasonality import compute_seasonality
from src.analytics.series_features import (
    collect_gaps_days,
    collect_numeric_pairs,
    compute_series_features,
)
from src.data.loader import load_glass_fill_csv

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
EXPECTED_FIGURES = (
    "fig_monthly_readings_holidays.png",
    "fig_fill_value_distribution.png",
    "fig_gap_days_distribution.png",
    "fig_delta_vs_gap_scatter.png",
    "fig_weekday_rates.png",
    "fig_grouping_profiles.png",
)


def _load(name: str):
    result = load_glass_fill_csv(Path("tests/fixtures") / name)
    assert not result.errors
    return result.dataset.readings


class TestWriteFigures:
    def test_renders_all_pngs_with_magic_bytes(self, tmp_path: Path) -> None:
        readings = _load("synthetic_seasonality.csv")
        seasonality = compute_seasonality(readings)
        features = compute_series_features(readings)
        grouping = cluster_or_tier(features)
        paths = write_figures(
            out_dir=tmp_path,
            seasonality=seasonality,
            readings=readings,
            gaps_days=collect_gaps_days(readings),
            numeric_pairs=collect_numeric_pairs(readings),
            grouping=grouping,
        )
        assert [p.name for p in paths] == list(EXPECTED_FIGURES)
        for path in paths:
            assert path.read_bytes().startswith(PNG_MAGIC)
            assert path.stat().st_size > 500

    def test_creates_missing_directory(self, tmp_path: Path) -> None:
        readings = _load("synthetic_accumulation.csv")
        nested = tmp_path / "a" / "b"
        seasonality = compute_seasonality(readings)
        features = compute_series_features(readings)
        paths = write_figures(
            out_dir=nested,
            seasonality=seasonality,
            readings=readings,
            gaps_days=collect_gaps_days(readings),
            numeric_pairs=collect_numeric_pairs(readings),
            grouping=cluster_or_tier(features),
        )
        assert all(p.exists() for p in paths)
