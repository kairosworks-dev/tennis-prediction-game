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

### Step 1 — Frontend against a mocked service layer

*In progress.*

---

### Step 2 — API contract

*Not started.*

---

### Step 3 — FastAPI backend, in-memory

*Not started.*

---

### Step 4 — Persistence

*Not started.*

---

## Reflections

*To be completed at the end of the module: what AI assistance did well, where it
needed correction, and which of the three enforcement mechanisms above actually
earned their keep.*
