"""The FastAPI application.

Errors follow RFC 7807 problem details and timestamps are ISO 8601 UTC, per
spec 7.5. The router layer never decides a rule — it resolves a service, hands
it the request, and turns whatever comes back into the wire shape.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.routers import auth, games, play, results
from app.repositories.interfaces import Repositories
from app.repositories.memory import MemoryRepositories
from app.repositories.models import Base
from app.repositories.sqlalchemy_repos import (
    SqlAlchemyRepositories,
    create_session_factory,
    create_sqlite_engine,
)
from app.seed import seed_demo_game
from app.services.errors import ServiceError

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


def build_repositories(backend: str | None = None) -> Repositories:
    """Pick a persistence implementation.

    This is the whole of step 4's swap: the services and the domain never
    learn which one they got. `memory` keeps the in-memory set from step 3;
    `sqlite` uses SQLAlchemy against a file, or against `:memory:` for tests.
    """
    choice = backend or os.environ.get("REPOSITORY_BACKEND", "memory")
    if choice == "memory":
        return MemoryRepositories()

    url = os.environ.get("DATABASE_URL", "sqlite:///./tennis.db")
    engine = create_sqlite_engine(url)
    # Alembic owns the schema for a real database; create_all is here so a
    # throwaway in-memory database works without running migrations first.
    Base.metadata.create_all(engine)
    return SqlAlchemyRepositories(create_session_factory(engine)())


def create_app(*, seed: bool = True, repositories: Repositories | None = None) -> FastAPI:
    app = FastAPI(
        title="Tennis Prediction Game",
        version="0.1.0",
        description="The agreement between the React frontend and the FastAPI backend.",
        servers=[{"url": "/api", "description": "Same-origin API"}],
    )

    repos = repositories if repositories is not None else build_repositories()
    if seed and repos.tournaments.get("roland-garros-2026") is None:
        seed_demo_game(repos)
    app.state.repositories = repos

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

    return app


app = create_app()
