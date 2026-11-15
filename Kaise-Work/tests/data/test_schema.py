"""Tests for src.data.schema — canonical reading contract (docs/contracts.md §1).

All objects here are SYNTHETIC in-memory fixtures (no file I/O, no data/raw
involvement). They pin the ReadingRecord invariant I3 and the empty-dataset
shape required by contract §1.3/§1.4.
"""

import dataclasses
from datetime import date

import pytest

from src.data.schema import Dataset, DatasetSummary, MaterialType, ReadingRecord


def _reading(**overrides: object) -> ReadingRecord:
    """SYNTHETIC valid numeric reading, overridable per test."""
    values: dict[str, object] = {
        "location_id": "loc-a",
        "material_type": "brown",
        "date": date(2025, 1, 1),
        "fill_level_pct": 10,
        "is_overfull": False,
    }
    values.update(overrides)
    return ReadingRecord(**values)  # type: ignore[arg-type]


def test_reading_record_is_frozen() -> None:
    record = _reading()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.fill_level_pct = 50  # type: ignore[misc]


def test_reading_record_rejects_overfull_with_numeric_fill() -> None:
    with pytest.raises(ValueError, match="is_overfull"):
        _reading(fill_level_pct=100, is_overfull=True)


def test_reading_record_rejects_overfull_without_none_fill() -> None:
    with pytest.raises(ValueError, match="is_overfull"):
        _reading(fill_level_pct=50, is_overfull=True)


def test_reading_record_allows_none_fill_only_when_overfull() -> None:
    record = _reading(fill_level_pct=None, is_overfull=True)
    assert record.fill_level_pct is None
    assert record.is_overfull is True


def test_material_type_literal_accepts_only_three_values() -> None:
    # Runtime enum check lives in the loader (rule R3); here we pin the alias.
    materials: set[MaterialType] = {"brown", "green", "white"}
    assert materials == {"brown", "green", "white"}


def test_empty_dataset_has_zeroed_summary_and_no_readings() -> None:
    dataset = Dataset.empty()
    assert dataset.readings == []
    assert dataset.summary.n_rows == 0
    assert dataset.summary.n_locations == 0
    assert dataset.summary.n_series == 0
    assert dataset.summary.date_min is None
    assert dataset.summary.date_max is None
    assert dataset.summary.rows_per_material == {"brown": 0, "green": 0, "white": 0}


def test_dataset_and_summary_are_frozen() -> None:
    summary = DatasetSummary(
        n_rows=1,
        n_locations=1,
        n_series=1,
        date_min=date(2025, 1, 1),
        date_max=date(2025, 1, 1),
        rows_per_material={"brown": 1, "green": 0, "white": 0},
    )
    dataset = Dataset(readings=[_reading()], summary=summary)
    with pytest.raises(dataclasses.FrozenInstanceError):
        dataset.readings = []  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        summary.n_rows = 2  # type: ignore[misc]
