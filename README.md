# Tennis Prediction Game

[![CI](https://github.com/kairosworks-dev/tennis-prediction-game/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/kairosworks-dev/tennis-prediction-game/actions/workflows/ci.yml)

A web application for running tennis prediction competitions among a group of friends.
One competition covers one tournament. Participants predict the tournament outcome
before play begins and submit smaller predictions round by round. Points accumulate
into a leaderboard.

No money, no odds, no payouts — this replaces a hand-maintained spreadsheet and a
chat thread full of bets, not a bookmaker.

The authoritative specification is [`docs/product-and-technical-spec.md`](docs/product-and-technical-spec.md).
Where the code currently stands against it — unmet definitions of done, known
defects, open decisions — is [`docs/status.md`](docs/status.md).
Instructions for coding agents are in [`AGENTS.md`](AGENTS.md).

---

## Status

Built in four sequential steps. Each step has a definition of done in Section 9 of
the spec, and no step starts before the previous one meets it.

| Step | Scope | State |
|---|---|---|
| 1 | React frontend against a mocked service layer | **Done** |
| 2 | `openapi.yaml` derived from the frontend service layer | **Done** |
| 3 | FastAPI backend with in-memory repositories | **Done** |
| 4 | SQLAlchemy and SQLite persistence | **Done** |

All four are done, to the narrowed screen surface set by decision D14 — nineteen
API operations rather than thirty-four, with the deferred screens recorded in
spec section 13 rather than dropped. 215 tests pass; the backend suite runs
twice, once against each repository implementation.

Two definitions of done are still unmet and two defects are known.
[`docs/status.md`](docs/status.md) lists them, and is the right place to start
when picking this up again.

---

## Stack

**Frontend** — React 18, TypeScript (strict), Vite, React Router, TanStack Query,
React Hook Form with Zod, Tailwind CSS. Tested with Vitest and React Testing
Library. (Playwright is specified for one end-to-end path per role and is not
built yet — see [`docs/status.md`](docs/status.md).)

**Backend** — FastAPI, Pydantic v2, SQLAlchemy 2.0 with SQLite, Alembic, Argon2
password hashing, session cookies. Tested with pytest and the httpx test client.

`openapi.yaml` at the repository root is the single agreement between the two.

---

## Repository layout

```
/backend               FastAPI application, domain layer, repositories, tests
/frontend              React application and its service layer
/docs
  product-and-technical-spec.md   requirements, decisions, scope, backlog
  status.md                       where the code stands against that spec
  ai-usage-report.md              how this was built, and what it taught
  design/                         Claude Design artboards (source for the canvas)
AGENTS.md              instructions for coding agents — read this first
CLAUDE.md              points at AGENTS.md
Makefile               make run, make test, make check
/.github/workflows     CI (ci.yml): check, commit-gate, integration
Dockerfile             one image: backend serving the built frontend
docker-compose.yml     app + Postgres for dev, test and CI
.env.example           optional compose settings, placeholders only
openapi.yaml           the agreement between frontend and backend
README.md              this file
```

---

## Running it locally

Requires **Node 20+** and **[uv](https://docs.astral.sh/uv/)**.

```bash
make install
make run
```

`make run` migrates the database, seeds a demo game, starts the backend on
**:8000** and the frontend on **:5173** pointed at it, and Ctrl-C stops both.
Open http://localhost:5173.

Sign in as `you@example.com` to play, or `organiser@example.com` to reach the
results screen. Password for both: `deuce-demo-password`.

`make` on its own lists every target. The ones worth knowing:

| | |
|---|---|
| `make run` | Backend and frontend together, on SQLite |
| `make run-mock` | Frontend alone on in-memory fixtures — no backend, no database |
| `make reset-db` | Throw the database away and rebuild it from empty |
| `make check` | Lint, typecheck and every unit test (no Docker) |
| `make test-integration` | Build the compose stack on a separate project, test it over HTTP, tear it down |

### Running it without make

```bash
# terminal one
cd backend && uv sync && uv run alembic upgrade head && uv run python scripts_seed.py
REPOSITORY_BACKEND=sqlalchemy uv run uvicorn app.main:app --port 8000

# terminal two
cd frontend && npm install && VITE_API_CLIENT=http npm run dev
```

Vite proxies `/api` to port 8000, so the session cookie stays same-origin.

`VITE_API_CLIENT` is the only difference between the two modes — `http` for the
real backend, `mock` for fixtures. No code changes, which is what the service
layer exists for. Set it in `frontend/.env` to make a choice stick.

### Database

Configuration is environment variables:

- `DATABASE_URL` selects the database. Default: `sqlite:///./tennis.db`.
  Postgres example: `postgresql+psycopg://postgres:postgres@localhost:5433/tennis`.
  Bare `postgresql://` and `postgres://` URLs are accepted and rewritten to
  `postgresql+psycopg://` (the installed driver) in one place, `create_db_engine`;
  Alembic uses the same rewrite.
- `REPOSITORY_BACKEND` is `memory` (default) or `sqlalchemy`; `sqlite` is kept
  as an alias for `sqlalchemy`. The dialect comes from `DATABASE_URL` alone.
  Any other value stops start-up with an error.

On SQLite the app creates missing tables itself. On any other URL it does not:
Alembic owns the schema, and starting against an unmigrated database fails
with a message naming `alembic upgrade head`.

A throwaway local Postgres (development placeholder credentials only):

```bash
docker run --rm -d --name tennis-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tennis -p 5433:5432 postgres:16
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/tennis
cd backend && uv run alembic upgrade head && uv run python scripts_seed.py
REPOSITORY_BACKEND=sqlalchemy uv run uvicorn app.main:app --port 8000
```

A second run of the seed script prints "Already seeded".

### Build and run the image

One image holds the whole app: the backend serves the API under `/api` and the
built frontend at `/`. It needs Docker only.

```bash
make docker-build        # docker build -t tennis-prediction-game .
docker run --rm -p 8000:8000 -e SESSION_SECRET=change-me tennis-prediction-game
```

Open <http://localhost:8000> and sign in as `you@example.com` with the demo
password. At start the container migrates its database, runs the idempotent demo
seed (on every start, for now) and then starts uvicorn; if the migration fails
it exits non-zero. It runs as a non-root user (UID 10001).

By default the data is a SQLite file at `/data/tennis.db`. **Without a volume it
is lost when the container is removed.** To keep it, mount a volume on `/data`
(`-v tennis-data:/data`; a bind mount must be writable by UID 10001).

| Variable | In the image | Meaning |
|---|---|---|
| `SESSION_SECRET` | **required**, no default | Signs the session cookie. The container refuses to start without it. |
| `DATABASE_URL` | `sqlite:////data/tennis.db` | Any SQLAlchemy URL; a bare `postgresql://` URL works. An unreachable database makes the container exit non-zero within `PGCONNECT_TIMEOUT` (10 s by default), with the error in `docker logs`. |
| `REPOSITORY_BACKEND` | `sqlalchemy` | See the backend conventions. |
| `COOKIE_SECURE` | unset | Passed through; see issue #7. |
| `FRONTEND_DIR` | `/app/static` | Where the built frontend lives; served only if it exists. |

`GET /health` (process is up, no database) and `GET /ready` (database answers)
are the container's probes; neither is part of `openapi.yaml` (decision D17).

### Run with Docker

The whole stack, app and Postgres, with one command and no setup:

```bash
docker compose up --build
```

Open <http://localhost:8000> and sign in as `you@example.com` or
`organiser@example.com` with the demo password `deuce-demo-password`; the game
list shows the seeded Roland Garros 2026 game. The app waits for Postgres to be
healthy, migrates, seeds (on every start; it is idempotent) and serves. This is
the stack for development, tests and CI only; the deployment builds the
image directly (issue #6). The image itself is described in
[Build and run the image](#build-and-run-the-image).

Every variable has a development-only default, so a `.env` file is optional;
copy `.env.example` to `.env` to change one.

| Variable | Default | Meaning |
|---|---|---|
| `SESSION_SECRET` | `compose-dev-only-not-a-secret` | Signs the session cookie. Local and CI use only, never a deployment. |
| `POSTGRES_USER` | `tennis` | Postgres user. |
| `POSTGRES_PASSWORD` | `tennis` | Postgres password. |
| `POSTGRES_DB` | `tennis` | Database name. |
| `APP_PORT` | `8000` | Host port the app is published on (`APP_PORT=8001 docker compose up`). |

`DATABASE_URL` is assembled from the three `POSTGRES_*` values and can be
overridden whole. `COOKIE_SECURE` is left unset: the stack is plain HTTP on
localhost.

- `docker compose down` stops the stack and **keeps** the data (named volume
  `pgdata`). `docker compose down -v` also deletes it; the next `up` starts
  empty, migrates and re-seeds.
- **The Postgres password is applied only when the volume is first created.**
  Changing `POSTGRES_USER`, `POSTGRES_PASSWORD` or `POSTGRES_DB` against an
  existing volume makes the app exit non-zero within `PGCONNECT_TIMEOUT` with
  the error in `docker compose logs app`; run `docker compose down -v` to change
  it.
- Postgres is not published to the host. To look inside:
  `docker compose exec postgres psql -U tennis tennis`.
- There is no restart policy: a failed migration stops the app instead of
  looping.

### Tests

There are two suites, and they answer different questions.

| | Unit (`make test`) | Integration (`make test-integration`) |
|---|---|---|
| Lives in | `backend/tests/`, `frontend/src/**/*.test.ts(x)` | `tests/integration/` |
| Talks to | the app in-process (`TestClient`), memory and SQLite repositories; Postgres too when `TEST_DATABASE_URL` is set | the built image and a real Postgres, over HTTP |
| Needs | Node and uv; no Docker | Docker, and uv for the backend's pytest and httpx |
| Covers | scoring, validation, repositories, every endpoint's rules, the UI | the key workflows end to end: sign-in, registration, joining, predicting, refusal of locked groups and of non-organisers, organiser results through to score and ranking, recalculation |
| Takes | about a minute | about 15 seconds once the image is cached, longer on a cold build |

#### Unit

```bash
cd frontend && npm run test && npm run lint && npm run typecheck
```

```bash
cd backend && uv run pytest && uv run ruff check .
```

The backend suite runs against the in-memory repositories and against SQLAlchemy
on SQLite. With `TEST_DATABASE_URL` set it also runs against Postgres. To add a Postgres run, point `TEST_DATABASE_URL` at a throwaway database
(`docker exec tennis-pg psql -U postgres -c "create database tennis_test"`):

```bash
cd backend && TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/tennis_test uv run pytest
```

Each Postgres test drops and recreates every table, and the suite refuses a
`TEST_DATABASE_URL` equal to `DATABASE_URL`. Without the variable the Postgres
parameter is skipped. `tests/test_contract_drift.py` fails if
`openapi.yaml` and the backend disagree about any operation.

#### Integration

```bash
make test-integration
```

It removes leftovers, builds and starts the compose stack under its own
project (`IT_PROJECT`, default `tennis-it`) on its own host port (`IT_PORT`,
default `18000`), waits for `GET /ready`, runs `tests/integration/` and
tears the stack down with its volume, also when a test fails or you press
Ctrl-C. On failure the app's logs are printed before teardown. The dev stack
(project `tennis-prediction-game`, port 8000) and its data are never touched,
so the two can run side by side; if `IT_PORT` is taken the run fails at
`docker compose up` with the bind error. Building retags the shared
`tennis-prediction-game` image, which is harmless.

The suite has its own `pytest.ini`, imports nothing from `app`, and uses
only the pytest and httpx already in the backend's dev group. It relies on the
two documented demo accounts (`you@example.com`, `organiser@example.com`,
password `deuce-demo-password`) and on the seed's shape: a game open for
signup, and a running game with an OPEN group holding a match-result question
and a SETTLED group. It finds ids by state, never by name, and asserts on
before/after relationships, never on absolute points.
The suite also checks that the frontend is served: the index page, the assets it
references and deep links that fall back to the app shell.

To run it against a stack that is already up:

```bash
APP_URL=http://localhost:8000 uv run --project backend pytest -c tests/integration/pytest.ini tests/integration
```

`APP_URL` defaults to `http://localhost:${APP_PORT:-8000}`. The readiness wait
is 90 seconds, overridable with `READY_TIMEOUT`. The tests register accounts and
change scores, so a host other than `localhost` or `127.0.0.1` aborts the run
before any request unless `INTEGRATION_ALLOW_REMOTE=1` is set.

#### CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml), a workflow named `CI`,
runs on every push to any branch and on every pull request targeting `main`.
Its three jobs are independent (none `needs:` another), so one red job does not
hide the verdicts of the others, and the deploy (issue #6) will depend on all
three. The names are a stable interface: do not rename them.

| Job | Runs | Local equivalent |
|---|---|---|
| `check` | `npm ci` and `uv sync --locked` (lockfiles only), then `make check` on Node 24, uv 0.12.10 and a `postgres:16` service container. `TEST_DATABASE_URL` points at a throwaway database on that service, so the backend suite runs against memory, SQLite **and** Postgres (its pytest summary reports 0 skipped), and the contract drift test runs here. | `make check` (add `TEST_DATABASE_URL` for the Postgres run) |
| `commit-gate` | `agent-hooks/commit-gate.sh` over the lines the change **adds**: for a pull request, since it left its base branch; for a push, since the previous tip (a new branch or a force-push falls back to the merge-base with `origin/main`). Then `agent-hooks/test-hooks.sh`. A hit prints the file and the pattern name, never the line. | `make hooks`, then commit; `agent-hooks/test-hooks.sh` |
| `integration` | `make docker-build` as its own step (so a broken Dockerfile or a `uv.lock` that disagrees with `pyproject.toml` fails with a clear name), then `make test-integration` on its own compose project. | `make docker-build` and `make test-integration` |

The workflow uses no repository secrets and a read-only token
(`permissions: contents: read`), and every action is pinned to a full commit
SHA. CI runs only the generic commit-gate patterns:
`agent-hooks/private-patterns.txt` is gitignored and absent there, so the
author's own name list still runs only locally, through `make hooks`.

### API documentation

With the backend running, http://localhost:8000/docs serves the generated
OpenAPI UI. The committed contract is [`openapi.yaml`](openapi.yaml) and it is
the source of truth — the drift check exists to keep the two honest.

## Architecture in one paragraph

Thin client, thick backend. All validation, rule enforcement and scoring live
server-side; the frontend duplicates validation for user experience only, and the
backend is always the authority. Every external dependency — tennis data,
authentication, email — sits behind an interface with a mock implementation, so
no vendor outage can break the game. Scores are derived data: they can be deleted
and recomputed at any time from predictions, the outcome grid and question
outcomes.

---

## Context

Built for Module 2 of the [AI Dev Tools Zoomcamp](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp) by Alexey Grigorev and the DataTalks.Club, as an exercise in a controlled AI-assisted workflow: spec first, then frontend, then contract, then backend, then persistence — verifying each step before starting the next. The AI usage log is in [`docs/ai-usage-report.md`](docs/ai-usage-report.md).
