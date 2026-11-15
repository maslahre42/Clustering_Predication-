"""Reproducible aggregate profiler for the raw glass fill-level CSV (M1 audit).

Read-only utility: prints compact aggregates so the facts documented in
docs/data_profile.md stay reproducible without reading the full dataset into
any context. Raw inputs in data/raw/ are immutable; this module never writes.

Usage:
    .venv/bin/python -m src.data.profile_glass_fill [PATH_TO_CSV]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]  # pandas 3.1.1 ships no py.typed; pandas-stubs not a repo dependency

DEFAULT_CSV = Path("data/raw/glass_fill_levels_anonymized_f.csv")
KEY_COLUMNS = ("Location_id", "material_type", "date")
SERIES_COLUMNS = ("Location_id", "material_type")  # one series = one location's material
DATE_FORMAT = "%Y-%m-%d"
OVERFULL_TOKEN = "overfull"
FILL_MIN = 0  # percent (unit per column name fill_level_perc)
FILL_MAX = 100  # percent


@dataclass(frozen=True)
class NullProfile:
    n_rows: int
    nulls_per_column: dict[str, int]


@dataclass(frozen=True)
class DateProfile:
    min_date: str
    max_date: str
    n_unique_dates: int
    n_nonnull_unparseable: int


@dataclass(frozen=True)
class MaterialProfile:
    row_counts: dict[str, int]
    distinct_raw_values: tuple[str, ...]
    distinct_stripped_lower: tuple[str, ...]
    n_location_ids_with_padding: int


@dataclass(frozen=True)
class FillProfile:
    n_numeric: int
    n_overfull: int
    n_other_text: int
    other_text_examples: tuple[str, ...]
    numeric_min: int
    numeric_max: int
    n_out_of_range: int
    value_counts: dict[int, int]


@dataclass(frozen=True)
class KeyProfile:
    n_rows: int
    n_exact_row_duplicates: int
    n_key_duplicate_rows: int
    n_duplicate_keys_with_conflicting_fills: int


@dataclass(frozen=True)
class SeriesProfile:
    n_locations: int
    n_series: int  # distinct (Location_id, material_type)
    readings_per_series: dict[str, float]
    gap_days: dict[str, float]
    per_series_median_gap_days: dict[str, float]
    top_gap_days: dict[int, int]
    locations_by_material_count: dict[int, int]
    same_day_pairs_by_material_count: dict[int, int]
    monthly_row_counts: dict[str, int]


@dataclass(frozen=True)
class StateProfile:
    """Series-level usage of the '100' numeric value vs the 'overfull' token."""

    n_series_with_100: int
    n_series_with_overfull: int
    n_series_with_both: int
    overfull_by_material: dict[str, int]
    share_numeric_100_by_material: dict[str, float]


@dataclass(frozen=True)
class TransitionProfile:
    """Consecutive-reading behaviour used to qualify full/overfull readings."""

    n_single_reading_series: int
    max_gap_days: int
    max_gap_series: str
    gaps_le_31_days_share: float
    next_value_after_full: dict[str, int]


def load_raw(path: Path) -> pd.DataFrame:
    """Read the raw CSV with every column as text; callers parse selectively."""
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str)


def profile_nulls(df: pd.DataFrame) -> NullProfile:
    per_column = {str(col): int(n) for col, n in df.isna().sum().items()}
    return NullProfile(n_rows=len(df), nulls_per_column=per_column)


def profile_dates(df: pd.DataFrame) -> DateProfile:
    parsed = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    valid = parsed.dropna()
    n_nonnull = int(df["date"].notna().sum())
    return DateProfile(
        min_date=valid.min().date().isoformat(),
        max_date=valid.max().date().isoformat(),
        n_unique_dates=int(valid.nunique()),
        n_nonnull_unparseable=n_nonnull - int(valid.notna().sum()),
    )


def profile_materials(df: pd.DataFrame) -> MaterialProfile:
    raw_values = df["material_type"].dropna().unique()
    counts = df["material_type"].value_counts()
    padded = int((df["Location_id"] != df["Location_id"].str.strip()).sum())
    return MaterialProfile(
        row_counts={str(k): int(v) for k, v in counts.items()},
        distinct_raw_values=tuple(sorted(str(v) for v in raw_values)),
        distinct_stripped_lower=tuple(sorted({str(v).strip().lower() for v in raw_values})),
        n_location_ids_with_padding=padded,
    )


def profile_fills(df: pd.DataFrame) -> FillProfile:
    values = df["fill_level_perc"]
    numeric = pd.to_numeric(values, errors="coerce")
    is_numeric = numeric.notna()
    is_overfull = values.eq(OVERFULL_TOKEN)
    is_other = ~(is_numeric | is_overfull)
    numeric_only = numeric[is_numeric]
    counts = numeric_only.astype("int64").value_counts().sort_index()
    examples = tuple(str(v) for v in values[is_other].head(5).tolist())
    return FillProfile(
        n_numeric=int(is_numeric.sum()),
        n_overfull=int(is_overfull.sum()),
        n_other_text=int(is_other.sum()),
        other_text_examples=examples,
        numeric_min=int(numeric_only.min()),
        numeric_max=int(numeric_only.max()),
        n_out_of_range=int(((numeric_only < FILL_MIN) | (numeric_only > FILL_MAX)).sum()),
        value_counts={int(k): int(v) for k, v in counts.items()},
    )


def profile_keys(df: pd.DataFrame) -> KeyProfile:
    fills_per_key = df.groupby(list(KEY_COLUMNS), dropna=False)["fill_level_perc"].nunique()
    return KeyProfile(
        n_rows=len(df),
        n_exact_row_duplicates=int(df.duplicated(keep="first").sum()),
        n_key_duplicate_rows=int(df.duplicated(subset=list(KEY_COLUMNS), keep="first").sum()),
        n_duplicate_keys_with_conflicting_fills=int((fills_per_key > 1).sum()),
    )


def _dist(values: pd.Series) -> dict[str, float]:
    """Return min/p25/median/p75/max of a numeric series as plain floats."""
    quantiles = values.quantile([0.25, 0.5, 0.75])
    return {
        "min": float(values.min()),
        "p25": float(quantiles.iloc[0]),
        "median": float(quantiles.iloc[1]),
        "p75": float(quantiles.iloc[2]),
        "max": float(values.max()),
    }


def _int_counts(values: pd.Series) -> dict[int, int]:
    return {int(k): int(v) for k, v in values.items()}


def profile_series(df: pd.DataFrame) -> SeriesProfile:
    parsed = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    d = df.assign(_date=parsed).dropna(subset=["_date"]).sort_values(list(KEY_COLUMNS))
    grouped = d.groupby(list(SERIES_COLUMNS), observed=True)
    series_sizes = grouped.size()
    d = d.assign(_gap_days=grouped["_date"].diff().dt.days)
    gaps = d["_gap_days"].dropna()
    per_series_median = (
        d.groupby(list(SERIES_COLUMNS), observed=True)["_gap_days"].median().dropna()
    )
    materials_per_location = d.groupby("Location_id", observed=True)["material_type"].nunique()
    same_day_pairs = d.groupby(["Location_id", "date"], observed=True)["material_type"].nunique()
    monthly = parsed.dt.to_period("M").value_counts().sort_index()
    return SeriesProfile(
        n_locations=int(df["Location_id"].nunique()),
        n_series=len(series_sizes),
        readings_per_series=_dist(series_sizes.astype(float)),
        gap_days=_dist(gaps),
        per_series_median_gap_days={
            "min": float(per_series_median.min()),
            "median": float(per_series_median.median()),
            "max": float(per_series_median.max()),
        },
        top_gap_days=_int_counts(gaps.round().astype("int64").value_counts().head(8).sort_index()),
        locations_by_material_count=_int_counts(materials_per_location.value_counts().sort_index()),
        same_day_pairs_by_material_count=_int_counts(same_day_pairs.value_counts().sort_index()),
        monthly_row_counts={str(k): int(v) for k, v in monthly.items()},
    )


def profile_states(df: pd.DataFrame) -> StateProfile:
    fills_by_series = df.groupby(list(SERIES_COLUMNS), observed=True)["fill_level_perc"]
    has_100 = fills_by_series.apply(lambda v: bool((v == "100").any()))
    has_overfull = fills_by_series.apply(lambda v: bool((v == OVERFULL_TOKEN).any()))
    is_overfull = df["fill_level_perc"].eq(OVERFULL_TOKEN)
    is_numeric = pd.to_numeric(df["fill_level_perc"], errors="coerce").notna()
    share_100 = (
        df[is_numeric]
        .groupby("material_type", observed=True)["fill_level_perc"]
        .apply(lambda v: float((v == "100").mean()))
    )
    overfull_counts = df[is_overfull]["material_type"].value_counts()
    return StateProfile(
        n_series_with_100=int(has_100.sum()),
        n_series_with_overfull=int(has_overfull.sum()),
        n_series_with_both=int((has_100 & has_overfull).sum()),
        overfull_by_material={str(k): int(v) for k, v in overfull_counts.items()},
        share_numeric_100_by_material={str(k): float(v) for k, v in share_100.items()},
    )


def profile_transitions(df: pd.DataFrame) -> TransitionProfile:
    parsed = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
    d = df.assign(_date=parsed).dropna(subset=["_date"]).sort_values(list(KEY_COLUMNS))
    grouped = d.groupby(list(SERIES_COLUMNS), observed=True)
    sizes = grouped.size()
    d = d.assign(
        _gap_days=grouped["_date"].diff().dt.days,
        _next_fill=grouped["fill_level_perc"].shift(-1),
    )
    gaps = d["_gap_days"].dropna()
    max_row = d.loc[d["_gap_days"].idxmax()]
    is_full = d["fill_level_perc"].isin(["100", OVERFULL_TOKEN])
    has_next = d["_next_fill"].notna()
    next_counts = d.loc[is_full & has_next, "_next_fill"].value_counts()
    return TransitionProfile(
        n_single_reading_series=int((sizes == 1).sum()),
        max_gap_days=int(max_row["_gap_days"]),
        max_gap_series=f"{max_row['Location_id']}|{max_row['material_type']}",
        gaps_le_31_days_share=float((gaps <= 31).mean()),
        next_value_after_full={str(k): int(v) for k, v in next_counts.items()},
    )


def format_report(
    source: Path,
    columns: tuple[str, ...],
    nulls: NullProfile,
    dates: DateProfile,
    materials: MaterialProfile,
    fills: FillProfile,
    keys: KeyProfile,
    series: SeriesProfile,
    states: StateProfile,
    transitions: TransitionProfile,
) -> str:
    """Render all aggregate sections as compact text (one fact per line)."""
    lines = [
        f"FILE: {source}",
        f"ROWS: {nulls.n_rows}",
        f"COLUMNS: {', '.join(columns)}",
        f"NULLS: {nulls.nulls_per_column}",
        (
            f"DATES: min={dates.min_date} max={dates.max_date} "
            f"unique={dates.n_unique_dates} nonnull_unparseable={dates.n_nonnull_unparseable} "
            "(date-only strings; no time component)"
        ),
        f"MATERIALS row_counts: {materials.row_counts}",
        f"MATERIALS distinct_raw: {materials.distinct_raw_values}",
        f"MATERIALS distinct_stripped_lower: {materials.distinct_stripped_lower}",
        f"LOCATION_IDS with padding/whitespace: {materials.n_location_ids_with_padding}",
        (
            f"FILLS: numeric={fills.n_numeric} overfull={fills.n_overfull} "
            f"other_text={fills.n_other_text} examples={fills.other_text_examples or '<none>'}"
        ),
        (
            f"FILLS numeric range: min={fills.numeric_min} max={fills.numeric_max} "
            f"out_of_range(<{FILL_MIN} or >{FILL_MAX})={fills.n_out_of_range}"
        ),
        f"FILLS numeric value_counts: {fills.value_counts}",
        (
            f"KEYS: exact_row_duplicates={keys.n_exact_row_duplicates} "
            f"key_duplicate_rows={keys.n_key_duplicate_rows} "
            f"conflicting_duplicate_keys={keys.n_duplicate_keys_with_conflicting_fills}"
        ),
        (
            f"SERIES: locations={series.n_locations} series={series.n_series} "
            f"readings/series={series.readings_per_series}"
        ),
        (f"GAPS days all-readings: {series.gap_days} top_counts={series.top_gap_days}"),
        (f"GAPS days per-series median: {series.per_series_median_gap_days}"),
        f"LOCATIONS by material_count: {series.locations_by_material_count}",
        f"SAME-DAY (location,date) pairs by material count: "
        f"{series.same_day_pairs_by_material_count}",
        f"MONTHLY row_counts: {series.monthly_row_counts}",
        (
            f"STATES: series_with_100={states.n_series_with_100} "
            f"series_with_overfull={states.n_series_with_overfull} "
            f"series_with_both={states.n_series_with_both}"
        ),
        f"STATES overfull_by_material: {states.overfull_by_material}",
        f"STATES share_numeric_100_by_material: {states.share_numeric_100_by_material}",
        (
            f"TRANSITIONS: single_reading_series={transitions.n_single_reading_series} "
            f"max_gap_days={transitions.max_gap_days} (series {transitions.max_gap_series}) "
            f"gaps<=31d_share={transitions.gaps_le_31_days_share:.3f}"
        ),
        f"TRANSITIONS next_value_after_full: {transitions.next_value_after_full}",
    ]
    return "\n".join(lines)


def build_report(path: Path) -> str:
    """Load the CSV once and return the full aggregate report text."""
    df = load_raw(path)
    return format_report(
        source=path,
        columns=tuple(str(c) for c in df.columns),
        nulls=profile_nulls(df),
        dates=profile_dates(df),
        materials=profile_materials(df),
        fills=profile_fills(df),
        keys=profile_keys(df),
        series=profile_series(df),
        states=profile_states(df),
        transitions=profile_transitions(df),
    )


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_CSV
    print(build_report(path))


if __name__ == "__main__":
    main()
