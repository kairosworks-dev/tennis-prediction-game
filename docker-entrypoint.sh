#!/bin/sh
# Container start-up: migrate, seed, then hand the process to uvicorn.
# `set -e` means a failed migration exits non-zero and uvicorn never starts;
# `exec` makes uvicorn PID 1 so SIGTERM from `docker stop` reaches it.
set -eu

# Image-only guard: the development default in app/api/deps.py is for local
# runs and the tests, never for a container.
: "${SESSION_SECRET:?SESSION_SECRET must be set (any long random string)}"

# Bound the wait on an unreachable Postgres (libpq honours this); retrying
# until it is up is the orchestrator's job, not this script's.
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"

alembic upgrade head
python scripts_seed.py   # idempotent: prints "Already seeded" on later starts

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
