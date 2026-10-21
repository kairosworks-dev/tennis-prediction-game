# One image: the FastAPI backend serves the API under /api and the built
# frontend at /. Build: `make docker-build`. Run: see README, "Build and run
# the image".
#
# Pins: Node 24 is the current LTS and builds the frontend; Python 3.12 matches
# `requires-python`; uv comes from its official image at a fixed version.

# --- Stage 1: build the frontend against the real backend (not the mock) ----
FROM node:24-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_CLIENT=http
RUN npm run build

# --- Stage 2: install the backend from the lockfile --------------------------
FROM python:3.12-slim-bookworm AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy
WORKDIR /build
COPY backend/pyproject.toml backend/uv.lock ./
# --locked (not --frozen): fail the build if uv.lock disagrees with
# pyproject.toml instead of trusting a stale lockfile or resolving fresh.
RUN uv sync --locked --no-dev --no-install-project

# --- Stage 3: runtime — no Node, no npm, no uv --------------------------------
FROM python:3.12-slim-bookworm
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    REPOSITORY_BACKEND=sqlalchemy \
    DATABASE_URL=sqlite:////data/tennis.db \
    FRONTEND_DIR=/app/static

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data \
    && chown app:app /data

WORKDIR /app
COPY --from=backend /opt/venv /opt/venv
COPY backend/alembic.ini backend/scripts_seed.py ./
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY --from=frontend /build/dist ./static
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "app.healthcheck"]
ENTRYPOINT ["docker-entrypoint.sh"]
