"""Tests for src.analytics.spatial — M4 coordinate finding + synthetic isolation.

The coordinate absence asserted here is an OBSERVED fact about the canonical
schema (docs/data_profile.md §13.8); the SYNTHETIC- prefix convention is the
M4 isolation contract (tests/fixtures/README.md).
"""

from pathlib import Path

import pytest

from src.analytics.spatial import (
    SYNTHETIC_ID_PREFIX,
    describe_coordinate_availability,
    is_synthetic_id,
    require_real_ids,
)
from src.data.loader import load_glass_fill_csv
from src.data.schema import Dataset, ReadingRecord

FIXTURES = Path("tests/fixtures")


def _fixture_dataset(name: str) -> Dataset:
    result = load_glass_fill_csv(FIXTURES / name)
    assert not result.errors
    return result.dataset


def _real_style_record(location: str) -> ReadingRecord:
    return ReadingRecord(
        location_id=location,
        material_type="brown",
        date=__import__("datetime").date(2026, 1, 1),
        fill_level_pct=50,
        is_overfull=False,
    )


class TestSyntheticIdConvention:
    def test_prefix_detection(self) -> None:
        assert is_synthetic_id("SYNTHETIC-acc-1")
        assert is_synthetic_id(SYNTHETIC_ID_PREFIX)
        assert not is_synthetic_id("0004c095-29ec-4d5f-9c1f-3c9d2e1a7b88")
        assert not is_synthetic_id("synthetic-acc-1")  # case-sensitive prefix
        assert not is_synthetic_id("loc-SYNTHETIC-1")  # prefix only counts at start

    def test_fixture_ids_all_synthetic(self) -> None:
        dataset = _fixture_dataset("synthetic_accumulation.csv")
        assert all(is_synthetic_id(r.location_id) for r in dataset.readings)

    def test_require_real_ids_passes_on_real_style_ids(self) -> None:
        readings = [_real_style_record(f"{i:08x}-1111-2222-3333-444444444444") for i in range(3)]
        require_real_ids(readings)  # must not raise

    def test_require_real_ids_raises_on_synthetic(self) -> None:
        dataset = _fixture_dataset("synthetic_accumulation.csv")
        with pytest.raises(ValueError, match=SYNTHETIC_ID_PREFIX) as excinfo:
            require_real_ids(dataset.readings)
        assert "SYNTHETIC-acc-1" in str(excinfo.value)


class TestCoordinateAvailability:
    def test_canonical_schema_has_no_coordinate_fields(self) -> None:
        availability = describe_coordinate_availability(
            _fixture_dataset("synthetic_accumulation.csv")
        )
        assert availability.n_coordinate_fields == 0
        assert availability.coordinate_fields == ()
        assert "no coordinates" in availability.statement
