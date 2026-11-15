"""API-level error types mapped to HTTP responses in ``src.api.main``.

Domain errors (:class:`src.collection.policy.PolicyConfigError`,
:class:`src.routing.schemas.RoutingSchemaError`) are raised unchanged by the
services and mapped to 422 with the validation message (contract §5.3).
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """Transport error carrying an HTTP status and a JSON ``detail`` payload."""

    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


class DemoDatasetMissingError(RuntimeError):
    """The server-side demo CSV constant path does not exist (POST
    /api/datasets/demo -> 404; contract §5.1: the path is never
    client-supplied, so absence is a server-side condition)."""
