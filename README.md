# Tennis Prediction Game

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

Three definitions of done are still unmet and two defects are known.
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
| `make check` | Lint, typecheck and every test |

### Running it without make

```bash
# terminal one
cd backend && uv sync && uv run alembic upgrade head && uv run python scripts_seed.py
REPOSITORY_BACKEND=sqlite uv run uvicorn app.main:app --port 8000

# terminal two
cd frontend && npm install && VITE_API_CLIENT=http npm run dev
```

Vite proxies `/api` to port 8000, so the session cookie stays same-origin.

`VITE_API_CLIENT` is the only difference between the two modes — `http` for the
real backend, `mock` for fixtures. No code changes, which is what the service
layer exists for. Set it in `frontend/.env` to make a choice stick.

### Tests

```bash
cd frontend && npm run test && npm run lint && npm run typecheck
```

```bash
cd backend && uv run pytest && uv run ruff check .
```

The backend suite runs twice: once against the in-memory repositories and once
against SQLAlchemy on SQLite. `tests/test_contract_drift.py` fails if
`openapi.yaml` and the backend disagree about any operation.

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
