# Tennis Prediction Game

A web application for running tennis prediction competitions among a group of friends.
One competition covers one tournament. Participants predict the tournament outcome
before play begins and submit smaller predictions round by round. Points accumulate
into a leaderboard.

No money, no odds, no payouts — this replaces a hand-maintained spreadsheet and a
chat thread full of bets, not a bookmaker.

The authoritative specification is [`docs/product-and-technical-spec.md`](docs/product-and-technical-spec.md).
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

---

## Stack

**Frontend** — React 18, TypeScript (strict), Vite, React Router, TanStack Query,
React Hook Form with Zod, Tailwind CSS. Tested with Vitest, React Testing Library
and Playwright.

**Backend** — FastAPI, Pydantic v2, SQLAlchemy 2.0 with SQLite, Alembic, Argon2
password hashing, session cookies. Tested with pytest and the httpx test client.

`openapi.yaml` at the repository root is the single agreement between the two.

---

## Repository layout

```
/backend            FastAPI application and its tests   (from step 3)
/docs               specification and supporting documentation
/frontend           React application                   (step 1)
AGENTS.md           instructions for coding agents
openapi.yaml        the API agreement                   (from step 2)
README.md           this file
```

---

## Running it locally

Requires **Node 20+** and **[uv](https://docs.astral.sh/uv/)**. Two terminals.

### The quick way — frontend only

The frontend runs against in-memory fixtures with no backend at all:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Sign in as `you@example.com` with any password, or
as `organiser@example.com` to reach the results screen. The fixtures cover a
two-draw Grand Slam at the quarter-finals, a game open for signup, a finished
game and a private game.

### The whole thing — frontend, backend and SQLite

**Terminal one** — create the database, seed a demo game, serve the API:

```bash
cd backend && uv sync && uv run alembic upgrade head && uv run python scripts_seed.py && REPOSITORY_BACKEND=sqlite uv run uvicorn app.main:app --port 8000
```

**Terminal two** — point the frontend at it and start:

```bash
cd frontend && npm install && echo "VITE_API_CLIENT=http" > .env && npm run dev
```

Open http://localhost:5173 and sign in with `you@example.com` /
`deuce-demo-password`, or `organiser@example.com` for the results screen. Vite
proxies `/api` to port 8000, so the session cookie stays same-origin.

Set `VITE_API_CLIENT=mock` in `frontend/.env` to go back to fixtures. That
environment variable is the only difference between the two modes — no code
changes, which is what the service layer exists for.

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
