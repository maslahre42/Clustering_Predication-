"""GET /health returns the service status payload (M0 smoke)."""

import asyncio

from fastapi.routing import APIRoute

from src.api.main import app


def test_health_endpoint_returns_ok() -> None:
    health_routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path == "/health"]
    assert len(health_routes) == 1, "exactly one /health route expected"
    result = asyncio.run(health_routes[0].endpoint())
    assert result == {"status": "ok", "service": "wasterouting-api"}
