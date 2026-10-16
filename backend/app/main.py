"""The FastAPI application.

Errors follow RFC 7807 problem details and timestamps are ISO 8601 UTC, per
spec 7.5. The router layer never decides a rule — it resolves a service, hands
it the request, and turns whatever comes back into the wire shape.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api import probes
from app.api.frontend import DEFAULT_FRONTEND_DIR, mount_frontend
from app.api.routers import auth, games, play, results
from app.bootstrap import build_repositories, build_repository_scope, fixed_scope
from app.repositories.interfaces import Repositories
from app.seed import seed_demo_game
from app.services.errors import ServiceError

#: `build_repository_scope` and `build_repositories` live in `app.bootstrap`; they
#: are re-exported so `from app.main import build_repository_scope` keeps working.
__all__ = ["app", "build_repositories", "build_repository_scope", "create_app"]

PROBLEM_BASE = "https://tennis-prediction-game.invalid/problems"

_SLUGS = {
    400: "bad-request",
    401: "unauthorized",
    403: "forbidden",
    404: "not-found",
    409: "conflict",
    422: "validation-failed",
}

_TITLES = {
    400: "Bad request",
    401: "Not signed in",
    403: "Not allowed",
    404: "Not found",
    409: "Conflict",
    422: "Validation failed",
}


def create_app(
    *,
    seed: bool = True,
    repositories: Repositories | None = None,
    frontend_dir: Path | None = None,
) -> FastAPI:
    """Build the app.

    `frontend_dir` (default: `FRONTEND_DIR`, else the image's path) is mounted
    only if it holds a build, so nothing changes without one.
    """
    app = FastAPI(
        title="Tennis Prediction Game",
        version="0.1.0",
        description="The agreement between the React frontend and the FastAPI backend.",
        servers=[{"url": "/api", "description": "Same-origin API"}],
    )

    scope = fixed_scope(repositories) if repositories is not None else build_repository_scope()
    if seed:
        with scope() as repos:
            if repos.tournaments.get("roland-garros-2026") is None:
                seed_demo_game(repos)
    app.state.repository_scope = scope

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> Response:
        del request
        status = exc.status
        body = {
            "type": f"{PROBLEM_BASE}/{_SLUGS.get(status, 'error')}",
            "title": _TITLES.get(status, "Error"),
            "status": status,
            "detail": exc.detail,
        }
        if exc.errors:
            body["errors"] = exc.errors
        return JSONResponse(body, status_code=status, media_type="application/problem+json")

    for router in (auth.router, games.router, play.router, results.router):
        app.include_router(router, prefix="/api")
    app.include_router(probes.router)

    static_dir = frontend_dir or Path(os.environ.get("FRONTEND_DIR", DEFAULT_FRONTEND_DIR))
    if (static_dir / "index.html").is_file():
        mount_frontend(app, static_dir)  # SPA served from the 404 handler

    return app


app = create_app()
