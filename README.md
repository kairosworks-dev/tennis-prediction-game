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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs against `MockApiClient` by default — deterministic in-memory fixtures,
no backend required. Switch implementations with the `VITE_API_CLIENT` environment
variable once the backend exists.

```bash
npm run test        # Vitest
npm run lint        # ESLint
npm run typecheck   # tsc --noEmit
```

### Backend

Not yet scaffolded. Arrives in step 3.

---

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
