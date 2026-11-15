"""Spatial/container analysis (M4) — coordinate availability + synthetic isolation.

Findings encoded here (docs/data_profile.md §13.8):
- the canonical reading schema carries NO coordinates, volumes, weights or any
  other geo/fleet fields — spatial clustering is impossible on this dataset and
  is NOT attempted; coordinates must come from the challenge host (M8).
- synthetic fixtures are isolated by convention: synthetic location ids carry
  the ``SYNTHETIC-`` prefix (tests/fixtures/), real challenge ids are
  UUID-format strings. ``require_real_ids`` fails any real-data code path that
  encounters a synthetic id, so real and synthetic locations cannot be
  silently mixed.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from src.data.schema import Dataset, ReadingRecord

SYNTHETIC_ID_PREFIX = "SYNTHETIC-"

_COORDINATE_HINTS: tuple[str, ...] = (
    "coord",
    "lat",
    "lon",
    "easting",
    "northing",
    "geo",
    "utm",
)


def is_synthetic_id(location_id: str) -> bool:
    """True when a location id carries the synthetic-fixture prefix."""
    return location_id.startswith(SYNTHETIC_ID_PREFIX)


def require_real_ids(readings: list[ReadingRecord]) -> None:
    """Guard for real-data code paths: raise if any synthetic id is present.

    Guards against loading tests/fixtures data into production/analysis paths.
    """
    offenders = sorted({r.location_id for r in readings if is_synthetic_id(r.location_id)})
    if offenders:
        preview = ", ".join(offenders[:5]) + (" ..." if len(offenders) > 5 else "")
        raise ValueError(
            "synthetic fixture ids found in real-data path "
            f"({len(offenders)} distinct, prefix {SYNTHETIC_ID_PREFIX!r}): {preview}"
        )


@dataclass(frozen=True)
class CoordinateAvailability:
    """Observed coordinate availability of a dataset (M4 documentation)."""

    n_coordinate_fields: int
    coordinate_fields: tuple[str, ...]
    statement: str


def describe_coordinate_availability(dataset: Dataset) -> CoordinateAvailability:
    """Introspect the canonical schema: coordinate fields present (observed: none)."""
    fields = [f.name for f in dataclasses.fields(ReadingRecord)]
    coordinate_fields = tuple(
        name for name in fields if any(hint in name.lower() for hint in _COORDINATE_HINTS)
    )
    statement = (
        f"canonical schema has {len(fields)} fields, {len(coordinate_fields)} of them "
        "coordinate-like; observed: no coordinates in the source CSV "
        "(docs/data_profile.md §13.8) — no spatial clustering possible"
    )
    return CoordinateAvailability(
        n_coordinate_fields=len(coordinate_fields),
        coordinate_fields=coordinate_fields,
        statement=statement,
    )
