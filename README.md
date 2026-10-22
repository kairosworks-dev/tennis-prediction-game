# Tennis Prediction Game

[![CI](https://github.com/kairosworks-dev/tennis-prediction-game/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/kairosworks-dev/tennis-prediction-game/actions/workflows/ci.yml)

A web application for running a tennis prediction game among a group of friends.

**The problem.** A group that bets on a tournament for fun usually ends up with a
hand-kept spreadsheet, a chat thread full of predictions, and one person adding
up the points by hand after every round. Rules get re-explained each time, late
bets are argued over, and nobody is sure who is winning.

**What this is.** One place where a group predicts a tournament and sees a
leaderboard. One game covers one tournament. Before play begins each participant
predicts how the tournament will go (who reaches the quarter-finals, who wins);
while it runs they submit smaller predictions round by round. The organiser
enters the real results, the app scores everyone, and the leaderboard updates.
There is no money, no odds and no payout: it replaces a spreadsheet and a chat
thread, not a bookmaker.

You can try it now at **https://deuce.kairosworks.dev** (see [Try it online](#try-it-online)),
or run it yourself with one Docker command (see [Quickest way to try it](#quickest-way-to-try-it)).

## Contents

- [How the game works](#how-the-game-works)
- [Status](#status)
- [Architecture](#architecture)
- [Try it online](#try-it-online)
- [Prerequisites](#prerequisites)
- [Quickest way to try it](#quickest-way-to-try-it)
- [Local development without Docker](#local-development-without-docker)
- [The image on its own](#the-image-on-its-own)
- [Tests](#tests)
- [CI](#ci)
- [Deploy](#deploy)
- [Configuration](#configuration)
- [API documentation](#api-documentation)
- [Observability](#observability)
- [Alerting on user impact](#alerting-on-user-impact)
- [On-call responder](#on-call-responder)
- [Repository layout](#repository-layout)
- [How it was built](#how-it-was-built)

The authoritative specification is [`docs/product-and-technical-spec.md`](docs/product-and-technical-spec.md);
where the code stands against it is [`docs/status.md`](docs/status.md).
Instructions for coding agents are in [`AGENTS.md`](AGENTS.md).

---

## How the game works

**Roles.** There are two. A **participant** registers, joins a game, places
predictions and reads the leaderboard. The **organiser** (called *admin* in the
spec) can do all of that and also enters the real results and triggers scoring
(spec [section 3](docs/product-and-technical-spec.md#3-users-and-roles)).

**Two kinds of bet.** *Tournament bets* are placed once per draw before the
tournament starts. *Round bets* are placed while it runs, one bet group per round.
A **bet group** is a set of questions that share one deadline and lock together.
A Grand Slam game has two draws (ATP and WTA), so it asks the tournament questions
twice. The point values below are the **default scoring profile** of spec
[section 5](docs/product-and-technical-spec.md#5-game-rules-and-scoring); the
spec makes every value editable per tournament.

**The six tournament questions** (per draw, [5.1](docs/product-and-technical-spec.md#51-tournament-bets)):

| Question | What you pick | Default points |
|---|---|---|
| Quarter-finalists | One player per draw section, 8 picks | 1 per correct pick |
| Semi-finalists | 4 of your quarter-finalists | 2 per correct pick |
| Finalists | 2 of your semi-finalists | 3 per correct pick |
| Champion | 1 of your finalists | 5 |
| Underperformer | One player seeded in the top 10 | 3 / 2 / 1 for an exit in round 1 / 2 / 3, otherwise 0 |
| Breakout | One unseeded entrant | 2 / 3 / 4 / 5 / 7 for reaching round 4 / the quarter-final / the semi-final / the final / winning |

**The two round questions** ([5.2](docs/product-and-technical-spec.md#52-round-bets)):

| Question | What you pick | Default points |
|---|---|---|
| Featured match | The winner and the set score, for example a 3-1 win | 1 for the correct winner, 1 more for the exact set score |
| Extra question | Whatever the organiser composes (a player, a match result, a number, a choice) | Set per question by the organiser |

The set-score point is awarded only when the winner is also correct.

**A worked example.** Ana's picks for one draw, scored against what actually happened:

| Question | Ana's pick | What happened | Points |
|---|---|---|---|
| Quarter-finalists | 8 players | 6 of them reached the quarter-final | 6 x 1 = 6 |
| Semi-finalists | 4 of those 8 | 3 of them reached the semi-final | 3 x 2 = 6 |
| Finalists | 2 of those 4 | 1 of them reached the final | 1 x 3 = 3 |
| Champion | 1 of those 2 (the finalist who got through) | that player won | 5 |
| Underperformer | a top-10 seed | lost in round 2 | 2 |
| Breakout | an unseeded entrant | reached the quarter-final | 3 |

That is 6 + 6 + 3 + 5 + 2 + 3 = **25 points** from the tournament bets. In the
quarter-final round Ana also answers the featured match: she picks player A to win
3-1. A wins, but 3-2. The winner is right (1 point) and the set score is wrong (no
point), so she scores **1** for the round, **26** in total. A participant who had
picked A to win 3-2 would have scored 2; one who had picked B to win 3-1 would
have scored 0, because the set-score point needs the correct winner. If Ben also
has 26 and Cleo has 20, the leaderboard reads Ana 1st, Ben 1st, Cleo 3rd.

**What follows from the rules.** Each claim is in the spec; the section is linked.

- **A bet group locks at its deadline.** Until then a participant can edit
  freely, and partial answers are saved as drafts. After it, the form is read-only
  and the server rejects submissions ([4.4.2](docs/product-and-technical-spec.md#442-betting)).
- **The backend enforces validation.** The pick chain (8 quarter-finalists, then 4,
  then 2, then 1), seed limits for the underperformer, an unseeded breakout and legal
  set scores are checked in the API; the UI only mirrors them for convenience
  ([5.3](docs/product-and-technical-spec.md#53-validation-rules)).
- **Scores are stored, not computed on read.** Each recalculation writes one score
  entry per participant per question, with the points and a reason
  ([5.4](docs/product-and-technical-spec.md#54-scoring-mechanics)).
- **The organiser triggers recalculation by hand.** Entering results does not
  rescore by itself; the organiser presses *Recalculate scores*, which is safe to
  repeat ([4.5.4](docs/product-and-technical-spec.md#454-results-and-scoring)).
- **Ties share a rank.** Two participants on the same total share a position and
  the next position is skipped; there is no tie-breaker
  ([4.4.4](docs/product-and-technical-spec.md#444-ranking)).

---

## Status

This is the final project of the [AI Dev Tools Zoomcamp](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp).
Per-criterion detail, known defects and open decisions are in [`docs/status.md`](docs/status.md).

**What works**

- Landing page with a live teaser of the next open game.
- Sign-up and sign-in with a session cookie.
- The game list in three states (open for signup, running, finished), and joining an open game.
- Placing tournament bets (with the pick chain validated) and round bets, up to the deadline.
- My predictions and scores, with a reason for each award.
- The leaderboard, with ties sharing a rank.
- For the organiser: entering the outcome grid and question answers, and recalculating scores.
- The same image runs on Postgres in a dev and a production environment, with CI
  and a promote-by-hand workflow ([CI](#ci), [Deploy](#deploy)).
- Observability ([Observability](#observability)), an alert on user impact
  ([Alerting on user impact](#alerting-on-user-impact)) and an on-call responder
  ([On-call responder](#on-call-responder)).

**Not built yet**

- Deferred by decision D14 ([spec section 13](docs/product-and-technical-spec.md#13-post-mvp-backlog)):
  admin screens other than the outcome grid and recalculation (tournaments, draws and
  questions are seeded by script), email verification, password reset, profile
  editing, account deletion, the draw view, the post-lock comparison view, and the
  landing-page gallery and testimonials.
- CSRF protection and rate limiting on the auth endpoints.
- Frontend types generated from `openapi.yaml`.
- A Playwright end-to-end test.

---

## Architecture

```mermaid
flowchart TD
  subgraph runtime["Running system"]
    browser["Browser"]
    subgraph container["Container image"]
      fe["Frontend: React, built by Vite, served by the backend at /"]
      subgraph be["Backend: FastAPI under /api"]
        api["api: routers, schemas, auth"]
        services["services: use cases"]
        domain["domain: entities, scoring, validation"]
        repos["repositories: memory and SQLAlchemy"]
        providers["providers: tennis data, email"]
        api --> services
        services --> domain
        services --> repos
        services --> providers
      end
    end
    db[("Database: SQLite locally and in unit tests, Postgres in compose, CI and deployed")]
    browser -->|"loads the app"| fe
    browser -->|"HTTP /api, session cookie"| api
    repos --> db
  end
  contract["openapi.yaml: the contract"]
  contract -.->|"frontend service layer"| fe
  contract -.->|"checked by the drift test"| api
  subgraph cicd["CI/CD: GitHub Actions"]
    check["check"]
    gate["commit-gate"]
    integration["integration"]
    image["image: built once, pushed to GHCR"]
    devdeploy["deploy-dev: automatic on every push to main"]
    promote["promote: by hand, with approval"]
    check --> image
    gate --> image
    integration --> image
    image --> devdeploy
    image --> promote
  end
  devdeploy --> devenv["dev environment"]
  promote --> prodenv["production environment"]
```

**Frontend.** React 18 with TypeScript (strict), Vite, React Router, TanStack Query,
React Hook Form with Zod and Tailwind CSS. Every call to the backend goes through
one service layer with two interchangeable implementations, a mock on fixtures and
an HTTP client, chosen by `VITE_API_CLIENT`. Vite builds it into static files that
the backend serves in the image. Tested with Vitest and React Testing Library.

**Backend.** FastAPI with Pydantic v2, SQLAlchemy 2.0, Alembic, Argon2 password hashing
and session cookies. It is layered with dependencies pointing inward: `api` calls
`services`, which orchestrate the `domain` (entities, the scoring engine and the
validation rules, with no framework imports), the `repositories` and the `providers`.
Tested with pytest and the httpx test client.

**Database.** The repository layer is one SQLAlchemy implementation that serves both
dialects, plus an in-memory one. SQLite is used locally and in the unit tests; Postgres
is used in the compose stack, in CI and in the deployed environments. On SQLite the
app creates missing tables itself; on Postgres Alembic owns the schema and the app
refuses to start against an unmigrated database.

**Containers.** One image holds the whole app: the backend serves the API under `/api`
and the built frontend at `/`. The container migrates, seeds the demo game and starts
uvicorn. `docker-compose.yml` runs that image next to a Postgres, for development,
tests and CI.

**CI/CD.** GitHub Actions runs `check` (lint, typecheck, unit tests), `commit-gate`
and `integration` on every push. On `main`, once all three pass, `image` builds the
image once and pushes it to GHCR; `deploy-dev` then deploys it to dev automatically.
Production changes only through the `Promote` workflow, started by hand, approved in
the `production` environment, and deploying the same image digest dev ran.

**How it fits.** The browser loads the built frontend and talks to the backend over
HTTP under `/api` with a session cookie. `openapi.yaml` is the agreement between the
two sides, and a test fails if it and the FastAPI schema disagree. The same image is
what CI tests, what compose runs and what both environments deploy.

**Thin client, thick backend.** All validation, rule enforcement and scoring live
server-side; the frontend duplicates validation for user experience only, and the
backend is always the authority. Every external dependency (tennis data,
authentication, email) sits behind an interface with a mock implementation, so no
vendor outage can break the game. Scores are derived data: they can be deleted and
recomputed at any time from predictions, the outcome grid and question outcomes.
These follow the hard rules in [`AGENTS.md`](AGENTS.md#hard-rules): no HTTP outside the
frontend service layer (rule 1), no business logic in the frontend (2), the contract
(3), a framework-free domain (4), a pure scoring function (5), dependencies behind
interfaces (6), rebuildable derived data (7) and the database as a URL (8).

---

## Try it online

The production deployment is at **https://deuce.kairosworks.dev**.

It runs the demo seed: a game open for signup and a game in progress. Sign in
as `you@example.com` to play, or as `organiser@example.com` to reach the
results screen; the password for both is `deuce-demo-password`. These accounts
are public, so anyone can change outcomes there. Production's data is wiped
after the course.

**Nothing is sent.** The app has no email provider that sends mail. It has two
mock implementations, `console` (prints to the app's output) and `discard` (writes
nothing, and the default when `EMAIL_PROVIDER` is unset), so no email leaves the
app. The compose dev stack and `make run` set `console`.

Anyone can register on the public site. Email verification is not built, so a
registration changes nothing visible beyond a new account.

---

## Prerequisites

| You want to | You need |
|---|---|
| Run the app: [Quickest way to try it](#quickest-way-to-try-it), [The image on its own](#the-image-on-its-own) | Docker with the compose plugin. Nothing else: no Node, no uv. |
| Develop without Docker: [Local development](#local-development-without-docker), `make run`, `make test-unit`, `make check` | **Node 20+** and **[uv](https://docs.astral.sh/uv/)** |
| Run every test: `make test`, `make test-integration` | Docker, and uv (the integration suite uses the backend's pytest and httpx) |

---

## Quickest way to try it

The whole stack, app and Postgres, with one command and no setup:

```bash
docker compose up --build
```

Open <http://localhost:8000> and sign in as `you@example.com` or
`organiser@example.com` with the demo password `deuce-demo-password`; the game
list shows the seeded Roland Garros 2026 game. The app waits for Postgres to be
healthy, migrates, seeds (on every start; it is idempotent) and serves. This is
the stack for development, tests and CI only; the deployments pull the image
CI built (see [Deploy](#deploy)). The image itself is described in
[The image on its own](#the-image-on-its-own).

**Port 8000 taken?** Publish the app on another host port:

```bash
APP_PORT=8001 docker compose up --build   # then open http://localhost:8001
```

Every variable has a development-only default, so a `.env` file is optional;
copy `.env.example` to `.env` to change one (see [Configuration](#configuration)).
The dev stack sets `EMAIL_PROVIDER=console`, so it prints the verification line
(address and token) to the app's output: `docker compose logs app`. The image
itself does not.

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

---

## Local development without Docker

Requires **Node 20+** and **[uv](https://docs.astral.sh/uv/)**.

```bash
make install
make run
```

`make run` migrates the database, seeds a demo game, starts the backend on
**:8000** and the frontend on **:5173** pointed at it, and Ctrl-C stops both.
Open http://localhost:5173. It uses SQLite.

Sign in as `you@example.com` to play, or `organiser@example.com` to reach the
results screen. Password for both: `deuce-demo-password`.

`make` on its own lists every target. The ones worth knowing:

| | |
|---|---|
| `make install` | Install both packages (`npm install`, `uv sync`) |
| `make run` | Backend and frontend together, on SQLite |
| `make run-mock` | Frontend alone on in-memory fixtures — no backend, no database |
| `make run-backend` | Backend alone, on SQLite (`db` first; auto-reload) |
| `make run-frontend` | Frontend alone, against a backend that is already running |
| `make db` | Migrate and seed the database (a no-op if already seeded) |
| `make reset-db` | Throw the database away and rebuild it from empty |
| `make test` | Every test: Vitest, pytest, then the integration tests (needs Docker) |
| `make test-unit` | Vitest and pytest only (no Docker) |
| `make test-frontend`, `make test-backend` | One half of the unit tests |
| `make test-integration` | Build the compose stack on a separate project, test it over HTTP, tear it down |
| `make lint`, `make typecheck` | ESLint and ruff; `tsc --noEmit` |
| `make check` | Lint, typecheck, every unit test and the commit-gate tests (no Docker) |
| `make docker-build` | Build the container image |
| `make hooks` | Enable the commit gate (a git pre-commit hook) for this clone; contributors only |
| `make clean` | Remove build output and the local database |

**Port 8000 taken?** `make run` needs it: the frontend dev server proxies `/api` to
`http://localhost:8000`, a fixed target in `frontend/vite.config.ts`, so the frontend
only reaches a backend on 8000, and setting `BACKEND_PORT` alone does not move the
pair. Use the Docker path above with `APP_PORT`, or `make run-mock` (no backend at all).
`make run-backend BACKEND_PORT=<port>` starts the backend alone on another port, for
`curl` or <http://localhost:8001/docs>.

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

`DATABASE_URL` selects the database. Default: `sqlite:///./tennis.db`.
Postgres example: `postgresql+psycopg://postgres:postgres@localhost:5433/tennis`.
Bare `postgresql://` and `postgres://` URLs are accepted and rewritten to
`postgresql+psycopg://` (the installed driver) in one place, `create_db_engine`;
Alembic uses the same rewrite. `REPOSITORY_BACKEND` is `memory` (default) or
`sqlalchemy`; `sqlite` is kept as an alias for `sqlalchemy`. The dialect comes from
`DATABASE_URL` alone. Any other value stops start-up with an error.

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

A second run of the seed script prints "Demo game roland-garros-2026 already present; nothing to do."

---

## The image on its own

One image holds the whole app: the backend serves the API under `/api` and the
built frontend at `/`. It needs Docker only.

```bash
make docker-build        # docker build -t tennis-prediction-game .
docker run --rm -p 8000:8000 -e SESSION_SECRET=change-me tennis-prediction-game
```

Open <http://localhost:8000> and sign in as `you@example.com` with the demo
password (use `-p 8001:8000` if 8000 is taken). At start the container migrates its
database, runs the idempotent demo seed (on every start, for now) and then starts
uvicorn; if the migration fails it exits non-zero. It runs as a non-root user (UID 10001).

By default the data is a SQLite file at `/data/tennis.db`. **Without a volume it
is lost when the container is removed.** To keep it, mount a volume on `/data`
(`-v tennis-data:/data`; a bind mount must be writable by UID 10001).

`GET /health` (process is up, no database) and `GET /ready` (database answers)
are the container's probes; neither is part of `openapi.yaml` (decision D17).
The variables the image reads are in [Configuration](#configuration).

---

## Tests

**One command.** `make test` runs every test the project has, in this order:
the Vitest suite, the backend pytest suite, then the integration tests over
HTTP against the compose stack, and stops at the first step that fails. It
needs Docker with the compose plugin; a preflight checks this before anything
runs and, if Docker is missing or stopped, prints a message and exits non-zero
(`make test-unit` is the alternative that needs no Docker). Allow about a
minute for the unit suites, plus the integration run, which is longer on a cold
image build. The Postgres parameter of the backend suite is skipped locally
unless `TEST_DATABASE_URL` is set (CI's `check` job sets it); the integration
phase runs against a real Postgres either way.

There are two suites, and they answer different questions.

| | Unit (`make test-unit`) | Integration (`make test-integration`) |
|---|---|---|
| Lives in | `backend/tests/`, `frontend/src/**/*.test.ts(x)` | `tests/integration/` |
| Talks to | the app in-process (`TestClient`), memory and SQLite repositories; Postgres too when `TEST_DATABASE_URL` is set | the built image and a real Postgres, over HTTP |
| Needs | Node and uv; no Docker | Docker, and uv for the backend's pytest and httpx |
| Covers | scoring, validation, repositories, every endpoint's rules, the UI | the key workflows end to end: sign-in, registration, joining, predicting, refusal of locked groups and of non-organisers, organiser results through to score and ranking, recalculation |
| Takes | about a minute | about 15 seconds once the image is cached, longer on a cold build |

### Unit

```bash
cd frontend && npm run test && npm run lint && npm run typecheck
```

```bash
cd backend && uv run pytest && uv run ruff check .
```

The backend suite runs against the in-memory repositories and against SQLAlchemy
on SQLite. With `TEST_DATABASE_URL` set it also runs against Postgres. To add a
Postgres run, start the throwaway Postgres from [Database](#database) and create a
throwaway database in it
(`docker exec tennis-pg psql -U postgres -c "create database tennis_test"`):

```bash
cd backend && TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/tennis_test uv run pytest
```

Each Postgres test drops and recreates every table, and the suite refuses a
`TEST_DATABASE_URL` equal to `DATABASE_URL`. Without the variable the Postgres
parameter is skipped. `tests/test_contract_drift.py` fails if
`openapi.yaml` and the backend disagree about any operation.

### Integration

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

---

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml), a workflow named `CI`,
runs on every push to any branch, on every pull request targeting `main` and
on a manual dispatch (`workflow_dispatch`, no inputs). Its first three jobs are
independent (none `needs:` another), so one red job does not hide the verdicts
of the others, and the `image` job depends on all three. The names are a stable
interface: do not rename them.

| Job | Runs | Local equivalent |
|---|---|---|
| `check` | `npm ci` and `uv sync --locked` (lockfiles only), then `make check` on Node 24, uv 0.12.10 and a `postgres:16` service container. `TEST_DATABASE_URL` points at a throwaway database on that service, so the backend suite runs against memory, SQLite **and** Postgres (its pytest summary reports 0 skipped), and the contract drift test runs here. | `make check` (add `TEST_DATABASE_URL` for the Postgres run) |
| `commit-gate` | `agent-hooks/commit-gate.sh` over the lines the change **adds**: for a pull request, since it left its base branch; for a push, since the previous tip (a new branch, a force-push or a dispatch falls back to the merge-base with `origin/main`, which is empty on `main`). Then `agent-hooks/test-hooks.sh`. A hit prints the file and the pattern name, never the line. | `make hooks`, then commit; `agent-hooks/test-hooks.sh` |
| `integration` | `make docker-build` as its own step (so a broken Dockerfile or a `uv.lock` that disagrees with `pyproject.toml` fails with a clear name), then `make test-integration` on its own compose project. | `make docker-build` and `make test-integration` |
| `image` | After the three jobs above are green, on `main` only (a push, or a dispatch from `main`): builds the `Dockerfile` once and pushes it to GHCR as `sha-<commit>`, or reuses that tag if it already exists. Its output is the image digest. | `make docker-build` (no push) |
| `deploy-dev` | On `main` only (a push, or a dispatch from `main`), after `image`: asks the dev server to run that digest, then waits for `/ready`. See [Deploy](#deploy). | none |

A push to another branch, a pull request and a dispatch run from a branch start
the first three jobs and nothing else. The workflow uses no repository secrets
and a read-only token by default (`permissions: contents: read`); only `image`
adds `packages: write`, and the five secrets of the `dev` environment are read
by `deploy-dev` alone. Every third-party action is pinned to a full commit SHA.
Dependabot proposes updates to those pins weekly, on branches named
`dependabot/…` (outside the `issue-<n>/…` naming); each proposal changes the
SHA and the `# vX.Y.Z` comment together, CI runs on it like on any pull
request, and the author reviews and merges it, with no auto-merge.
CI runs only the generic commit-gate patterns:
`agent-hooks/private-patterns.txt` is gitignored and absent there, so the
author's own name list still runs only locally, through `make hooks`.

---

## Deploy

**In short:** dev is deployed automatically on every push to `main`; production is
promoted by hand, with an approval, and runs the same image digest that CI built
and dev ran. Both run the image CI built, never a rebuild from the repository and
never `docker-compose.yml`.

| Environment | What updates it | Who triggers it |
|---|---|---|
| dev | The `deploy-dev` job of `CI`, on every push to `main` that passes the gate | Nobody: it is automatic. A dispatch of `CI` from `main` redeploys the tip |
| production | The [`Promote`](.github/workflows/promote.yml) workflow, for one commit that passed CI and ran on dev | The author, by hand, then approves the run in the `production` environment |

To promote a commit to production, from a checkout with `gh`:

```bash
gh workflow run promote.yml -f sha=<sha>
```

`<sha>` is the full 40-character lower-case commit sha of a commit that passed `CI`
and was deployed to dev. [`ci.yml`](.github/workflows/ci.yml) has the jobs `check`,
`commit-gate`, `integration`, `image` and `deploy-dev`;
[`promote.yml`](.github/workflows/promote.yml) has `verify` (read-only checks that
the commit passed CI, ran on dev and has an image) and `promote` (waits for the
approval, then deploys). The details of both environments, the request sent to
the server and the limits are below.

<details>
<summary>Deploy details: dev, production, the server interface and limits</summary>

`deploy-dev` and the promote job share one deploy action,
[`.github/actions/deploy`](.github/actions/deploy/action.yml), so the request,
the host-key pinning, the fixed sentences and the `/ready` poll are the same for
both. The interface to the server is described once, under *The interface to the
server* below; the scripts on the server are not in this repository.

**Dev** is the first deployed environment.

- **What updates dev.** A push to `main` runs the gate, `image` and
  `deploy-dev`, with no manual step, so dev runs the newest commit that passed
  the gate. A dispatch of the `CI` workflow from `main` (Actions, *Run
  workflow*, branch `main`) does the same for the tip of `main`: it is a manual
  redeploy. A run on any other branch never builds, pushes or deploys.
- **The image.** `ghcr.io/<owner>/<repo>:sha-<full 40-character commit sha>`,
  lower case, one tag per commit, never overwritten and with no `latest` or
  other moving tag. It carries the `org.opencontainers.image.source` and
  `.revision` labels. If the tag already exists (a re-run, or a dispatch on the
  same commit) `image` builds and pushes nothing and reuses its digest. The
  environment is told to run the **digest**,
  `ghcr.io/<owner>/<repo>@sha256:<64 hex>`, which names the exact bytes.
- **Secrets.** Five environment secrets of the GitHub environment `dev`, read
  only by `deploy-dev`: `DEPLOY_SSH_KEY`, `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`,
  `DEPLOY_SSH_KNOWN_HOSTS` and `APP_URL`. If one is empty, or `APP_URL` does not start with
  `https://`, the job fails first, naming it. The workflow never holds a database URL, a session secret or a
  token of the hosting platform; those live only on the server.
- **Variables of the dev application.**

  | Variable | Dev application |
  |---|---|
  | `DATABASE_URL` | **set**, the managed Postgres' internal URL. Unset, the image falls back to SQLite in `/data`, which has no volume: the app starts, `/ready` is 200 and the data is lost at every redeploy |
  | `SESSION_SECRET` | **set**, a long random value made for this environment. The container refuses to start without it |
  | `COOKIE_SECURE` | **set to `true`**: the URL is HTTPS |
  | `EMAIL_PROVIDER` | **must not be set.** Unset is `discard`; `console` would print registrants' addresses and tokens to the logs of a public environment |
  | `REPOSITORY_BACKEND`, `FRONTEND_DIR` | do not set; the image sets them |
  | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `APP_PORT` | do not set; compose-only variables |

  The platform's environment store is filled one variable at a time, never by
  pasting `.env.example` or `docker-compose.yml`.

- **The interface to the server.** GitHub reaches the server over SSH, as a
  deploy user whose key is limited to one forced command. That script is the
  author's, is not in this repository and is the only thing that calls the
  hosting platform. The pipeline depends on this interface and nothing else.
  - *Request.* Exactly one line, as the SSH command, and no arguments after it:
    `deploy ghcr.io/<owner>/<repo>@sha256:<64 lowercase hex>`, matching
    `^deploy ghcr\.io/[a-z0-9._-]+/[a-z0-9._-]+@sha256:[0-9a-f]{64}$`. The
    workflow checks its own string against that pattern and fails the job
    without connecting if it does not match. The server rejects anything that
    does not match in full, and accepts only its one configured image name.
  - *Answer.* One line on stdout, `ok` or `error: <word>`, and an exit status:
    `0` for `ok`, `10` a rejected request, `11` a failed deployment, `12` the
    script's own timeout (shorter than the workflow's 10 minutes for the call).
    It never uses `255`, which `ssh` itself returns when the connection or the
    host-key check fails.
  - *What the workflow does with it.* It prints one fixed sentence per status:
    `255` the connection or host-key check failed; `10` the server rejected the
    request; `11` the deployment failed on the server; `12` the server gave up
    waiting for the deployment; anything else (a call that outlives the
    workflow's timeout ends with `124`) is "unexpected exit code N". It shows the
    server's answer line only if it matches `^(ok|error: [a-z-]+)$`, and
    discards `ssh` error output, which can contain the host name. The host key
    is checked against the pinned `DEPLOY_SSH_KNOWN_HOSTS`; there is no scan and
    no trust on first use. After exit `0` it polls `GET /ready` on `APP_URL`
    every 10 seconds, up to 24 times, and fails the job unless it gets 200. The
    job summary gives the commit, the digest and the `/ready` status; it never
    prints a URL, host, user or key.
- **Dev may be reset at will.** It runs demo data only, and the demo organiser
  account is public (see the demo accounts above), so anyone can change outcomes
  there. Recovery is resetting the dev database.
- **Re-running an old run redeploys that commit.** Re-running `deploy-dev` from
  an older run deploys that run's image. This is intended and keeps a rollback
  possible. Migrations run on container start and are not reversed, so an older
  image runs against the newer schema; keep migrations backward compatible.
- **Limits.** The image deployed is built from the same commit after the gate is
  green, but it is not byte-for-byte the image `integration` tested on its own
  runner. Pushes to `main` that land while a run is still going replace the run
  that is merely waiting, so a superseded commit is never built or deployed; the
  newest one is.

### Production

Production is deployed by hand, only through the `Promote` workflow, and only
with a commit that already passed CI and ran on dev.

- **Promote.** From a checkout of the repository, with `gh`:

  ```bash
  gh workflow run promote.yml -f sha=<sha>
  ```

  or *Run workflow* on `Promote` in Actions, branch `main`. `<sha>` is the full
  40-character lower-case commit sha; anything else is refused before any
  request. A dispatch from another branch starts nothing.
- **Which sha dev is running.** The latest `dev` deployment, for example
  `gh api "repos/<owner>/<repo>/deployments?environment=dev&per_page=1" --jq '.[0].sha'`
  (the *Deployments* list of the repository shows the same). Any commit that dev
  deployed successfully can be promoted, not only the latest one.
- **Which sha production is running.** Read it from the summary of the
  `promote` job, not from the *Deployments* list: GitHub records every
  production deployment under the commit the promote run ran on (the tip of
  `main`), not under the promoted commit.
- **What the workflow does.** Job `verify`, which holds none of production's
  secrets, checks that a `CI` run on `main` for that commit concluded success,
  that dev has a deployment of it with a `success` status in its history, and
  that the tag `sha-<sha>` exists in GHCR (read anonymously, so it relies on the
  package being public). It refuses with a fixed sentence naming the check, and
  an error from GitHub or the registry is reported with its status code, never as
  "not found". Only if all three hold does job `promote` start; it pauses for the
  required reviewer of the `production` environment, then sends the same request
  as `deploy-dev` for the digest of that tag and polls `/ready`. Its summary
  gives the promoted commit, the digest and the `/ready` status: for the same
  commit, the same digest as dev's summary.
- **Secrets.** The `production` environment has the same five secret names as
  `dev` and its own values, read only by the `promote` job. It accepts
  deployments from `main` only and requires an approval for each run.
- **Older commits.** Promoting a commit that is no longer dev's current one
  works; this keeps a rollback possible. A commit that was superseded before it
  was ever built and deployed has no dev deployment and is refused. Migrations
  are not reversed by an older image, so keep them backward compatible.
- **Production's application** follows the variable table above, with its own
  values (its own database, its own `SESSION_SECRET`).
- **Limit: tag overwrite.** A GHCR tag can be overwritten in principle. The
  `image` job never overwrites one, so it takes a deliberate action by the
  maintainer or a stolen credential. The named, unbuilt upgrade is to have
  `image` upload its digest as a run artifact and `verify` compare it with the
  tag.
- **Demo data.** Production runs the same image and the same demo seed as dev,
  is never reset by the pipeline, and its data is wiped after the course.

</details>

---

## Configuration

Configuration is environment variables. Every default below is for development; none
of these values is a secret.

| Variable | Default | Where | Meaning |
|---|---|---|---|
| `DATABASE_URL` | `sqlite:///./tennis.db`; the image sets `sqlite:////data/tennis.db`; compose builds a Postgres URL from the `POSTGRES_*` values | backend, image, compose | Any SQLAlchemy URL; a bare `postgresql://` URL works. An unreachable database makes the container exit non-zero within `PGCONNECT_TIMEOUT` (10 s by default), with the error in `docker logs`. |
| `REPOSITORY_BACKEND` | `memory` in the code; the image sets `sqlalchemy`; `make run` sets `sqlite` (an alias) | backend, image | `memory` or `sqlalchemy`. Any other value stops start-up. |
| `SESSION_SECRET` | none in the image, which **refuses to start** without it; compose uses the placeholder `compose-dev-only-not-a-secret`; a bare backend (tests, `make run`) uses a development-only value | image, compose, backend | Signs the session cookie. The placeholders are for local and CI use only, never a deployment. |
| `COOKIE_SECURE` | unset, which means `false` | backend, image | `true` marks the session cookie `Secure`, for a deployment behind HTTPS; `false` is for plain HTTP and local use only. Any other value (`True`, `1`, `yes`) stops start-up. Compose leaves it unset. |
| `EMAIL_PROVIDER` | unset, which means `discard`; compose and `make run` set `console` | backend, image, compose | `discard` writes nothing; `console` prints the verification line (address and token) to stderr, for a machine you control. Neither sends mail. Any other value stops start-up. Neither the image nor the pipeline sets it. |
| `FRONTEND_DIR` | `/app/static` (set by the image) | image | Where the built frontend lives; served only if it exists. |
| `APP_PORT` | `8000` | compose | Host port the app is published on (`APP_PORT=8001 docker compose up`). |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `tennis` each | compose | Postgres user, password and database name. Applied only when the `pgdata` volume is first created. |
| `VITE_API_CLIENT` | `mock` | frontend | `mock` (fixtures, no backend) or `http` (the real API). `make run` and the image build use `http`. Set it in `frontend/.env` to make a choice stick. |
| `PGCONNECT_TIMEOUT` | `10` (set by the image entrypoint) | image | Seconds to wait for an unreachable Postgres before the container exits. |

`.env.example` at the root holds the compose values (`SESSION_SECRET`,
`POSTGRES_*`, `APP_PORT`, `EMAIL_PROVIDER`) and is optional. The variables of the
test targets (`TEST_DATABASE_URL`, `IT_PROJECT`, `IT_PORT`, `APP_URL`) are in [Tests](#tests).

---

## API documentation

With the backend running, http://localhost:8000/docs serves the generated
OpenAPI UI. The committed contract is [`openapi.yaml`](openapi.yaml) and it is
the source of truth — the drift check exists to keep the two honest.

---

## Observability

An optional local telemetry stack for looking inside the running app. It is not
needed to run, test or deploy the app. What it is and how to start it:
[`docs/observability.md`](docs/observability.md).

## Alerting on user impact

An alert that fires when users are affected. What it watches and how to read it:
[`docs/alerting.md`](docs/alerting.md).

## On-call responder

The on-call responder handles that alert. How it works and how it is run:
[`incident-response/README.md`](incident-response/README.md).

---

## Repository layout

```
/backend               FastAPI application, domain layer, repositories, unit tests
/frontend              React application and its service layer
/tests/integration     integration tests, run over HTTP against the compose stack
/docs
  product-and-technical-spec.md   requirements, decisions, scope, backlog
  status.md                       where the code stands against that spec
  process.md                      how an issue moves from open to closed
  team/                           the role definitions: pm, software-engineer, qa-engineer
  task-template.md                the template for a new issue
  ai-usage-report.md              how this was built, and what it taught
  permissions.md, demo.md         permissions note; the extension-pack demo
  design/                         Claude Design artboards (source for the canvas)
/agent-capabilities    reusable workflows and subagent definitions (tool-agnostic)
/agent-hooks           guardrail scripts, including the commit gate
/ops                   sanitised operational evidence
/.claude               links into agent-capabilities/ and the hook wiring
/.github
  workflows/ci.yml        CI: check, commit-gate, integration, image, deploy-dev
  workflows/promote.yml   Promote: verify, promote (production, by hand)
  actions/deploy          the deploy action both workflows share
  dependabot.yml          weekly updates to the pinned actions
AGENTS.md              instructions for coding agents — read this first
CLAUDE.md              points at AGENTS.md
Makefile               make run, make test, make test-unit, make check, and more
Dockerfile             one image: backend serving the built frontend
docker-entrypoint.sh   the image's start-up: migrate, seed, serve
docker-compose.yml     app + Postgres for dev, test and CI
.env.example           optional compose settings, placeholders only
openapi.yaml           the agreement between frontend and backend
product-spec.md        pointer to docs/product-and-technical-spec.md
README.md              this file
```

---

## How it was built

This is the final project of the [AI Dev Tools Zoomcamp](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp)
by Alexey Grigorev and the DataTalks.Club. It was built spec first, then the
frontend on a mocked service layer, then the contract, the backend and persistence,
and then shipped and operated: containers, tests under one command, CI/CD and
deployment. An agent team with defined roles (product manager, engineer, QA,
API reviewer) did the work an issue at a time: see [`AGENTS.md`](AGENTS.md),
[`docs/process.md`](docs/process.md) and the usage log
[`docs/ai-usage-report.md`](docs/ai-usage-report.md).
