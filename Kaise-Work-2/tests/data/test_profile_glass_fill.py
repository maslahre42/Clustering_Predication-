"""Tests for src.data.profile_glass_fill.

Uses a small SYNTHETIC fixture written to tmp_path — never data/raw.
The fixture encodes: an exact-row duplicate, a same-key pair with conflicting
fills, one "overfull" token, one same-day reading pair (0-day gap), and one
single-reading series (no gap).
"""

from pathlib import Path

from src.data.profile_glass_fill import (
    build_report,
    load_raw,
    profile_dates,
    profile_fills,
    profile_keys,
    profile_materials,
    profile_nulls,
    profile_series,
    profile_states,
    profile_transitions,
)

SYNTHETIC_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2025-01-01,10
loc-a,brown,2025-01-11,50
loc-a,brown,2025-01-21,overfull
loc-a,white,2025-01-01,100
loc-b,brown,2025-02-01,0
loc-b,brown,2025-02-01,40
loc-a,brown,2025-01-11,50
loc-c,green,2025-01-05,overfull
loc-c,green,2025-01-20,100
"""


def _write_fixture(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic_glass.csv"
    path.write_text(SYNTHETIC_CSV, encoding="utf-8")
    return path


def test_load_raw_reads_all_columns_as_text(tmp_path: Path) -> None:
    df = load_raw(_write_fixture(tmp_path))
    assert len(df) == 9
    assert tuple(str(c) for c in df.columns) == (
        "Location_id",
        "material_type",
        "date",
        "fill_level_perc",
    )


def test_profile_nulls_reports_shape_and_missing(tmp_path: Path) -> None:
    profile = profile_nulls(load_raw(_write_fixture(tmp_path)))
    assert profile.n_rows == 9
    assert profile.nulls_per_column == {
        "Location_id": 0,
        "material_type": 0,
        "date": 0,
        "fill_level_perc": 0,
    }


def test_profile_dates_parses_strict_iso(tmp_path: Path) -> None:
    profile = profile_dates(load_raw(_write_fixture(tmp_path)))
    assert profile.min_date == "2025-01-01"
    assert profile.max_date == "2025-02-01"
    assert profile.n_unique_dates == 6
    assert profile.n_nonnull_unparseable == 0


def test_profile_materials_counts_rows_and_values(tmp_path: Path) -> None:
    profile = profile_materials(load_raw(_write_fixture(tmp_path)))
    assert profile.row_counts == {"brown": 6, "white": 1, "green": 2}
    assert profile.distinct_raw_values == ("brown", "green", "white")
    assert profile.n_location_ids_with_padding == 0


def test_profile_fills_separates_numeric_and_overfull(tmp_path: Path) -> None:
    profile = profile_fills(load_raw(_write_fixture(tmp_path)))
    assert profile.n_numeric == 7
    assert profile.n_overfull == 2
    assert profile.n_other_text == 0
    assert profile.other_text_examples == ()
    assert profile.numeric_min == 0
    assert profile.numeric_max == 100
    assert profile.n_out_of_range == 0
    assert profile.value_counts == {0: 1, 10: 1, 40: 1, 50: 2, 100: 2}


def test_profile_keys_distinguishes_exact_and_conflicting_duplicates(
    tmp_path: Path,
) -> None:
    profile = profile_keys(load_raw(_write_fixture(tmp_path)))
    assert profile.n_rows == 9
    assert profile.n_exact_row_duplicates == 1
    assert profile.n_key_duplicate_rows == 2
    assert profile.n_duplicate_keys_with_conflicting_fills == 1


def test_profile_series_gaps_and_grouping(tmp_path: Path) -> None:
    profile = profile_series(load_raw(_write_fixture(tmp_path)))
    assert profile.n_locations == 3
    assert profile.n_series == 4
    assert profile.readings_per_series == {
        "min": 1.0,
        "p25": 1.75,
        "median": 2.0,
        "p75": 2.5,
        "max": 4.0,
    }
    assert profile.gap_days["min"] == 0.0
    assert profile.gap_days["p25"] == 0.0
    assert profile.gap_days["median"] == 10.0
    assert profile.gap_days["p75"] == 10.0
    assert profile.gap_days["max"] == 15.0
    assert profile.top_gap_days == {0: 2, 10: 2, 15: 1}
    assert profile.per_series_median_gap_days == {
        "min": 0.0,
        "median": 10.0,
        "max": 15.0,
    }
    assert profile.locations_by_material_count == {1: 2, 2: 1}
    assert profile.same_day_pairs_by_material_count == {1: 5, 2: 1}
    assert profile.monthly_row_counts == {"2025-01": 7, "2025-02": 2}


def test_profile_states_counts_series_level_value_usage(tmp_path: Path) -> None:
    profile = profile_states(load_raw(_write_fixture(tmp_path)))
    assert profile.n_series_with_100 == 2
    assert profile.n_series_with_overfull == 2
    assert profile.n_series_with_both == 1
    assert profile.overfull_by_material == {"brown": 1, "green": 1}
    assert profile.share_numeric_100_by_material == {
        "brown": 0.0,
        "green": 1.0,
        "white": 1.0,
    }


def test_profile_transitions_gaps_and_next_after_full(tmp_path: Path) -> None:
    profile = profile_transitions(load_raw(_write_fixture(tmp_path)))
    assert profile.n_single_reading_series == 1
    assert profile.max_gap_days == 15
    assert profile.max_gap_series == "loc-c|green"
    assert profile.gaps_le_31_days_share == 1.0
    assert profile.next_value_after_full == {"100": 1}


def test_build_report_contains_all_sections(tmp_path: Path) -> None:
    report = build_report(_write_fixture(tmp_path))
    for marker in (
        "ROWS: 9",
        "NULLS:",
        "DATES:",
        "MATERIALS row_counts:",
        "FILLS:",
        "KEYS:",
        "SERIES:",
        "GAPS days",
        "MONTHLY row_counts:",
        "STATES:",
        "TRANSITIONS:",
    ):
        assert marker in report, f"missing section marker: {marker}"
