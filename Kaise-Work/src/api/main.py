"""WasteRouting.AI API — M10 (docs/contracts.md §5).

Thin transport layer: routers from ``src.api.endpoints`` under the ``/api``
prefix, the M0 root ``/health``, and exception handlers mapping domain errors
to contract §5.3 responses (404 no dataset, 422 validation messages, 422 full
§1 error list on rejected uploads).

Run from the repository root:
    uvicorn src.api.main:app --reload

Single-process Docker deployment: when a built frontend bundle exists at
``SPA_DIST_DIR``, the same app also serves the React SPA at ``/`` with an
SPA fallback (``src.api.spa``) — registered last so ``/api`` routes and
``/health`` keep priority (README "Run with Docker").
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.endpoints import router
from src.api.errors import ApiError, DemoDatasetMissingError
from src.api.spa import install_spa
from src.api.state import NoDatasetError
from src.collection.policy import PolicyConfigError
from src.routing.schemas import RoutingSchemaError
from src.routing.solver import RoutingSolverError

SPA_DIST_DIR = Path("frontend/dist")
"""Built frontend bundle served by the same process when present (Docker
image copies stage-1 ``frontend/dist`` here); absent locally without a
frontend build -> the SPA route is simply not installed."""


def create_app(dist_dir: Path | None = None) -> FastAPI:
    """Build the FastAPI app; ``dist_dir`` (default ``SPA_DIST_DIR``) mounts
    the built SPA when it exists, otherwise the install is a no-op."""
    application = FastAPI(title="WasteRouting.AI API")
    application.include_router(router)

    @application.get("/health")
    async def health() -> dict[str, str]:
        """Liveness probe returning the service status payload (M0, kept)."""
        return {"status": "ok", "service": "wasterouting-api"}

    @application.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        """Transport errors with explicit payloads (e.g. rejected uploads, §5.3)."""
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @application.exception_handler(NoDatasetError)
    async def no_dataset_handler(_request: Request, exc: NoDatasetError) -> JSONResponse:
        """No active dataset -> 404 (contract §5.3)."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(DemoDatasetMissingError)
    async def demo_dataset_missing_handler(
        _request: Request, exc: DemoDatasetMissingError
    ) -> JSONResponse:
        """Server-side demo CSV constant path absent -> 404 (contract §5.1)."""
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(PolicyConfigError)
    @application.exception_handler(RoutingSchemaError)
    async def config_validation_handler(
        _request: Request, exc: PolicyConfigError | RoutingSchemaError
    ) -> JSONResponse:
        """Invalid §3.1/§4.6 overrides -> 422 with the domain validation message
        (contract §5.3: validated by constructing the config objects)."""
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(RoutingSolverError)
    async def solver_error_handler(_request: Request, exc: RoutingSolverError) -> JSONResponse:
        """Solver statuses NOT_SOLVED/INVALID are internal bugs (M9 docstring),
        not user-facing routing outcomes -> 500 with the message."""
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    # SPA serving registered LAST: every /api route and /health above keeps
    # priority (route order = match order).
    install_spa(application, dist_dir if dist_dir is not None else SPA_DIST_DIR)
    return application


app = create_app()

__all__ = ["app", "create_app"]
