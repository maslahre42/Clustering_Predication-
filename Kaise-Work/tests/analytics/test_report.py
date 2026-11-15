"""Tests for src.analytics.report — entry point wiring (SYNTHETIC fixtures).

The real-dataset aggregate pins live in tests/analytics/test_real_csv_aggregates.py.
Here we verify: compact text output, figure writing, and the synthetic-id guard
(build_report refuses tests/fixtures data unless explicitly allowed).
"""

from pathlib import Path

import pytest

from src.analytics.report import DEFAULT_FIGURES_DIR, build_report

FIXTURE = Path("tests/fixtures/synthetic_seasonality.csv")


class TestBuildReportOnSyntheticFixture:
    def test_report_text_and_figures(self, tmp_path: Path) -> None:
        figures_dir = tmp_path / "figs"
        text = build_report(FIXTURE, figures_dir, require_real=False)
        assert text.startswith("FILE: ")
        assert "ROWS: " in text
        assert "COORDINATES: " in text
        assert "GROUPING: method=" in text
        assert "HOLIDAYS(BW, EXTERNAL CALENDAR INPUT): n=10" in text
        assert "FIGURES: " in text
        written = list(figures_dir.glob("*.png"))
        assert len(written) == 6

    def test_synthetic_ids_are_rejected_by_default(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="SYNTHETIC-"):
            build_report(FIXTURE, tmp_path)


class TestDefaults:
    def test_default_figures_dir_is_docs(self) -> None:
        assert str(DEFAULT_FIGURES_DIR) == "docs/figures"
