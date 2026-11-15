"""Tests for src.data.loader — canonical CSV loader (docs/contracts.md §1).

All CSV fixtures below are SYNTHETIC and labelled as such; they are written to
tmp_path at test time. data/raw is read-only and touched by exactly one test
(test_real_csv_matches_observed_profile), which asserts only aggregates from
docs/data_profile.md §17 — the file itself is never printed or read whole.

Row-number convention asserted here: row_number is the 1-based data-row index
(header excluded); R1 header errors use row_number 0.
"""

from datetime import date
from pathlib import Path

from src.data.loader import load_glass_fill_csv
from tests.helpers import require_real_csv_path

# SYNTHETIC valid fixture, written WITH a UTF-8 BOM (mirrors the real file,
# docs/data_profile.md §1). Covers: all three materials, numeric decile fill,
# boundary values 0/100, and one literal "overfull" token (I3 transform).
SYNTHETIC_VALID_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,10
loc-a,brown,2025-01-15,overfull
loc-a,green,2025-01-01,100
loc-a,white,2025-01-01,0
loc-b,green,2025-02-02,40
"""

SYNTHETIC_R1_BAD_HEADER_CSV = """Location_id,material_type,date,fill_pct
loc-a,brown,2025-01-01,10
"""

SYNTHETIC_R2_EMPTY_FIELD_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,
loc-a,brown,2025-01-02
loc-a,brown,2025-01-03,50,extra
loc-a,brown,2025-01-04,20
"""

SYNTHETIC_R3_BAD_MATERIAL_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,10
loc-a,blue,2025-01-02,20
loc-a,BROWN,2025-01-03,30
"""

SYNTHETIC_R4_BAD_DATE_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-1-1,10
loc-a,brown,not-a-date,20
loc-a,brown,2025-02-30,30
loc-a,brown,2025-01-05T00:00:00,40
loc-a,brown,2025-01-05,50
"""

SYNTHETIC_R5_BAD_FILL_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,55.5
loc-a,brown,2025-01-02,150
loc-a,brown,2025-01-03,-10
loc-a,brown,2025-01-04,half
loc-a,brown,2025-01-05, 50
loc-a,brown,2025-01-06,100
"""

SYNTHETIC_R6_DUPLICATE_KEY_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,10
loc-a,brown,2025-01-01,10
loc-a,brown,2025-01-02,30
loc-a,brown,2025-01-02,50
"""

# SYNTHETIC R7 fixture: 55 is a valid in-range integer but not a decile, so the
# file loads WITH one warning and no errors (warning level, not error level).
SYNTHETIC_R7_NON_DECILE_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,55
"""

# SYNTHETIC mixed fixture: three distinct rules each on its own row, asserting
# the full error list is collected (no fail-fast) with correct row numbers.
SYNTHETIC_MIXED_ERRORS_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,blue,2025-01-01,10
loc-a,brown,not-a-date,20
loc-a,brown,2025-01-03,150
loc-a,brown,2025-01-04,80
"""


def _write_fixture(tmp_path: Path, text: str, bom: bool = False) -> Path:
    path = tmp_path / "synthetic_glass_fill.csv"
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    return path


def test_valid_fixture_loads_with_expected_summary(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_VALID_CSV, bom=True))
    assert result.errors == []
    assert result.warnings == []
    summary = result.dataset.summary
    assert summary.n_rows == 5
    assert summary.n_locations == 2
    assert summary.n_series == 4
    assert summary.date_min == date(2025, 1, 1)
    assert summary.date_max == date(2025, 2, 2)
    assert summary.rows_per_material == {"brown": 2, "green": 2, "white": 1}


def test_valid_fixture_preserves_row_order_and_i3_transform(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_VALID_CSV, bom=True))
    readings = result.dataset.readings
    assert [r.date for r in readings] == [
        date(2025, 1, 1),
        date(2025, 1, 15),
        date(2025, 1, 1),
        date(2025, 1, 1),
        date(2025, 2, 2),
    ]
    assert readings[0] == (
        readings[0].__class__(
            location_id="loc-a",
            material_type="brown",
            date=date(2025, 1, 1),
            fill_level_pct=10,
            is_overfull=False,
        )
    )
    assert readings[1].fill_level_pct is None
    assert readings[1].is_overfull is True
    assert readings[2].fill_level_pct == 100
    assert readings[2].is_overfull is False
    assert readings[3].fill_level_pct == 0
    assert readings[3].is_overfull is False


def test_r1_header_mismatch_is_error_with_row_zero(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R1_BAD_HEADER_CSV))
    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.rule_id == "R1"
    assert error.row_number == 0
    assert "fill_level_perc" in error.message
    assert result.dataset.readings == []
    assert result.dataset.summary.n_rows == 0


def test_r2_missing_or_empty_fields_are_errors(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R2_EMPTY_FIELD_CSV))
    assert [e.rule_id for e in result.errors] == ["R2", "R2", "R2"]
    assert [e.row_number for e in result.errors] == [1, 2, 3]
    assert result.dataset.readings == []
    assert result.warnings == []


def test_r3_material_outside_enum_is_error(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R3_BAD_MATERIAL_CSV))
    assert [e.rule_id for e in result.errors] == ["R3", "R3"]
    assert [e.row_number for e in result.errors] == [2, 3]
    assert [e.value for e in result.errors] == ["blue", "BROWN"]
    assert result.dataset.readings == []


def test_r4_non_strict_iso_date_is_error(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R4_BAD_DATE_CSV))
    assert [e.rule_id for e in result.errors] == ["R4", "R4", "R4", "R4"]
    assert [e.row_number for e in result.errors] == [1, 2, 3, 4]
    assert [e.value for e in result.errors] == [
        "2025-1-1",
        "not-a-date",
        "2025-02-30",
        "2025-01-05T00:00:00",
    ]
    assert result.dataset.readings == []


def test_r5_fill_outside_int_range_or_non_integer_is_error(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R5_BAD_FILL_CSV))
    assert [e.rule_id for e in result.errors] == ["R5"] * 5
    assert [e.row_number for e in result.errors] == [1, 2, 3, 4, 5]
    assert [e.value for e in result.errors] == ["55.5", "150", "-10", "half", " 50"]
    assert result.dataset.readings == []


def test_r6_identical_and_conflicting_duplicates_are_errors(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R6_DUPLICATE_KEY_CSV))
    assert [e.rule_id for e in result.errors] == ["R6", "R6"]
    assert [e.row_number for e in result.errors] == [2, 4]
    messages = [e.message for e in result.errors]
    assert any("identical" in m for m in messages)
    assert any("conflicting" in m for m in messages)
    assert result.dataset.readings == []
    assert result.dataset.summary.n_rows == 0


def test_r7_non_decile_fill_is_warning_and_row_still_loads(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_R7_NON_DECILE_CSV))
    assert result.errors == []
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.rule_id == "R7"
    assert warning.row_number == 1
    assert warning.value == "55"
    assert result.dataset.summary.n_rows == 1
    assert result.dataset.readings[0].fill_level_pct == 55
    assert result.dataset.readings[0].is_overfull is False


def test_mixed_errors_are_all_collected_not_fail_fast(tmp_path: Path) -> None:
    result = load_glass_fill_csv(_write_fixture(tmp_path, SYNTHETIC_MIXED_ERRORS_CSV))
    assert [e.rule_id for e in result.errors] == ["R3", "R4", "R5"]
    assert [e.row_number for e in result.errors] == [1, 2, 3]
    assert result.dataset.readings == []
    assert result.warnings == []


def test_real_csv_matches_observed_profile() -> None:
    """Aggregate-only assertions on the immutable raw CSV (profile §17).

    Observed facts this pins: 11,701 rows; 449 locations; 1,338 series;
    1,192 "overfull" rows; span 2025-10-17 → 2026-09-30; per-material rows
    brown 3,100 / green 4,169 / white 4,432. The real file is clean under
    R1-R7 (§9-§11: no nulls, no duplicates, no out-of-range, all deciles).
    Skips when the private CSV is absent (clean checkout / CI).
    """
    result = load_glass_fill_csv(require_real_csv_path())
    assert result.errors == []
    assert result.warnings == []
    summary = result.dataset.summary
    assert summary.n_rows == 11_701
    assert summary.n_locations == 449
    assert summary.n_series == 1_338
    assert summary.date_min == date(2025, 10, 17)
    assert summary.date_max == date(2026, 9, 30)
    assert summary.rows_per_material == {"brown": 3_100, "green": 4_169, "white": 4_432}
    n_overfull = sum(1 for r in result.dataset.readings if r.is_overfull)
    assert n_overfull == 1_192
