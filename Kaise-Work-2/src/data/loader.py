"""Canonical CSV loader — docs/contracts.md §1 (v1, agreed for M2).

Loads the raw glass fill-level CSV (docs/data_profile.md) into the canonical
schema with validation rules R1-R7 and invariants I1-I3 (contract §1.2/§1.4):

- reads with encoding ``utf-8-sig`` (source carries a UTF-8 BOM, profile §1);
- reads every cell as text first; only validated values are typed;
- parses dates strictly ``%Y-%m-%d`` (zero-padded ISO, date-only, no timezone);
- maps the literal ``overfull`` token to ``fill_level_pct=None, is_overfull=True``
  and never coerces it to a number (contract §1.1 non-decision);
- any R1-R6 error yields ``Dataset.empty()`` plus the full error list — rows are
  never silently dropped; R7 (non-decile fill) is a warning only;
- data/raw files are read-only: this loader only opens files for reading.

Row-number convention: 1-based data-row index, header excluded; R1 header
errors use row_number 0.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import TypeAlias

from src.data.schema import (
    MATERIALS,
    Dataset,
    DatasetSummary,
    LoadResult,
    ReadingRecord,
    ValidationError,
    ValidationWarning,
)

EXPECTED_COLUMNS: tuple[str, ...] = (
    "Location_id",
    "material_type",
    "date",
    "fill_level_perc",
)
DATE_FORMAT = "%Y-%m-%d"
OVERFULL_TOKEN = "overfull"
FILL_MIN_PCT = 0  # percent, inclusive (observed range 0-100, profile §8)
FILL_MAX_PCT = 100  # percent, inclusive
DECILE_STEP_PCT = 10  # observed quantization (profile §8); warning R7 only

_RowOutcome: TypeAlias = tuple[
    list[ValidationError],
    list[ValidationWarning],
    ReadingRecord | None,
    # (raw key tuple, raw fill text) when location/material/date cells exist and
    # the date parses strictly — the basis for duplicate-key detection (R6).
    tuple[tuple[str, str, date], str] | None,
]


def load_glass_fill_csv(path: Path) -> LoadResult:
    """Load and validate one glass fill-level CSV file (contract §1.3/§1.4)."""
    rows = _read_rows(path)
    header_error = _validate_header(rows)
    if header_error is not None:
        return LoadResult(dataset=Dataset.empty(), errors=[header_error], warnings=[])

    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []
    readings: list[ReadingRecord] = []
    seen_keys: dict[tuple[str, str, date], str] = {}

    for row_number, cells in enumerate(rows[1:], start=1):
        row_errors, row_warnings, record, key_info = _validate_data_row(cells, row_number)
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if key_info is not None:
            key, raw_fill = key_info
            duplicate_error = _duplicate_key_error(seen_keys, key, raw_fill, row_number)
            if duplicate_error is not None:
                errors.append(duplicate_error)
            else:
                seen_keys[key] = raw_fill
        if record is not None:
            readings.append(record)

    dataset = (
        Dataset.empty() if errors else Dataset(readings=readings, summary=_build_summary(readings))
    )
    return LoadResult(dataset=dataset, errors=errors, warnings=warnings)


def _read_rows(path: Path) -> list[list[str]]:
    """Read all cells as text with utf-8-sig (BOM tolerated, profile §1)."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def _validate_header(rows: list[list[str]]) -> ValidationError | None:
    """Rule R1: column set/header mismatch (contract §1.4)."""
    header = tuple(rows[0]) if rows else ()
    if header == EXPECTED_COLUMNS:
        return None
    return ValidationError(
        rule_id="R1",
        row_number=0,
        message=(
            f"header mismatch: expected {','.join(EXPECTED_COLUMNS)}, "
            f"got {','.join(header) or '<empty file>'}"
        ),
        value=",".join(header) or None,
    )


def _validate_data_row(cells: list[str], row_number: int) -> _RowOutcome:
    """Validate one data row against R2-R5 (+R7 warning); build its record.

    R2 short-circuits the row (cell positions unusable); R3, R4 and R5 are
    evaluated independently so the full issue list is collected per row.
    """
    if len(cells) != len(EXPECTED_COLUMNS):
        error = ValidationError(
            rule_id="R2",
            row_number=row_number,
            message=(f"expected {len(EXPECTED_COLUMNS)} fields, got {len(cells)}"),
            value=",".join(cells),
        )
        return [error], [], None, None

    location_id, material, raw_date, raw_fill = cells
    errors: list[ValidationError] = []

    if not location_id:
        errors.append(ValidationError("R2", row_number, "empty field: Location_id", None))
    if not material:
        errors.append(ValidationError("R2", row_number, "empty field: material_type", None))
    if not raw_date:
        errors.append(ValidationError("R2", row_number, "empty field: date", None))
    if not raw_fill:
        errors.append(ValidationError("R2", row_number, "empty field: fill_level_perc", None))

    if errors:
        return errors, [], None, None

    if material not in MATERIALS:
        errors.append(
            ValidationError(
                "R3",
                row_number,
                f"material_type {material!r} outside enum {list(MATERIALS)}",
                material,
            )
        )
    parsed_date = _parse_strict_iso_date(raw_date)
    if parsed_date is None:
        errors.append(
            ValidationError(
                "R4",
                row_number,
                f"date {raw_date!r} is not strict {DATE_FORMAT}",
                raw_date,
            )
        )

    is_overfull = raw_fill == OVERFULL_TOKEN
    fill_level_pct = None if is_overfull else _parse_fill_pct(raw_fill)
    if not is_overfull and fill_level_pct is None:
        errors.append(
            ValidationError(
                "R5",
                row_number,
                _fill_rejection_message(raw_fill),
                raw_fill,
            )
        )
    record: ReadingRecord | None = None
    row_warnings: list[ValidationWarning] = []
    # Record guard is the exact negation of the R3/R4/R5 error conditions above,
    # so a row yields a record iff it produced none of those errors.
    if (
        material in MATERIALS
        and parsed_date is not None
        and (is_overfull or fill_level_pct is not None)
    ):
        record = ReadingRecord(
            location_id=location_id,
            material_type=material,
            date=parsed_date,
            fill_level_pct=fill_level_pct,
            is_overfull=is_overfull,
        )
        if fill_level_pct is not None and fill_level_pct % DECILE_STEP_PCT != 0:
            row_warnings.append(
                ValidationWarning(
                    "R7",
                    row_number,
                    f"fill_level_perc {fill_level_pct} is not a multiple of "
                    f"{DECILE_STEP_PCT} (observed source values are deciles, "
                    "profile §8)",
                    raw_fill,
                )
            )
    key = (location_id, material, parsed_date) if parsed_date is not None else None
    key_info = (key, raw_fill) if key is not None else None
    return errors, row_warnings, record, key_info


def _parse_strict_iso_date(raw: str) -> date | None:
    """Strictly parse zero-padded ``%Y-%m-%d``; None when not exactly that."""
    try:
        parsed = datetime.strptime(raw, DATE_FORMAT)
    except ValueError:
        return None
    if parsed.date().isoformat() != raw:
        return None  # e.g. "2025-1-1" parses but is not zero-padded ISO
    return parsed.date()


def _parse_fill_pct(raw: str) -> int | None:
    """Parse an ASCII decimal integer fill in [0,100] percent; else None."""
    if not (raw.isascii() and raw.isdigit()):
        return None
    value = int(raw)
    if not FILL_MIN_PCT <= value <= FILL_MAX_PCT:
        return None
    return value


def _fill_rejection_message(raw: str) -> str:
    if raw.isascii() and raw.isdigit():
        return (
            f"fill_level_perc {raw} out of range "
            f"[{FILL_MIN_PCT}, {FILL_MAX_PCT}] percent and not {OVERFULL_TOKEN!r}"
        )
    return f"fill_level_perc {raw!r} is neither an integer percent nor {OVERFULL_TOKEN!r}"


def _duplicate_key_error(
    seen_keys: dict[tuple[str, str, date], str],
    key: tuple[str, str, date],
    raw_fill: str,
    row_number: int,
) -> ValidationError | None:
    """Rule R6/I1: flag any row whose (location, material, date) key repeats.

    Both identical-row duplicates and conflicting-value duplicates are errors;
    the later occurrence is the flagged one.
    """
    first_fill = seen_keys.get(key)
    if first_fill is None:
        return None
    kind = "identical" if first_fill == raw_fill else "conflicting"
    return ValidationError(
        rule_id="R6",
        row_number=row_number,
        message=(
            f"duplicate key ({key[0]}, {key[1]}, {key[2].isoformat()}) with {kind} fill value"
        ),
        value=raw_fill,
    )


def _build_summary(readings: list[ReadingRecord]) -> DatasetSummary:
    """Derive contract §1.3 summary counters; deterministic zero-filled counts."""
    if not readings:
        return DatasetSummary(n_rows=0, n_locations=0, n_series=0, date_min=None, date_max=None)
    rows_per_material = {material: 0 for material in MATERIALS}
    for reading in readings:
        rows_per_material[reading.material_type] += 1
    reading_dates = [reading.date for reading in readings]
    return DatasetSummary(
        n_rows=len(readings),
        n_locations=len({reading.location_id for reading in readings}),
        n_series=len({(reading.location_id, reading.material_type) for reading in readings}),
        date_min=min(reading_dates),
        date_max=max(reading_dates),
        rows_per_material=rows_per_material,
    )
