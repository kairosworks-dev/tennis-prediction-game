"""The FastAPI application.

Errors follow RFC 7807 problem details and timestamps are ISO 8601 UTC, per
spec 7.5. The router layer never decides a rule — it resolves a service, hands
it the request, and turns whatever comes back into the wire shape.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session, sessionmaker

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


#: Opens a `Repositories` for the life of one request and closes it after.
RepositoryScope = Callable[[], AbstractContextManager[Repositories]]


def _fixed_scope(repos: Repositories) -> RepositoryScope:
    """One shared instance, for the in-memory set and for injected test doubles."""

    @contextmanager
    def scope() -> Iterator[Repositories]:
        yield repos

    return scope


def _session_scope(session_factory: sessionmaker[Session]) -> RepositoryScope:
    """A fresh session per request.

    A SQLAlchemy Session is not thread-safe, and uvicorn runs sync endpoints in
    a threadpool, so sharing one across requests corrupts results under any
    concurrency at all — it surfaces as an IndexError inside SQLAlchemy's row
    handling rather than as anything that names the real cause. One session per
    request is the standard answer and the only correct one here.
    """

    @contextmanager
    def scope() -> Iterator[Repositories]:
        session = session_factory()
        try:
            yield SqlAlchemyRepositories(session)
        finally:
            session.close()

    return scope


def build_repository_scope(backend: str | None = None) -> RepositoryScope:
    """Pick a persistence implementation.

    This is the whole of step 4's swap: the services and the domain never learn
    which one they got. `memory` keeps the in-memory set from step 3; `sqlite`
    uses SQLAlchemy against a file, or against `:memory:` for tests.
    """
    choice = backend or os.environ.get("REPOSITORY_BACKEND", "memory")
    if choice == "memory":
        return _fixed_scope(MemoryRepositories())

    url = os.environ.get("DATABASE_URL", "sqlite:///./tennis.db")
    engine = create_sqlite_engine(url)
    # Alembic owns the schema for a real database; create_all is here so a
    # throwaway in-memory database works without running migrations first.
    Base.metadata.create_all(engine)
    return _session_scope(create_session_factory(engine))


def build_repositories(backend: str | None = None) -> Repositories:
    """A single `Repositories` outside a request — for scripts and seeding.

    Holds its session open for the caller's lifetime, which is right for a
    one-shot script and wrong for a server; the server uses the scope above.
    """
    scope = build_repository_scope(backend)
    context = scope()
    return context.__enter__()


def create_app(*, seed: bool = True, repositories: Repositories | None = None) -> FastAPI:
    app = FastAPI(
        title="Tennis Prediction Game",
        version="0.1.0",
        description="The agreement between the React frontend and the FastAPI backend.",
        servers=[{"url": "/api", "description": "Same-origin API"}],
    )

    scope = _fixed_scope(repositories) if repositories is not None else build_repository_scope()
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

    return app


app = create_app()
