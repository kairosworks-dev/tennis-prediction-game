"""The FastAPI application.

Errors follow RFC 7807 problem details and timestamps are ISO 8601 UTC, per
spec 7.5. The router layer never decides a rule — it resolves a service, hands
it the request, and turns whatever comes back into the wire shape.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.routers import auth, games, play, results
from app.repositories.memory import MemoryRepositories
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


def create_app(*, seed: bool = True) -> FastAPI:
    app = FastAPI(
        title="Tennis Prediction Game",
        version="0.1.0",
        description="The agreement between the React frontend and the FastAPI backend.",
        servers=[{"url": "/api", "description": "Same-origin API"}],
    )

    # Step 3 wires the in-memory set; step 4 swaps this one line.
    repositories = MemoryRepositories()
    if seed:
        seed_demo_game(repositories)
    app.state.repositories = repositories

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
