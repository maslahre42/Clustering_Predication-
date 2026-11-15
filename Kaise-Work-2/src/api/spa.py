"""Static SPA serving for the single-process Docker deployment.

``install_spa(app, dist_dir)`` wires the built React bundle
(``frontend/dist``) into the FastAPI app so ONE process serves both the API
and the frontend (README "Run with Docker"). Registered LAST, after every
``/api`` route and ``/health``, so the API keeps priority:

- GET of an existing static file (e.g. ``/assets/index-abc.js``) → that file.
- GET of a path with no file extension and no API match → ``index.html``
  (SPA client-side routing fallback).
- GET of a path with an extension but no matching file → 404 JSON.
- ``/api``/``/api/...`` and ``/health``/``/health/...`` paths never fall back
  to the SPA — unknown ones stay 404 JSON.

Traversal-safe: a candidate file is served only when it resolves inside
``dist_dir``. When the bundle is absent (local dev without ``npm run
build``) the install is a no-op and behaviour is unchanged.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def install_spa(app: FastAPI, dist_dir: Path) -> None:
    """Add the SPA catch-all GET route when a built bundle exists at
    ``dist_dir``; no-op otherwise. Must be called after all API routes are
    registered (route order = priority)."""
    index = dist_dir / "index.html"
    if not index.is_file():
        return  # no built bundle (local dev) -> leave the app untouched
    resolved_dist = dist_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # API and health paths never fall back to the SPA: unknown ones stay
        # 404 JSON (real /api and /health routes were registered earlier and
        # win; this guard covers unmatched ones).
        if (
            full_path == "api"
            or full_path.startswith("api/")
            or full_path == "health"
            or full_path.startswith("health/")
        ):
            raise HTTPException(status_code=404, detail="Not Found")
        if any(part == ".." for part in Path(full_path).parts):
            # Traversal attempt (URL-encoded %2f arrives decoded here) —
            # never serve anything, not even the SPA fallback.
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (resolved_dist / full_path).resolve()
        if candidate.is_relative_to(resolved_dist) and candidate.is_file():
            return FileResponse(candidate)
        if Path(full_path).suffix:
            # Looks like an asset but does not exist -> 404, never index.html.
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index)  # SPA client-side route fallback


__all__ = ["install_spa"]
