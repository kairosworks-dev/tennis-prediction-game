# AGENTS.md

Instructions for coding agents working in this repository. Read this before making any change. It is written to be tool-agnostic: `CLAUDE.md` only includes this file, and the agent capabilities live in plain folders (see *Agent extension pack* below).

## What this is

A web application for running tennis prediction competitions. One competition covers one tournament. Participants predict the tournament outcome before play begins and submit smaller predictions round by round. Points accumulate into a leaderboard.

The authoritative specification is [`docs/product-and-technical-spec.md`](docs/product-and-technical-spec.md). Read it before your first substantive change. Its decision log (Section 11) is binding.

[`docs/status.md`](docs/status.md) records where the code actually stands
against that spec and against the course criteria — unmet definitions of done,
known defects, open decisions. Read it before picking up work, and update it
when you close something.

## Repository layout

```
/backend              FastAPI application, domain layer, repositories, unit tests
/frontend             React application and its service layer
/tests/integration    integration tests, run against the compose stack
/docs                 spec, status, process, roles, AI usage report, pack docs
/agent-capabilities   reusable workflows and subagent definitions (tool-agnostic)
/agent-hooks          guardrail scripts
/mcp-server           one scoped MCP tool                       (issue #15)
/custom-agent         headless agent for red CI runs            (issue #16)
/ops                  sanitised operational evidence
/security             audit, scan and policy artefacts
/.github/workflows    CI and the gated deploy
/.claude              links into agent-capabilities/ and the hook wiring
AGENTS.md             this file
CLAUDE.md             includes this file
Dockerfile            one image: backend serving the built frontend
docker-compose.yml    app + Postgres
Makefile              make run, make test, make check, make test-integration
openapi.yaml          the API agreement between frontend and backend
product-spec.md       pointer to docs/product-and-technical-spec.md
README.md             setup, run, test and deploy instructions
```

Folders marked with an issue number arrive with that issue.

## Where we are

The MVP was built in four sequential steps, each with a definition of done in spec Section 9. All four are **done** (frontend on mocks, `openapi.yaml`, FastAPI backend, SQLAlchemy persistence), to the narrowed screen surface of decision D14.

**Now: the final-project phase.** The work is to ship and operate the app: Postgres, containers, integration tests, CI/CD, deployment, the agent extension pack, hardening artefacts and documentation. Spec Section 9, step 5, holds the definition of done; **the work items are the GitHub Issues of this repository**, and [`docs/process.md`](docs/process.md) says how an issue moves from open to closed. Pick work from the issues, not from this file.

**The screen surface stays narrowed** (decision D14, spec 13.1). Deferred: admin screens other than the outcome grid and recalculation; email verification, password reset, profile editing and account deletion; the draw view; the post-lock comparison view; the landing-page gallery and testimonials. Deferred means *not now*, not *never* — Section 4 still describes the intended product, so do not delete its requirements. The architecture is **not** narrowed: every hard rule below applies in full.

## By-hand ops tasks — not agent work

Some issues carry the label **`by-hand`** (#8 monitoring and alerting, #9 backups, #10 rollback drill, #11 the public `ops/` evidence). The author does these himself, on the server, as part of his own operations learning. **An agent does not do them**, does not script them in advance, and does not close them. An agent may review the written evidence for leaks and formatting when asked. The AI usage report records this split honestly.

## Public repository

This repository is public. **Nothing in it names the author's infrastructure:** no server names, IP addresses, firewall rules, backup bucket names, credentials, personal paths, or the author's private notes and their locations. Operational evidence in `ops/` is written as *what was done, when, and the measured result*, nothing more. A commit-gate hook ([`agent-hooks/`](agent-hooks/), issue #14) blocks the common patterns; it is a backstop, not a licence. When in doubt, leave the detail out.

---

## Hard rules

These are the constraints that are cheap to violate and expensive to unwind. Breaking one is a defect regardless of whether tests pass.

### 1. No HTTP calls outside the frontend service layer

Every backend interaction goes through `frontend/src/services/`. No component, hook, page or utility imports `fetch`, `axios`, or any HTTP client directly. There is an ESLint rule enforcing this; do not disable it, and do not add exceptions.

### 2. No business logic in the frontend

Validation, scoring and rule enforcement live in the backend. The frontend duplicates validation for user experience only. When the two disagree, the backend is right. Never implement a rule in the frontend that does not also exist server-side.

### 3. `openapi.yaml` is the contract

Changing an endpoint means changing the spec first, then both sides. Never let the FastAPI-generated schema and the committed `openapi.yaml` drift. `backend/tests/test_contract_drift.py` fails on drift and CI runs it; fix the cause, not the check. The `api-reviewer` subagent exists for exactly this review. One recorded exception: the operational probes `/health` and `/ready` are not in the contract (spec decision D17).

### 4. The domain layer imports no framework

`backend/app/domain/` contains entities, the scoring engine and validation rules. It imports no FastAPI, no SQLAlchemy, no HTTP client, no settings object. If you need one of those in `domain/`, the design is wrong.

### 5. Scoring is a pure function

The scoring engine maps `(predictions, outcome grid, question outcomes, scoring profile)` to score entries. No I/O, no clock reads, no randomness, no database access. It must be testable with plain data structures.

### 6. External dependencies sit behind interfaces

Tennis data, authentication and email are each an interface with a mock implementation. Call sites depend on the interface, never on a concrete vendor. See spec Sections 7.2 and 7.4.

### 7. Derived data is rebuildable

Score entries can always be deleted and recomputed from predictions, the outcome grid and question outcomes. Never make a score entry the only place a fact lives.

### 8. The database is a URL

Persistence goes through the repository interfaces, implemented in memory and with SQLAlchemy. The SQLAlchemy implementation is dialect-agnostic: SQLite for local work and unit tests, Postgres in production (decision D15). No raw SQL, no dialect-specific column types outside `repositories/models.py`, no code path that knows which database it is on.

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

- FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Argon2 for password hashing, session cookies.
- Repository interfaces are defined once and implemented twice. The SQLAlchemy implementation serves SQLite and Postgres from the same code (hard rule 8).
- Configuration comes from the environment: `DATABASE_URL`, `REPOSITORY_BACKEND`, `SESSION_SECRET`, `COOKIE_SECURE`. Defaults are development-only and say so. Never a secret in a file.
- Authorisation is checked server-side on every admin route. Never rely on the frontend hiding a button.
- Errors follow RFC 7807 problem details. Timestamps are ISO 8601 UTC.

---

## Testing expectations

- **Unit tests** live next to the code: `backend/tests/` (pytest; the suite runs against the in-memory, the SQLite and, when `TEST_DATABASE_URL` is set, the Postgres repositories) and `frontend/src/**/*.test.ts(x)` (Vitest, React Testing Library).
- **Integration tests** live in `tests/integration/` at the root, talk HTTP to a running compose stack, and cover the key workflows end to end. They are never mixed into the unit suite.
- The scoring engine has unit tests covering every question kind, including zero-point and partial-credit cases. This is the highest-value test surface in the project.
- Validation rules from spec Section 5.3 are tested individually.
- Playwright for one end-to-end path per role is specified and not built; see `docs/status.md`.
- Do not write tests that assert on mock fixture contents in a way that makes changing a fixture a test rewrite.

## Commands

Keep these accurate. An agent that cannot run the tests will not write good code.

`make` from the repository root lists every target; `make run` starts the whole
app and `make check` runs lint, typecheck and every unit test. The underlying
commands are below and remain the source of truth.

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
needed) or `http`. Copy `.env.example` to `.env` to change it.

```bash
# backend
cd backend && uv sync
uv run alembic upgrade head && uv run python scripts_seed.py
REPOSITORY_BACKEND=sqlalchemy uv run uvicorn app.main:app --reload   # `sqlite` is an alias
uv run pytest
uv run ruff check .
```

`DATABASE_URL` picks the database (default `sqlite:///./tennis.db`; Postgres:
`postgresql+psycopg://user:pw@localhost:5432/tennis`). On Postgres the schema
comes only from `uv run alembic upgrade head`. `TEST_DATABASE_URL` (a throwaway
Postgres database, never the one `DATABASE_URL` names) adds a Postgres
parameter to the backend suite; without it that parameter is skipped.

Docker and the integration tests: see the README once issues #2–#4 land; the
Makefile targets are `make test-integration` and `docker compose up --build`.

## Commits, branches and the process

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`.
- One logical change per commit. A commit that touches the contract, the backend and the frontend is three commits unless they are genuinely inseparable.
- **Trunk-based.** `main` is always deployable and is what the pipeline deploys. One short-lived branch per issue, named `issue-<n>/<short-description>`, merged by pull request after QA passes. Documentation-only changes go straight to `main`.
- Who does what: the engineer commits on the issue branch; the orchestrator opens the PR and merges after a QA `PASS`; the author pushes `main`. Full process, roles, stop rules and label legend: [`docs/process.md`](docs/process.md).
- Never commit secrets, `.env` files, real participant data, or anything the *Public repository* section excludes.

## Agent extension pack

Canonical, tool-agnostic locations; `.claude/` only links to them.

| Capability | Where |
|---|---|
| Project instructions | this file |
| Reusable workflows | `agent-capabilities/implement-issue/`, `agent-capabilities/review-api-change/`, `agent-capabilities/debug-ci-failure/` |
| Subagents | `agent-capabilities/subagents/` (`pm`, `software-engineer`, `qa-engineer`, `api-reviewer`) |
| Hook / guardrail | `agent-hooks/` |
| MCP server | `mcp-server/` (issue #15) |
| Custom agent | `custom-agent/` (issue #16) |
| Permissions and security note | `docs/permissions.md` |
| Pack overview and demo | `docs/agent-extension-pack.md`, `docs/demo.md` (issue #17) |

---

## When you are uncertain

- **A decision in the spec seems wrong.** Say so, explain why, and stop. Do not implement the alternative and mention it afterwards. The decision log exists so that reopening a decision is a conversation, not a commit.
- **The spec is silent.** Spec Section 14 lists the known open questions. If your question is there, ask. If it is not, make the smallest reasonable choice, implement it, and flag it in your summary.
- **You need a new dependency.** Ask first. The *application* deliberately runs as one process with no scheduler, no queue and no external services (spec 7.1, principle 5). Platform services around it — the database server, the reverse proxy, the CI runner, the backup job — are not application dependencies and are in scope.
- **Something is out of scope.** Spec Section 12 lists exclusions explicitly. Out of scope means out of scope, including "while I was in there anyway".
- **The task is labelled `by-hand`.** It is not yours. Say so and stop.

## Scope reminders

Not in the MVP, by decision: entry fees and prize pots, doubles and qualifying draws, live score polling, background jobs and schedulers *inside the application*, notifications beyond transactional email, file and image upload, OAuth and two-factor authentication, internationalisation, full bracket tree modelling, and admin-editable marketing content.

Not in the first pass, by decision D14: see the deferred list above and spec 13.1.

If a task appears to require one of these, it is the task that is wrong. Stop and ask.
