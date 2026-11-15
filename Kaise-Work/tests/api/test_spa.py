"""Static SPA serving (``src.api.spa``) — single-process Docker deployment.

Deployment brief task 3 §1: the built ``frontend/dist`` is served by the
same FastAPI process; ``/api`` routes and ``/health`` keep priority; any
non-API GET without a file extension falls back to ``index.html``. The SPA
is wired via ``install_spa`` on a fresh ``create_app`` with a synthetic
dist dir (never the real bundle, which may or may not exist locally).
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import SPA_DIST_DIR, create_app
from tests.api.conftest import VALID_CSV


def make_client(tmp_path: Path, files: dict[str, str]) -> TestClient:
    """TestClient over an app whose SPA is a synthetic dist directory."""
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return TestClient(create_app(tmp_path))


class TestSpaServing:
    def test_no_bundle_noop_unknown_path_404(self, tmp_path: Path) -> None:
        # No dist dir at all (local dev without a frontend build).
        client = TestClient(create_app(tmp_path / "absent"))
        assert client.get("/").status_code == 404

    def test_root_serves_index_html(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html><body>SPA</body></html>"})
        response = client.get("/")
        assert response.status_code == 200
        assert "SPA" in response.text
        assert response.headers["content-type"].startswith("text/html")

    def test_health_still_json(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "wasterouting-api"}

    def test_unknown_path_without_extension_falls_back_to_index(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        response = client.get("/some/client/route")
        assert response.status_code == 200
        assert "SPA" in response.text

    def test_existing_static_file_served(self, tmp_path: Path) -> None:
        client = make_client(
            tmp_path,
            {"index.html": "<html>SPA</html>", "assets/app.js": "console.log(1);"},
        )
        response = client.get("/assets/app.js")
        assert response.status_code == 200
        assert "console.log(1);" in response.text

    def test_encoded_traversal_path_404(self, tmp_path: Path) -> None:
        """URL-encoded ../ traversal must never escape the dist dir."""
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        assert client.get("/..%2f..%2fetc%2fpasswd").status_code == 404
        assert client.get("/..%2f..%2fetc%2fpasswd.js").status_code == 404

    def test_missing_asset_with_extension_404(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        assert client.get("/assets/missing.js").status_code == 404

    def test_unknown_api_path_stays_json_404(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        response = client.get("/api/unknown")
        assert response.status_code == 404
        assert "SPA" not in response.text

    def test_api_upload_unaffected(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        response = client.post(
            "/api/datasets",
            files={"file": ("glass.csv", VALID_CSV.encode("utf-8"), "text/csv")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["n_rows"] == 10

    def test_health_subpath_never_falls_back(self, tmp_path: Path) -> None:
        client = make_client(tmp_path, {"index.html": "<html>SPA</html>"})
        assert client.get("/health/nope").status_code == 404


class TestRealAppWiring:
    def test_default_dist_dir_constant(self) -> None:
        assert Path("frontend/dist") == SPA_DIST_DIR

    def test_real_app_serves_spa_when_bundle_exists(self) -> None:
        # Covers the actual module-level `app` wiring when a bundle exists
        # (skipped on clean checkouts without a frontend build, e.g. CI).
        if not (SPA_DIST_DIR / "index.html").is_file():
            import pytest

            pytest.skip("frontend/dist not built — SPA not installed in this checkout")
        from src.api.main import app

        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/html")
            assert client.get("/health").json()["status"] == "ok"
