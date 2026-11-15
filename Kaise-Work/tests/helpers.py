"""Shared test helpers.

The challenge CSV is private data and git-ignored: it exists on the real
machine but not on a clean checkout / CI runner. Tests that pin aggregate
facts against it skip (with a clear reason) instead of erroring when the
file is absent, and run unchanged when it is present.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Same relative path the loader/demo endpoint uses; never copied elsewhere.
REAL_CSV_PATH = Path("data/raw/glass_fill_levels_anonymized_f.csv")

_SKIP_REASON = "real challenge CSV not present (private data, gitignored) — skipped"


def require_real_csv_path() -> Path:
    """Return the real-CSV path or skip the calling test with a clear reason."""
    if not REAL_CSV_PATH.is_file():
        pytest.skip(_SKIP_REASON)
    return REAL_CSV_PATH
