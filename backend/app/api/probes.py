"""Operational probes: `/health` and `/ready`.

These are for the container runtime and the platform, not for the frontend, so
they sit at the root (outside `/api`) and are left out of `openapi.yaml` — the
narrow exception to hard rule 3 recorded as decision D17 in the spec.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(include_in_schema=False)


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process answers. Deliberately never touches the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    """Readiness: 200 only when the configured store answers a trivial query."""
    # Rollback drill (#10): an injected fault, set only on production; reverted after the drill.
    if os.environ.get("DRILL_READY_FAIL") == "1":
        return JSONResponse({"status": "unavailable"}, status_code=503)
    try:
        with request.app.state.repository_scope() as repos:
            repos.ping()
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})
