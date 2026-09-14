# Project status

**Last updated:** 14 September 2026

Where the code stands. This is deliberately a different question from the two
documents either side of it:

- [`product-and-technical-spec.md`](product-and-technical-spec.md) says what the
  product **should be** — requirements, decisions, scope, backlog.
- [`ai-usage-report.md`](ai-usage-report.md) says what we **did** and what we
  learned doing it.
- This file says what is **true of the code right now**, including the places it
  falls short of the spec.

Keep it current in place rather than starting a dated copy: the point of one
status file is that "where do we stand" has exactly one answer. Git history
holds the snapshots.

---

## Build state

| Step | Scope | State |
|---|---|---|
| 1 | React frontend against a mocked service layer | Done, to the narrowed surface in D14 |
| 2 | `openapi.yaml` derived from the service layer | Done |
| 3 | FastAPI backend, in-memory repositories | Done |
| 4 | SQLAlchemy and SQLite persistence | Done |

**It runs.** `make install && make run` migrates, seeds a demo game, starts the
backend on :8000 and the frontend on :5173 pointed at it. `make run-mock` runs
the frontend alone on fixtures with no backend at all. Walked end to end in a
browser: sign-in including the failure path, the game list in three states,
joining a game, the tournament-bet cascade, submitting a prediction that
persists to SQLite, scores, the tied ranking, and the organiser's outcome grid
and recalculation.

**215 tests.** 95 frontend, 120 backend — the backend suite runs twice, once
against each repository implementation.

---

## Unmet definitions of done

Items the spec or `AGENTS.md` asks for that are not built. None of them block
the app running; all of them are real.

### 1. Frontend types are not generated from the contract

Spec section 9, step 2: *"Frontend types are generated from the spec and the app
still compiles against them."*

`HttpApiClient` is hand-written against hand-written types in
`frontend/src/services/types/`. They agree with `openapi.yaml` today because
the contract was derived from them, but nothing enforces it.

**Why this matters more than it looks.** Drift is guarded in one direction only:
`backend/tests/test_contract_drift.py` fails if the contract and FastAPI's
schema disagree. There is no equivalent between the contract and the frontend,
so a backend change that updates both the contract and the server would leave
the frontend silently wrong until something broke at runtime.

**Fix:** `openapi-typescript` as a dev dependency, generate into
`frontend/src/services/http/`, and have `HttpApiClient` use the generated
types. Asking first, per `AGENTS.md` on new dependencies.

### 2. No end-to-end test

`AGENTS.md` testing expectations: *"Playwright for one end-to-end path per
role."* Playwright is not installed and there is no `e2e/` directory.

Every path listed under **Build state** above was walked by hand. That found
four fixture bugs and two real defects, so the manual pass earned its keep — but
it is not repeatable and nothing catches a regression in it.

**Fix:** Playwright, two specs — a participant placing a bet, an organiser
entering a result and recalculating.

### 3. Nothing runs the drift check automatically

`AGENTS.md` hard rule 3: *"CI fails on drift."* The check exists as a test; no
pipeline runs it. CI and deployment are out of scope for this build by
agreement (spec 12), so this is correctly deferred rather than forgotten — but
until there is a pipeline, rule 3 depends on somebody running `make check`.

---

## Known defects

### Seed placement lets the top two seeds meet in the quarter-finals

Both the backend seed and the frontend fixtures place seeds as
`pass_index * SECTIONS + section_index`, putting seed 1 in section 1 and seed 2
in section 2. Those sections pair up in the quarter-finals, so the world number
one and number two can meet there. In a real draw they are placed at opposite
ends and can only meet in the final. Seen rendering as a featured quarter-final
between the two top WTA seeds.

Cosmetic — no rule is wrong and no test is wrong — but it is the kind of detail
that makes a demo unconvincing to anyone who follows the sport. Fixing it
changes which players win sections, so
`frontend/src/services/mock/fixtures/scoreEntries.json` must be regenerated;
the drift guard in `fixtures.test.ts` will fail until it is.

### Unmet security requirements from spec 7.5

Section 7.5 asks for *"CSRF protection on mutating requests, rate limiting on
auth endpoints"*. Neither is built. The session cookie is `httponly` with
`samesite=lax`, which does block the classic cross-site POST, and there is no
`secure` flag for when this is not localhost.

Newly relevant because decision D8 — session cookies rather than bearer tokens —
was raised and confirmed on 14 September. CSRF matters precisely because the
session is a cookie.

---

## Decisions

### Settled

| | |
|---|---|
| **D1–D13** | As recorded in spec section 11. Unchanged. |
| **D14** | First pass builds a narrowed screen surface. Nineteen operations, eight screens. Architecture untouched. |
| **D8, reconfirmed** | Session cookies, not bearer tokens. Raised while building the backend; the spec and 7.5's CSRF requirement both point at cookies. |
| **Scoring lives in one place** | The frontend mock serves a committed snapshot produced by the backend's engine. No code in `frontend/src/` computes points. |

### Open

The five questions in spec section 14 are all still open. None blocks anything
built so far; each will bite when the deferred work arrives.

1. **Signup deadline versus tournament start** — bites when someone tries to join a running game.
2. **Draw section imbalance** — bites on the first tournament with byes.
3. **Player registry maintenance** — bites when an organiser types 128 entrants by hand for the first time.
4. **Recalculation trigger** — currently manual, and the organiser screen makes that explicit. Bites if saving the grid is expected to rescore.
5. **Legal footing** — privacy notice and terms. Blocks a public launch, nothing before it.

---

## Recommended order from here

1. **Fix the seed placement.** Cheapest, most visible, and makes every demo better.
2. **Close the 7.5 security gaps.** CSRF, rate limiting, the `secure` flag.
3. **Generate the frontend types.** Closes the one-directional drift guard.
4. **Add the two Playwright paths.** Makes the manual walk repeatable.
5. **Then the backlog**, in the order spec 13 sets out — admin screens first.

Items 1 and 2 are queued as tasks. Items 3 and 4 are unmet definitions of done
rather than new work, and should land before the backlog rather than after.
