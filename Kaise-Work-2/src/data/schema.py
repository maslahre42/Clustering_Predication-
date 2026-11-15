"""Canonical fill-level reading schema — docs/contracts.md §1 (v1, agreed for M2).

Frozen stdlib dataclasses only (no pydantic). The reading semantics deliberately
remain undecided per contract §1.1: "overfull" is NOT coerced to a number,
decile quantization is NOT enforced, and no capacity/volume/weight fields exist.

Field/status provenance is documented in docs/contracts.md §1.1; observed facts
trace to docs/data_profile.md. Units: fill_level_pct is percent (implied by the
source column name `fill_level_perc`, profile §3); dates are timezone-naive
calendar dates (profile §4 — do not attach a timezone).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, TypeAlias

MaterialType: TypeAlias = Literal["brown", "green", "white"]
"""Glass colours observed in the source (profile §2): exactly these three."""

MATERIALS: tuple[MaterialType, ...] = ("brown", "green", "white")


@dataclass(frozen=True)
class ReadingRecord:
    """One fill reading for one (location_id, material_type, date) — contract §1.1.

    Invariant I3 (contract §1.2): `fill_level_pct is None` exactly when
    `is_overfull` is True; enforced at construction.
    """

    location_id: str
    material_type: MaterialType
    date: date  # timezone-naive calendar date; see profile §4 / open question §13.6
    fill_level_pct: int | None  # percent; None iff is_overfull (I3)
    is_overfull: bool  # preserves the literal "overfull" token

    def __post_init__(self) -> None:
        if self.is_overfull != (self.fill_level_pct is None):
            raise ValueError(
                "invariant I3 violated: fill_level_pct is None exactly when "
                f"is_overfull is True (got fill_level_pct={self.fill_level_pct!r}, "
                f"is_overfull={self.is_overfull!r})"
            )


@dataclass(frozen=True)
class DatasetSummary:
    """Aggregate counters over a Dataset — contract §1.3.

    date_min/date_max are None only for an empty dataset. rows_per_material
    always contains all three materials (0 included) for deterministic access.
    """

    n_rows: int
    n_locations: int
    n_series: int  # distinct (location_id, material_type) pairs
    date_min: date | None
    date_max: date | None
    rows_per_material: dict[MaterialType, int] = field(
        default_factory=lambda: {material: 0 for material in MATERIALS}
    )


@dataclass(frozen=True)
class Dataset:
    """Canonical reading collection — contract §1.3.

    readings preserve source file order (no sorting); summary is derived.
    """

    readings: list[ReadingRecord]
    summary: DatasetSummary

    @classmethod
    def empty(cls) -> Dataset:
        """Zeroed dataset used by LoadResult when validation produced errors."""
        return cls(
            readings=[],
            summary=DatasetSummary(
                n_rows=0,
                n_locations=0,
                n_series=0,
                date_min=None,
                date_max=None,
            ),
        )


@dataclass(frozen=True)
class ValidationError:
    """A rule violation that invalidates the whole dataset — contract §1.3/§1.4.

    row_number is the 1-based data-row index (header excluded); 0 denotes the
    header row itself (used by R1). value is the offending raw cell text when
    one exists, else None.
    """

    rule_id: str
    row_number: int
    message: str
    value: str | None = None


@dataclass(frozen=True)
class ValidationWarning:
    """A data-quality finding that does NOT invalidate the dataset — contract §1.4.

    Same row_number/value conventions as ValidationError (R7 today).
    """

    rule_id: str
    row_number: int
    message: str
    value: str | None = None


@dataclass(frozen=True)
class LoadResult:
    """Outcome of loading one CSV file — contract §1.3.

    Policy (contract §1.4): if errors is non-empty, dataset is Dataset.empty()
    (zeroed summary, no readings) and errors holds the full list — rows are
    never silently dropped or coerced. warnings never empty the dataset.
    """

    dataset: Dataset
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
