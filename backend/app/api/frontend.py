"""Serve the built frontend from the same process as the API.

Only mounted when the build output exists (see `create_app`), so local
development and the unit suite never see it. It adds no route: the app shell is
served from the 404 handler, so Starlette's own routing is untouched and a
wrong method (405 with `Allow`) or a trailing-slash redirect behaves exactly as
without a build. Only a GET/HEAD that matched nothing, outside `/api` and
`/assets`, gets a file or the index; everything else keeps the default JSON 404.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

#: Where the image puts the built frontend.
DEFAULT_FRONTEND_DIR = "/app/static"


def mount_frontend(app: FastAPI, directory: Path) -> None:
    root = directory.resolve()
    index = root / "index.html"
    if (root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    async def not_found(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, StarletteHTTPException)
        path = request.url.path.lstrip("/")
        spa_path = (
            request.method in {"GET", "HEAD"}
            and path != "api"
            and not path.startswith(("api/", "assets/"))
        )
        if not spa_path:
            return await http_exception_handler(request, exc)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index, media_type="text/html")

    app.add_exception_handler(404, not_found)
