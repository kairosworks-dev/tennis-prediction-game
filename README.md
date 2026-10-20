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

## Try it online

The production deployment is at **https://deuce.kairosworks.dev**.

It runs the demo seed: a game open for signup and a game in progress. Sign in
as `you@example.com` to play, or as `organiser@example.com` to reach the
results screen; the password for both is `deuce-demo-password`. These accounts
are public, so anyone can change outcomes there. Production's data is wiped
after the course.

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
Makefile               make run, make test, make test-unit, make check
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
| `make test` | Every test: Vitest, pytest, then the integration tests (needs Docker) |
| `make test-unit` | Vitest and pytest only (no Docker) |
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
- `EMAIL_PROVIDER` is `console` or `discard`. Unset or empty means `discard`: nothing
  is written anywhere. `console` prints the verification line to stderr (address and
  token), for a machine you control; `make run` and `make run-backend` set it.
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

A second run of the seed script prints "Demo game roland-garros-2026 already present; nothing to do."

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
| `EMAIL_PROVIDER` | unset, which means `discard` | `discard` or `console`. The default never writes an address or a token to the output; set `console` only on a machine you control. Any other value stops start-up. A deployed environment leaves it unset, and the pipeline never sets it. |
| `COOKIE_SECURE` | unset, which means `false` | `true` marks the session cookie `Secure`, for a deployment behind HTTPS; `false` is for plain HTTP and local use only. Any other value (`True`, `1`, `yes`) stops start-up. |
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
the stack for development, tests and CI only; the deployment pulls the image
CI built (see [Deploy](#deploy)). The image itself is described in
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
| `EMAIL_PROVIDER` | `console` | The dev stack prints the verification line (address and token) to the app's output, see `docker compose logs app`. |

The dev stack prints the verification line on purpose (`EMAIL_PROVIDER=console`);
the image does not.

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
request, and the author reviews and merges it himself, with no auto-merge.
CI runs only the generic commit-gate patterns:
`agent-hooks/private-patterns.txt` is gitignored and absent there, so the
author's own name list still runs only locally, through `make hooks`.

### Deploy

Two environments run the image CI built, never a rebuild from the repository
and never `docker-compose.yml`:

| Environment | What updates it | Who triggers it |
|---|---|---|
| dev | The `deploy-dev` job of `CI`, on every push to `main` that passes the gate | Nobody: it is automatic. A dispatch of `CI` from `main` redeploys the tip |
| production | The [`Promote`](.github/workflows/promote.yml) workflow, for one commit that passed CI and ran on dev | The author, by hand, then approves the run in the `production` environment |

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

#### Production

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
