"""Shared fixtures for tests/forecasting — synthetic data only here.

The fixture CSV uses SYNTHETIC- prefixed ids per the tests/fixtures/README.md
isolation convention; the real challenge CSV is loaded only by
test_real_csv_pins.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.data.loader import load_glass_fill_csv
from src.data.schema import Dataset

SYNTHETIC_FORECAST_CSV = Path("tests/fixtures/synthetic_forecast.csv")


@pytest.fixture(scope="session")
def forecast_dataset() -> Dataset:
    """Canonical dataset built from tests/fixtures/synthetic_forecast.csv."""
    result = load_glass_fill_csv(SYNTHETIC_FORECAST_CSV)
    assert not result.errors, f"synthetic fixture must load cleanly: {result.errors}"
    return result.dataset
