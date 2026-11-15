"""Hosted deployment knobs (``src.api.hosted``) — env-driven solver limits.

Deployment brief task 3 §4: ``WASTECITY_SOLVER_TIME_LIMIT_S`` overrides the
§4.6 ``solver_time_limit_s`` *default* only when the request does not
override it; ``WASTECITY_MAX_STOPS`` caps the candidates handed to the
solver deterministically (first N in the §3.3 order) and the remainder
surfaces in ``unserved`` with reason ``hosted_demo_stop_cap`` — never
silently dropped. Invalid values fall back with a warning log (500-free).
Unset → byte-identical default behaviour (labels all ``[demo assumption]``).
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api import hosted, services
from tests.api.conftest import upload_csv

AS_OF = "2026-02-15"


def route_body(client: TestClient, **routing: Any) -> dict[str, Any]:
    """POST /api/route with optional routing_config overrides."""
    body: dict[str, Any] = {"as_of_date": AS_OF}
    if routing:
        body["routing_config"] = routing
    response = client.post("/api/route", json=body)
    assert response.status_code == 200, response.text
    return response.json()


class TestEnvSolverTimeLimit:
    def test_env_overrides_default_when_request_does_not(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(hosted.ENV_SOLVER_TIME_LIMIT_S, "1.5")
        upload_csv(client)
        body = route_body(client)
        labels = "\n".join(body["assumptions"])
        assert "solver_time_limit_s=1.5" in labels
        assert "[deployment setting]" in labels
        assert "WASTECITY_SOLVER_TIME_LIMIT_S" in labels
        assert "not a demo assumption" in labels

    def test_request_override_beats_env(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(hosted.ENV_SOLVER_TIME_LIMIT_S, "1.5")
        upload_csv(client)
        body = route_body(client, solver_time_limit_s=0.5)
        labels = "\n".join(body["assumptions"])
        assert "solver_time_limit_s=0.5" in labels
        assert "solver_time_limit_s=1.5" not in labels
        assert "[deployment setting]" not in labels

    def test_unset_is_byte_identical_default(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(hosted.ENV_SOLVER_TIME_LIMIT_S, raising=False)
        monkeypatch.delenv(hosted.ENV_MAX_STOPS, raising=False)
        upload_csv(client)
        body = route_body(client)
        assert all(
            "[demo assumption]" in label or "[representative]" in label or "[literature]" in label
            for label in body["assumptions"]
        )
        joined = "\n".join(body["assumptions"])
        assert f"solver_time_limit_s={services.demo_routing_config().solver_time_limit_s}" in joined
        assert "deployment setting" not in joined

    @pytest.mark.parametrize("raw", ["not-a-float", "-2", "0"])
    def test_invalid_value_falls_back_with_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        raw: str,
    ) -> None:
        monkeypatch.setenv(hosted.ENV_SOLVER_TIME_LIMIT_S, raw)
        upload_csv(client)
        with caplog.at_level(logging.WARNING, logger="src.api.hosted"):
            body = route_body(client)
        assert hosted.hosted_solver_time_limit_s() is None  # 500-free fallback
        assert all(
            "[demo assumption]" in label or "[representative]" in label or "[literature]" in label
            for label in body["assumptions"]
        )
        assert any(record.levelno == logging.WARNING for record in caplog.records)
        assert "not a float" in caplog.text or "positive float" in caplog.text

    @pytest.mark.parametrize("raw", ["inf", "-inf", "nan", "1e400"])
    def test_non_finite_value_rejected_with_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        raw: str,
    ) -> None:
        """inf/nan/1e400 pass naive `> 0` checks but would poison the solver
        cap — rejected via math.isfinite, same warning + fallback path."""
        monkeypatch.setenv(hosted.ENV_SOLVER_TIME_LIMIT_S, raw)
        upload_csv(client)
        with caplog.at_level(logging.WARNING, logger="src.api.hosted"):
            body = route_body(client)
        assert hosted.hosted_solver_time_limit_s() is None  # 500-free fallback
        assert all(
            "[demo assumption]" in label or "[representative]" in label or "[literature]" in label
            for label in body["assumptions"]
        )
        assert "solver_time_limit_s=inf" not in "\n".join(body["assumptions"])
        assert any(
            record.levelno == logging.WARNING and "finite" in record.getMessage()
            for record in caplog.records
        )

    def test_blank_value_falls_back(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(hosted.ENV_SOLVER_TIME_LIMIT_S, "   ")
        upload_csv(client)
        body = route_body(client)
        assert all(
            "[demo assumption]" in label or "[representative]" in label or "[literature]" in label
            for label in body["assumptions"]
        )


class TestEnvMaxStops:
    def test_cap_keeps_first_n_and_surfaces_rest_in_unserved(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(hosted.ENV_MAX_STOPS, "2")
        upload_csv(client)
        body = route_body(client)
        selected = body["selection"]["selected"]
        assert len(selected) == 4  # synthetic fixture policy selection
        unserved = body["solution"]["unserved"]
        capped = [item for item in unserved if item["reason"].startswith("hosted_demo_stop_cap")]
        assert len(capped) == 2
        # Deterministic: the kept candidates are the FIRST 2 in the §3.3
        # order; the capped-out are exactly the remaining (tail) candidates
        # (set comparison: the unserved list is presentation-sorted).
        assert {(item["location_id"], item["material_type"]) for item in capped} == {
            (candidate["location_id"], candidate["material_type"]) for candidate in selected[2:]
        }
        for item in capped:
            assert "WASTECITY_MAX_STOPS=2" in item["reason"]
        # Reconcile invariant holds with the cap active.
        totals = body["solution"]["totals"]
        assert totals["stops_total"] == 4
        assert totals["stops_served"] + len(unserved) == totals["stops_total"]
        # Selection echo is the full, unchanged policy output.
        assert len(body["selection"]["selected"]) == 4
        # Cap visible in the assumptions labels.
        joined = "\n".join(body["assumptions"])
        assert "[deployment setting] WASTECITY_MAX_STOPS" in joined
        assert "hosted_demo_stop_cap" in joined
        # Solver only received the kept stops (keyed by full series).
        served_stops = {
            (node["location_id"], node["material_type"])
            for route in body["solution"]["routes"]
            for node in route["sequence"]
            if node["node_type"] == "stop"
        }
        assert {(item["location_id"], item["material_type"]) for item in capped}.isdisjoint(
            served_stops
        )

    def test_cap_ge_selected_is_noop(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(hosted.ENV_MAX_STOPS, "99")
        upload_csv(client)
        body = route_body(client)
        assert not any(
            item["reason"].startswith("hosted_demo_stop_cap")
            for item in body["solution"]["unserved"]
        )
        assert "deployment setting" not in "\n".join(body["assumptions"])

    def test_unset_no_cap(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(hosted.ENV_MAX_STOPS, raising=False)
        upload_csv(client)
        body = route_body(client)
        assert not any(
            "hosted_demo_stop_cap" in item["reason"] for item in body["solution"]["unserved"]
        )
        assert all(
            "[demo assumption]" in label or "[representative]" in label or "[literature]" in label
            for label in body["assumptions"]
        )

    @pytest.mark.parametrize("raw", ["abc", "-1", "0"])
    def test_invalid_value_no_cap_with_warning(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        raw: str,
    ) -> None:
        monkeypatch.setenv(hosted.ENV_MAX_STOPS, raw)
        upload_csv(client)
        with caplog.at_level(logging.WARNING, logger="src.api.hosted"):
            body = route_body(client)
        assert hosted.hosted_max_stops() is None  # 500-free fallback
        assert not any(
            item["reason"].startswith("hosted_demo_stop_cap")
            for item in body["solution"]["unserved"]
        )
        assert any(record.levelno == logging.WARNING for record in caplog.records)

    def test_comparison_stays_uncapped_full_basis(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """§4.7 ruling: the stop cap applies to the interactive route demo
        only — /api/comparison's ortools row must reflect the FULL policy
        selection (stops_total == n_selected, not the cap)."""
        monkeypatch.setenv(hosted.ENV_MAX_STOPS, "2")
        upload_csv(client)
        response = client.get("/api/comparison")
        assert response.status_code == 200, response.text
        ortools_row = response.json()["scenarios"][3]  # v4 order: fixed_frequency is [0]
        assert ortools_row["method"] == "ortools"
        assert ortools_row["stops_total"] == 4  # full selection, NOT the cap
        # The same env caps the interactive route as usual (contrast).
        body = route_body(client)
        assert any(
            item["reason"].startswith("hosted_demo_stop_cap")
            for item in body["solution"]["unserved"]
        )

    def test_both_knobs_together(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(hosted.ENV_SOLVER_TIME_LIMIT_S, "2.0")
        monkeypatch.setenv(hosted.ENV_MAX_STOPS, "2")
        upload_csv(client)
        body = route_body(client)
        joined = "\n".join(body["assumptions"])
        assert "solver_time_limit_s=2.0" in joined
        assert "[deployment setting] WASTECITY_MAX_STOPS" in joined
        assert any(
            item["reason"].startswith("hosted_demo_stop_cap")
            for item in body["solution"]["unserved"]
        )
