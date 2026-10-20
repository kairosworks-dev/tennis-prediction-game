# Project status

**Last updated:** 19 October 2026

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
| 5 | Ship and operate: Postgres, containers, integration tests, CI/CD, deploy, extension pack, hardening, docs | **In progress since 15 Oct** — GitHub Issues #1 to #58; see *Against the course criteria* below |

**It runs.** `make install && make run` migrates, seeds a demo game, starts the
backend on :8000 and the frontend on :5173 pointed at it. `make run-mock` runs
the frontend alone on fixtures with no backend at all. Walked end to end in a
browser: sign-in including the failure path, the game list in three states,
joining a game, the tournament-bet cascade, submitting a prediction that
persists to SQLite, scores, the tied ranking, and the organiser's outcome grid
and recalculation.

**230 tests.** 95 frontend, 135 backend — the backend suite runs once per
repository implementation (memory, SQLite) and, with `TEST_DATABASE_URL` set,
a third time on Postgres (164 backend results, 29 more).

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
`Set-Cookie`). CSRF and rate limiting are still open.

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
The scores below were checked against the repository on 17 October 2026 and are
updated when an issue closes. The spec records the switch from
the earlier 14-criterion version (D18).

| # | Criterion | Today | Target | Closes with |
|---|---|---|---|---|
| 1 | Problem description | 1 | 2 | #23 |
| 2 | Product specification | 2 | 2 | none |
| 3 | Agent team specification | 2 | 2 | none |
| 4 | Context management | 2 | 2 | none |
| 5 | Application | 2 | 2 | none |
| 6 | Testing | 2 | 2 | done: #54 (`make test` runs unit and integration tests); more coverage: #43 to #45 |
| 7 | Containerization | 2 | 2 | none |
| 8 | Deployment | 0 | 2 | #6 and #7 done; still missing: a URL a reviewer can open (README, via #55 and #23) and the evidence in #11 |
| 9 | CI/CD | 2 | **3** | done: #6 (every push to `main` deploys dev: 2); #55 (3) |
| 10 | Observability | 1 | 2 | #56 (by hand) |
| 11 | Alerting on user impact | 0 | 1 | #57 (by hand; #8 feeds it) |
| 12 | On-call agent | 0 | 2 | #58 (by hand) |
| | **Total** | **16 of 24** | **24** | |

Criterion 6 reached 2 on 17 October with #54: `make test` runs the frontend
and backend unit tests and then the integration tests against the compose stack,
in one command. One judgement call remains. Criterion 10 is a 1 only
if uvicorn's default access log in the container counts as "emits logs": it is
unstructured, carries no trace ID, and the application itself logs nothing (the
email provider prints only when `EMAIL_PROVIDER=console`, which no deployment sets).

Issues #8 to #11 (monitoring, backups, rollback, public `ops/` evidence) and
#56 to #58 (observability, the alert on user impact, the on-call agent) are all
`by-hand`: the author does them themself, on their own machine and server, for
their own operations learning. #8 feeds criterion 11, #10 and #11 feed criteria
9 and 8, #9 earns no criterion, and criteria 10, 11 and 12 come from the
by-hand issues #56, #57 and #58. Agents may review their written evidence for
leaks and formatting when asked, nothing more.

The ungraded issues (#15 to #22, #24) continue after the submission deadline;
the course grade is tied to the commit submitted, so later commits do not
change it.

## Recommended order from here

1. **Graded work first**, in this order: #53 (this context) and #54 (one test
   command), both done 17 October, as is #59 (the email provider, which had to
   land before the deploy), and #7 (secure cookie), done 19 October; then #6
   (deploy to dev: step A, the image job and a deploy started by hand, merged 19
   October; step B, the deploy on every push to `main`, done), #55 (dev
   and production), #56, #57, #58, then #23 (README), #43 to #45 (integration
   coverage) and #25
   (clean-clone run and submission). #12 to #14 (process, workflows, commit
   gate) are graded evidence for criteria 3 and 4 and belong to this group.
2. **The by-hand issues** (#8 to #11 and #56 to #58) are the author's, done
   alongside the above.
3. **The ungraded issues last**: #15 to #22 and #24 (D18).

Not on that path, and deliberately left where they are: the seed-placement
defect above, the generated frontend types and the Playwright paths. None of
them is graded; all three stay here as known gaps.
