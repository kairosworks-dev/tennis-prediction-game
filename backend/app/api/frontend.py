"""Serve the built frontend from the same process as the API.

Only mounted when the build output exists (see `create_app`), so local
development and the unit suite never see it. The catch-all below must not
shadow the backend: anything under `/api`, and any non-GET method, keeps the
JSON 404 FastAPI gives an unknown route.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

#: Where the image puts the built frontend.
DEFAULT_FRONTEND_DIR = "/app/static"

_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]


def _not_found() -> JSONResponse:
    return JSONResponse({"detail": "Not Found"}, status_code=404)


def mount_frontend(app: FastAPI, directory: Path) -> None:
    root = directory.resolve()
    index = root / "index.html"
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=_METHODS, include_in_schema=False)
    def spa(request: Request, path: str) -> Response:
        if request.method not in {"GET", "HEAD"} or path == "api" or path.startswith("api/"):
            return _not_found()
        if path.startswith("assets/"):
            return _not_found()  # a missing asset is a 404, not the app shell
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, media_type="text/html")
