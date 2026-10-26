# Project status

**Last updated:** 26 October 2026

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
| 5 | Ship and operate: Postgres, containers, integration tests, CI/CD, deploy, observability, alert, on-call agent, docs | **Done for every graded criterion on 23 Oct** (24 of 24, see *Against the course criteria* below). Open: the ungraded issues, the by-hand #9 to #11 and the integration coverage #43 to #45, all after the submission |

**It runs.** `make install && make run` migrates, seeds a demo game, starts the
backend on :8000 and the frontend on :5173 pointed at it. `make run-mock` runs
the frontend alone on fixtures with no backend at all. Walked end to end in a
browser: sign-in including the failure path, the game list in three states,
joining a game, the tournament-bet cascade, submitting a prediction that
persists to SQLite, scores, the tied ranking, and the organiser's outcome grid
and recalculation.

The same app runs as one image on Postgres: `docker compose up --build` locally,
and in a dev environment (deployed on every green push to `main`) and a
production environment (promoted by hand), both over HTTPS. On the author's
machine, as an optional local demo (D20), `make telemetry-up` adds the telemetry
stack and the 5xx alert, and `make responder` the on-call responder.

**Tests, as `make check` reports them on 26 October.** 119 frontend (Vitest);
310 backend results (pytest), because the backend suite runs once per
repository implementation (memory, SQLite) and, with `TEST_DATABASE_URL` set,
a third time on Postgres (72 more results, skipped locally, run in CI); 110 for
the on-call responder; 128 for the commit gate. The integration suite in
`tests/integration/` runs against the compose stack with `make test` or
`make test-integration`.

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
`samesite=lax`, which does block the classic cross-site POST.

Newly relevant because decision D8 — session cookies rather than bearer tokens —
was raised and confirmed on 14 September. CSRF matters precisely because the
session is a cookie.

**15 Oct:** the `secure` flag is issue #7 (with the HTTPS deploy). CSRF and rate
limiting stay open and named; the security scan (#19) and the policy (#22)
report them as known gaps rather than hiding them. The deployment runs demo
data only, by decision, until the course is over.

**17 Oct (issue #59):** registration email addresses and tokens are not written to
the output of a deployed environment. `EMAIL_PROVIDER` defaults to `discard`, which
writes nothing, and the `console` provider (stderr, local development and the dev
compose stack only) must be asked for. No deployment sets it.

**19 Oct (issue #7):** the `secure` flag is built. `COOKIE_SECURE=true` marks the
session cookie `Secure` on login, register and logout (the logout deletion carries
the attributes of the cookie it deletes). The default is `false`, development-only,
so the compose stack keeps working over plain HTTP. Parsing is strict: only `true`
and `false` (or unset or empty, meaning `false`) are accepted, and any other value
stops start-up. Unset in a deployment is silently insecure; the checks that catch
it are on the deployed environments (#6 and #55 verify `Secure` on the login
`Set-Cookie`). CSRF and rate limiting are still open, as #64 and #65.

### Smaller defects, tracked as issues

- #46: a locked bet group counts and shows drafts as answers.
- #47: an unknown `/api/` path answers `{"detail"}` instead of problem details.
- #62: the framework's own validation errors (422) are not problem details.
- #61: the contract drift test compares operations and paths only, not
  schemas, status codes or error responses.

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

## Against the course criteria

The project is graded on the course's **final** rubric, published on 16 October
2026 in the public course repository
([`project/README.md`](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md)):
12 criteria, 24 points, pass at 10. Three peer reviews of other projects are
also required to pass; they happen off-repository and are not a work item here.
The scores below were checked against the repository on 26 October 2026 and are
updated when an issue closes. The spec records the switch from
the earlier 14-criterion version (D18).

| # | Criterion | Today | Target | Closes with |
|---|---|---|---|---|
| 1 | Problem description | 2 | 2 | done: #23 (the README rewritten for the final project, PR #73) |
| 2 | Product specification | 2 | 2 | none |
| 3 | Agent team specification | 2 | 2 | none |
| 4 | Context management | 2 | 2 | none |
| 5 | Application | 2 | 2 | none |
| 6 | Testing | 2 | 2 | done: #54 (`make test` runs unit and integration tests); more coverage: #43 to #45 |
| 7 | Containerization | 2 | 2 | none |
| 8 | Deployment | 2 | 2 | done: #6 and #7 (dev deploys on every push to `main`, over HTTPS); #55 (production, and the public URL in README *Try it online*); the evidence in #11 adds depth, not points |
| 9 | CI/CD | 3 | 3 | done: #6 (every push to `main` deploys dev: 2); #55 (a manual promote to production through a shared deploy action: 3) |
| 10 | Observability | 2 | 2 | done: #56 (metrics, traces and structured logs of the key journey sharing a trace ID, viewed in Grafana, PR #72) |
| 11 | Alerting on user impact | 1 | 1 | done: #57 (a Grafana rule on 5xx of the key journey, with a webhook to the responder, PR #75) |
| 12 | On-call agent | 2 | 2 | done: #58 (the responder wakes on the alert and opens a checked fix, PR #76; run recorded in `incident-response/README.md`) |
| | **Total** | **24 of 24** | **24** | |

Criteria 8 and 9 reached 2 and 3 on 20 October with #55: the rubric (v2) gives 2
for "deployed and reachable at a public URL, or there's a clear demo with the
deployment", and 3 for "CI runs tests, CD deploys to dev, and there's a manual
deploy to production". Both were settled by the proof run of #55 on 20 October:
the merge push re-proved dev through the shared action, and a manual promote of
the same commit was approved
([recorded on the issue](https://github.com/kairosworks-dev/tennis-prediction-game/issues/55#issuecomment-6300030238)).

Criterion 6 reached 2 on 17 October with #54: `make test` runs the frontend
and backend unit tests and then the integration tests against the compose stack,
in one command.

Criteria 1, 10, 11 and 12 reached their targets between 22 and 23 October.
Criterion 1 with #23, the README rewritten to describe the problem, what the
system does and how it behaves. Criterion 10 with #56: the key journey (sign
in, open a game, submit a prediction; `docs/observability.md`) emits metrics,
traces and structured JSON request logs that share a trace ID, an allowlist in
the app and again in the Collector keeps customer data and credentials out
(D22), and Prometheus, Tempo and Loki store the signals, viewed in Grafana.
Criterion 11 with #57: one Grafana rule, provisioned as code, fires on 5xx of
that journey and calls the responder's webhook (`docs/alerting.md`). Criterion
12 with #58: the responder in `incident-response/` wakes on that alert, saves
the incident's context, starts a headless coding agent in its own worktree, and
publishes the fix as a pull request only after its own checks pass. The author
watched a live run end to end on 23 October (a code fault fixed, PR #77, CI
green), recorded in `incident-response/README.md`, *Recorded run*.

Criteria 10 to 12 are a **local demo** on the author's machine (D20): nothing
runs 24/7, the deployed environments send no telemetry, and the responder uses
the author's logged-in coding agent, not an API key. #56 to #58 were planned as
`by-hand` and were built by agents with the author reviewing every groomed issue
and pull request (D21); the checks #58 marks **(author)** were the author's.
Issues #8 to #11 (monitoring, backups, rollback, public `ops/` evidence) are
`by-hand`. #8 is done (the uptime check on the deployed app, distinct from the
alert of #57). #9 to #11 are done after the submission (D21); #10 and #11 add
evidence to criteria 9 and 8 but no points, and #9 earns no criterion. Agents
may review their written evidence for leaks and formatting when asked, nothing
more.

The ungraded issues (#15 to #22, #24) continue after the submission deadline;
the course grade is tied to the commit submitted, so later commits do not
change it.

## Recommended order from here

The tracker follows the same split with two milestones (`docs/process.md`):
**Project 1 — 27 Oct** holds only #25 open, next to the issues closed before
the submission; **After submission** holds every other open issue.

1. **Submission**: #25, the clean-clone run from the README and the submission
   of that commit.
2. **After the submission**: the integration coverage #43 to #45 (criterion 6
   is at its target, so they add depth, not points); the by-hand #9 to #11;
   the follow-ups of the local demo, #74 (telemetry targets share one Docker
   project across worktrees) and #78 (on-call agent hardening).
3. **The ungraded issues last**: #15 to #22 and #24 (D18), and the defects
   above.

Not on that path, and deliberately left where they are: the seed-placement
defect above, the generated frontend types and the Playwright paths. None of
them is graded; all three stay here as known gaps.
