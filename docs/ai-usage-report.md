# AI Usage Report

A running log of how AI assistance was used to build this project, kept as the work
happens rather than reconstructed afterwards.

**Module:** AI Dev Tools Zoomcamp, Module 2 — Build and Ship an AI-Assisted Full-Stack App
**Repository:** `kairosworks-dev/tennis-prediction-game`

---

## Working method

The guiding constraint is that AI accelerates the work but does not own it. Each
step is specified before it is generated, generated output is reviewed before it is
committed, and no step begins before the previous one meets its definition of done
(spec Section 9).

Three mechanisms enforce this:

1. **`AGENTS.md`** — the constraints that are cheap for an agent to violate and
   expensive to unwind, stated once and applied to every session.
2. **The decision log** (spec Section 11) — binding. Reopening a decision is a
   conversation, not a commit.
3. **The step table** — marked *Active* on exactly one step, with an explicit
   instruction not to work ahead.

---

## Tools used

| Tool | Role |
|---|---|
| Claude (chat) | Drafting and refining the product and technical specification |
| Claude Code (Opus 5) | Repository work, review, implementation, git operations |
| Claude Design | Visual design of the frontend screens |

---

## Log

### Step 0 — Specification

**Outcome:** [`docs/product-and-technical-spec.md`](product-and-technical-spec.md),
575 lines. Product requirements, domain model, architecture, a four-step delivery
plan with per-step definitions of done, a 13-entry decision log, an explicit
out-of-scope list, and 14 recorded open questions.

**Method:** drafted conversationally, then hardened. The decision log was the most
valuable output — each entry pairs a decision with its rationale, which stops later
sessions from silently re-deciding.

**Notable decisions captured:**

- Admin-entered data is the source of truth for tennis results; any vendor feed is
  an accelerator behind an interface, never a dependency (D1, D2). There is no free,
  reliable, open tennis draw API, so the MVP is designed not to need one.
- Section-level draw model, eight sections per draw, rather than a full bracket tree
  (D5). Most of the validation value at a fraction of the cost.
- Scoring is a pure function and scores are persisted derived data, rebuildable at
  any time (D9).

**Human judgement applied:** scope was cut deliberately and recorded in Section 12
rather than left implicit. Open questions were written down as open rather than
resolved by guesswork.

---

### Step 0.5 — Repository setup

**Outcome:** repository initialised, `AGENTS.md` and `CLAUDE.md` in place, `.gitignore`
covering secrets, virtualenvs, `node_modules` and SQLite files, connected to GitHub.

**AI contribution:** review of the spec and agent instructions for internal
consistency before the first push.

**Issues the review caught:**

- `AGENTS.md` linked to `docs/product-and-technical-spec.md` while the directory was
  actually named `_docs/` — a broken link in the first file any agent reads.
  Directory renamed to match the spec.
- `README.md` was listed in the declared repository layout but did not exist.
- Local branch was `master` against a `main` default. Renamed before the first push.

**Human judgement applied:** each fix was proposed with its rationale and chosen
explicitly rather than applied silently.

---

### Step 0.75 — Frontend design

**Outcome:** a nine-artboard design canvas covering the participant screens,
published as an Artifact and kept as source in [`design/`](design/).

**Method:** Claude Design. The direction was delegated ("you pick") and settled
on warm editorial rather than a dark broadcast aesthetic, because the spec is
emphatic that this is friends replacing a spreadsheet, not a betting platform.
The tournament-bet cascade was built as a working prototype rather than a
static mockup, on the reasoning that it is the riskiest screen in the app and
worth feeling before implementing.

**What review caught:** a second pass over the artboards found eleven defects,
including a binding to a handler that was never returned — the section headers
looked interactive and were not — a score breakdown that summed to 26 against a
displayed total of 34, a rank that read 4th on two screens and 5th on a third,
and an underperformer pick that violated the seed-ten rule the same design
advertised two screens away.

**Human judgement applied:** the defects were reported before being fixed, and
the fix commit lists each one.

---

### Step 1 — Frontend against a mocked service layer

**Outcome:** a React application running entirely on in-memory fixtures. One
`ApiClient` interface, two implementations, selection by environment variable.

**Method:** the service layer was built first, before any screen, because it is
what step 2 derives the contract from. Prediction payloads are a discriminated
union keyed on question kind, so a quarter-final pick and a set score cannot be
confused for one another anywhere in the system.

**What review caught:** five fixture bugs, four of which only appeared when the
app was actually run rather than when tests were run — seeds assigned after
shuffling the pool, so seed 1 was a random unknown; a featured quarter-final
between two first-round losers; score reasons interpolating player ids instead
of names; questions settling before the round they asked about; and a session
that did not survive a page reload, which meant signing in only appeared to
work because the default session was already that user.

**Human judgement applied:** the ESLint rule enforcing "no HTTP outside the
service layer" was verified by writing a component that called `fetch`,
`window.fetch` and `axios`, and confirming all three were rejected. It later
caught a test importing the concrete client; rather than carve an exception,
the service layer grew a `createTestApiClient` seam.

---

### Step 1.5 — Rescoping

**Outcome:** decision D14 and spec section 13.1.

The spec described roughly twenty screens and thirty-four API operations. Every
operation kept is built three times — contract, endpoint, repository — and
twice more when it needs a screen and a test, so screen count compounds. The
first-pass surface was narrowed to nineteen operations and eight screens, the
architecture was left untouched, and the deferred items were written into the
backlog with a reason each rather than quietly dropped.

**Human judgement applied:** this was put to the product owner as a decision
rather than taken unilaterally, because `AGENTS.md` makes the decision log
binding. The cut was to product surface, never to the scoring engine, the
contract, the layering or the twice-implemented repository interface.

---

### Step 2 — API contract

**Outcome:** [`openapi.yaml`](../openapi.yaml), nineteen operations.

**Method:** derived from the `ApiClient` interface and checked one-to-one in
both directions. Validated as OpenAPI 3.1 by Redocly.

---

### Step 3 — FastAPI backend, in-memory

**Outcome:** all nineteen operations, layered with dependencies pointing
inward. 93 tests.

**Method:** the domain layer was written first and imports no framework. The
scoring engine is a pure function of predictions, the outcome grid, question
outcomes and the scoring profile — 41 tests exercise every question kind with
plain data structures, no database and no HTTP client.

**What review caught:** one test was wrong rather than the engine — it asserted
a zero-point case without putting anyone in the outcome grid who had reached
the round in question, so the engine correctly declined to settle it.

---

### Step 4 — Persistence

**Outcome:** SQLAlchemy and SQLite behind the existing interfaces, Alembic
migrations building fourteen tables from empty, a seed script producing a demo
game with a real leaderboard. 117 tests.

**What review caught:** the requirement to run the suite against both
repository implementations earned its keep immediately. SQLite has no
timezone-aware column type, so stored timestamps came back naive and the next
comparison against `datetime.now(UTC)` raised `TypeError`. The in-memory
implementation could never have surfaced it. A `UtcDateTime` type decorator now
normalises on the way in and marks UTC on the way out.

**Human judgement applied:** the seed was rewritten to go through the
repository interfaces rather than reaching into the in-memory store, so both
backends seed by the same path. An earlier version had a `getattr(repos,
"store", None)` in it, which would have made step 4 impossible to seed.

---

## Reflections

**What the three mechanisms were worth.**

`AGENTS.md` earned its keep in a way that was easy to measure: the ESLint rule
it mandated rejected three separate routes to the network, and then caught a
violation in code written to test the rule itself. The instruction to keep the
domain layer framework-free made the scoring engine trivially testable, which
is why it has the densest tests in the project.

The decision log was most valuable at the moment the scope was cut. Because D1
to D13 recorded *why*, the rescope could be surgical — cut screens, keep
architecture — rather than a negotiation from first principles. D14 was added
in the same form, so the next reader sees the reasoning rather than an
unexplained gap between the spec and the repository.

The step table mattered less than expected, because the work stayed in order
anyway. Its real value was as a place to record that step 1 was done to a
*narrowed* definition, which would otherwise have been invisible.

**Where AI assistance needed correcting.**

Almost every defect found in this project was found by *running* something, not
by generating it. The design canvas looked right and had eleven defects. The
fixtures passed 79 tests while assigning seed 1 to an unknown player. The
frontend appeared to sign in correctly for a reason that had nothing to do with
sign-in working. Tests written alongside code caught real bugs — the fixture
clock, the timezone decorator — but only the ones they were pointed at.

The pattern worth keeping: generate, then look at the actual artifact.

**What would be done differently.**

The screen surface should have been scoped before the frontend was designed
rather than after. The design canvas covers screens the first pass does not
build, which is not wasted — it is backlog documentation now — but the cut
would have been cheaper one step earlier.
