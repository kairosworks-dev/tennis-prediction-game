# AGENTS.md

Instructions for coding agents working in this repository. Read this before making any change.

## What this is

A web application for running tennis prediction competitions. One competition covers one tournament. Participants predict the tournament outcome before play begins and submit smaller predictions round by round. Points accumulate into a leaderboard.

The authoritative specification is [`docs/product-and-technical-spec.md`](docs/product-and-technical-spec.md). Read it before your first substantive change. Its decision log (Section 11) is binding.

## Repository layout

```
/backend            FastAPI application and its tests
/docs               supporting documentation
/frontend           React application
AGENTS.md           this file
openapi.yaml        the API agreement between frontend and backend
README.md           setup and run instructions
```

## Current step

The project is built in four sequential steps. **Do not work ahead.** Code that belongs to a later step does not get written early, even when it seems obvious.

| Step | Scope | State |
|---|---|---|
| 1 | React frontend against a mocked service layer | **Done** |
| 2 | `openapi.yaml` derived from the frontend service layer | **Done** |
| 3 | FastAPI backend with in-memory repositories | **Active** |
| 4 | SQLAlchemy and SQLite persistence | Not started |

Each step has a definition of done in Section 9 of the spec. A step is finished when every item is met, not when the code appears to work.

**The first pass builds a narrowed screen surface** (decision D14, spec 13.1).
Deferred: admin screens other than the outcome grid and recalculation; email
verification, password reset, profile editing and account deletion; the draw
view; the post-lock comparison view; the landing-page gallery and testimonials.
Deferred means *not now*, not *never* — Section 4 still describes the intended
product, so do not delete its requirements. The architecture is **not** narrowed:
every hard rule below applies in full.

**Update the table above when a step completes.**

---

## Hard rules

These are the constraints that are cheap to violate and expensive to unwind. Breaking one is a defect regardless of whether tests pass.

### 1. No HTTP calls outside the frontend service layer

Every backend interaction goes through `frontend/src/services/`. No component, hook, page or utility imports `fetch`, `axios`, or any HTTP client directly. There is an ESLint rule enforcing this; do not disable it, and do not add exceptions.

### 2. No business logic in the frontend

Validation, scoring and rule enforcement live in the backend. The frontend duplicates validation for user experience only. When the two disagree, the backend is right. Never implement a rule in the frontend that does not also exist server-side.

### 3. `openapi.yaml` is the contract

From step 2 onward: changing an endpoint means changing the spec first, then both sides. Never let the FastAPI-generated schema and the committed `openapi.yaml` drift. CI fails on drift; fix the cause, not the check.

### 4. The domain layer imports no framework

`backend/domain/` contains entities, the scoring engine and validation rules. It imports no FastAPI, no SQLAlchemy, no HTTP client, no settings object. If you need one of those in `domain/`, the design is wrong.

### 5. Scoring is a pure function

The scoring engine maps `(predictions, outcome grid, question outcomes, scoring profile)` to score entries. No I/O, no clock reads, no randomness, no database access. It must be testable with plain data structures.

### 6. External dependencies sit behind interfaces

Tennis data, authentication and email are each an interface with a mock implementation. Call sites depend on the interface, never on a concrete vendor. See spec Sections 7.2 and 7.4.

### 7. Derived data is rebuildable

Score entries can always be deleted and recomputed from predictions, the outcome grid and question outcomes. Never make a score entry the only place a fact lives.

---

## Frontend conventions

- React 18, TypeScript in strict mode, Vite, React Router, TanStack Query, React Hook Form with Zod, Tailwind CSS.
- The service layer exposes one `ApiClient` interface with two implementations: `MockApiClient` and `HttpApiClient`. Selection is by environment variable.
- `MockApiClient` uses deterministic seed fixtures. Fixtures must cover a two-draw Grand Slam mid-tournament, a finished game and a game open for signup.
- Every `ApiClient` method has an explicitly declared request and response type. No `any`, no implicit return types on service methods.
- Prediction payload shapes are discriminated unions keyed on question kind. Do not widen them to a permissive record type.
- Participant views are phone-first. Admin views may assume a desktop viewport.
- English only. Do not introduce an i18n framework.

## Backend conventions

Layering, with dependencies pointing inward:

```
api/          FastAPI routers, request and response schemas, auth dependencies
domain/       entities, scoring engine, validation rules — no framework imports
services/     use cases orchestrating domain and repositories
repositories/ persistence interfaces and implementations (memory, sqlalchemy)
providers/    tennis data, email — interfaces and mocks
```

- FastAPI, Pydantic v2, Argon2 for password hashing, session cookies.
- Repository interfaces are defined once and implemented twice. Step 4 swaps the implementation without touching `services/` or `domain/`.
- Authorisation is checked server-side on every admin route. Never rely on the frontend hiding a button.
- Errors follow RFC 7807 problem details. Timestamps are ISO 8601 UTC.

---

## Testing expectations

- The scoring engine has unit tests covering every question kind, including zero-point and partial-credit cases. This is the highest-value test surface in the project.
- Validation rules from spec Section 5.3 are tested individually.
- From step 4: the existing suite passes against both the in-memory and the SQLAlchemy repository implementations.
- Frontend: Vitest and React Testing Library for the service layer and form validation, Playwright for one end-to-end path per role.
- Do not write tests that assert on mock fixture contents in a way that makes changing a fixture a test rewrite.

## Commands

Keep these accurate. An agent that cannot run the tests will not write good code.

```bash
# frontend — Node 20+
cd frontend
npm install
npm run dev          # Vite dev server, runs against MockApiClient
npm run test         # Vitest, one pass
npm run test:watch   # Vitest, watching
npm run lint         # ESLint, including the no-HTTP-outside-services rule
npm run typecheck    # tsc --noEmit
npm run build        # typecheck, then production build
```

`VITE_API_CLIENT` selects the implementation: `mock` (default, no backend
needed) or `http` (step 3 onward). Copy `.env.example` to `.env` to change it.

```bash
# backend — from step 3
cd backend && uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
```

## Commits and branches

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- One logical change per commit. A commit that touches the contract, the backend and the frontend is three commits unless they are genuinely inseparable.
- Branch per unit of work, named `step-<n>/<short-description>`.
- Never commit secrets, `.env` files, or real participant data.

---

## When you are uncertain

- **A decision in the spec seems wrong.** Say so, explain why, and stop. Do not implement the alternative and mention it afterwards. The decision log exists so that reopening a decision is a conversation, not a commit.
- **The spec is silent.** Spec Section 14 lists the known open questions. If your question is there, ask. If it is not, make the smallest reasonable choice, implement it, and flag it in your summary.
- **You need a new dependency.** Ask first. This project deliberately runs on a small stack with no scheduler, no queue and no external services in the MVP.
- **Something is out of scope.** Spec Section 12 lists exclusions explicitly. Out of scope means out of scope, including "while I was in there anyway".

## Scope reminders

Not in the MVP, by decision: entry fees and prize pots, doubles and qualifying draws, live score polling, background jobs and schedulers, notifications beyond transactional email, file and image upload, OAuth and two-factor authentication, internationalisation, full bracket tree modelling, and admin-editable marketing content.

Not in the first pass, by decision D14: see the deferred list above and spec 13.1.

If a task appears to require one of these, it is the task that is wrong. Stop and ask.
