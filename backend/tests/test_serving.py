"""The static frontend mount and the operational probes (issue #2).

The probes run against every repository implementation via the `client`
fixture; the mount tests build an app around a throwaway frontend directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.interfaces import Repositories
from app.repositories.memory import MemoryRepositories

INDEX = "<!doctype html><title>app shell</title>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX)
    (root / "assets" / "app-abc123.js").write_text("console.log(1)")
    (root / "favicon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("outside the frontend directory")
    return root


@pytest.fixture
def served(dist: Path) -> TestClient:
    return TestClient(create_app(repositories=MemoryRepositories(), frontend_dir=dist))


def test_index_is_served_at_the_root(served: TestClient) -> None:
    response = served.get("/")
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")


def test_a_hashed_asset_is_served_with_its_content_type(served: TestClient) -> None:
    response = served.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_a_root_file_is_served(served: TestClient) -> None:
    assert served.get("/favicon.svg").text == "<svg/>"


def test_a_deep_link_falls_back_to_the_index(served: TestClient) -> None:
    response = served.get("/games/roland-garros-2026/play")
    assert response.status_code == 200
    assert response.text == INDEX


def test_a_missing_asset_is_a_404_not_the_app_shell(served: TestClient) -> None:
    assert served.get("/assets/nope.js").status_code == 404


def test_unknown_api_paths_stay_a_json_404(served: TestClient) -> None:
    for method in ("get", "post"):
        response = getattr(served, method)("/api/nothing-here")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": "Not Found"}


def test_the_backend_routes_are_not_shadowed(served: TestClient) -> None:
    assert served.get("/docs").status_code == 200
    assert served.get("/openapi.json").json()["info"]["title"] == "Tennis Prediction Game"
    login = served.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert login.headers["content-type"].startswith("application/problem+json")
    assert served.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path",
    ["/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/../secret.txt", "/assets/..%2fsecret.txt"],
)
def test_traversal_never_leaves_the_frontend_directory(served: TestClient, path: str) -> None:
    response = served.get(path)
    assert "outside the frontend directory" not in response.text


def test_nothing_is_mounted_when_the_directory_is_absent(tmp_path: Path) -> None:
    app = create_app(repositories=MemoryRepositories(), frontend_dir=tmp_path / "missing")
    client = TestClient(app)
    assert client.get("/").status_code == 404
    assert client.get("/games/x").status_code == 404


def test_the_directory_comes_from_the_environment(
    dist: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FRONTEND_DIR", str(dist))
    client = TestClient(create_app(repositories=MemoryRepositories()))
    assert client.get("/").text == INDEX


def test_health_is_ok_and_not_in_the_contract(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    paths = client.get("/openapi.json").json()["paths"]
    assert "/health" not in paths
    assert "/ready" not in paths


def test_ready_is_ok_when_the_store_answers(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_is_503_when_the_store_does_not_answer(
    repositories: Repositories, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down() -> None:
        raise ConnectionError("database unreachable")

    monkeypatch.setattr(repositories, "ping", down)
    client = TestClient(create_app(repositories=repositories))
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200
