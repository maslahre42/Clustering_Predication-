"""Shared fixtures/helpers for M10 API contract tests — docs/contracts.md §5.

Synthetic CSV content (labelled ``loc-a``/``loc-b`` ids, never real data —
M4 rule). Each test gets a fresh in-memory store via the ``client`` fixture
(contract §5: one active dataset per process).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.state import store

# 10 rows, 2 locations, 5 series; includes one overfull token and one
# numeric-100 reading so both distinct states are covered.
VALID_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2026-01-05,20
loc-a,brown,2026-01-19,50
loc-a,brown,2026-02-02,90
loc-a,green,2026-01-05,10
loc-a,green,2026-02-01,overfull
loc-a,white,2026-01-06,40
loc-b,brown,2026-01-07,30
loc-b,brown,2026-01-21,80
loc-b,white,2026-01-07,60
loc-b,white,2026-01-21,100
"""

SMALL_CSV = """Location_id,material_type,date,fill_level_perc
loc-a,brown,2026-01-05,20
loc-a,brown,2026-01-19,50
"""


@pytest.fixture()
def client() -> TestClient:
    """TestClient over a reset in-memory dataset store."""
    store.reset()
    return TestClient(app)


def upload_csv(
    client: TestClient,
    content: str = VALID_CSV,
    name: str = "glass.csv",
) -> None:
    """Upload synthetic CSV content; fail the test on a non-200 response."""
    response = client.post(
        "/api/datasets",
        files={"file": (name, content.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200, response.text
