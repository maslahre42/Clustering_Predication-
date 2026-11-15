"""In-memory active dataset store — docs/contracts.md §5 (v1 limitation).

One active dataset per process; an upload replaces it, validation errors
never replace it (§5.3). This is a documented prototype limitation, not a
persistence claim.
"""

from __future__ import annotations

from src.data.schema import Dataset, ValidationWarning


class NoDatasetError(LookupError):
    """Raised when an endpoint needs the active dataset and none is loaded."""


class DatasetStore:
    """Holds the single active dataset plus its upload provenance."""

    def __init__(self) -> None:
        self._dataset: Dataset | None = None
        self._warnings: list[ValidationWarning] = []
        self._source_name: str | None = None

    def reset(self) -> None:
        """Clear the store (used by tests and not exposed via the API)."""
        self._dataset = None
        self._warnings = []
        self._source_name = None

    def set(
        self,
        dataset: Dataset,
        warnings: list[ValidationWarning],
        source_name: str,
    ) -> None:
        """Atomically replace the active dataset after successful validation."""
        self._dataset = dataset
        self._warnings = list(warnings)
        self._source_name = source_name

    @property
    def has_dataset(self) -> bool:
        return self._dataset is not None

    @property
    def dataset(self) -> Dataset:
        """The active dataset; raises :class:`NoDatasetError` when unset."""
        if self._dataset is None:
            raise NoDatasetError("no active dataset; upload one via POST /api/datasets")
        return self._dataset

    @property
    def warnings(self) -> list[ValidationWarning]:
        """Warnings of the upload that produced the active dataset."""
        return list(self._warnings)

    @property
    def source_name(self) -> str:
        """Source file name of the active dataset (empty string when unset)."""
        return self._source_name or ""


store = DatasetStore()
"""Process-wide active dataset (contract §5: exactly one)."""
