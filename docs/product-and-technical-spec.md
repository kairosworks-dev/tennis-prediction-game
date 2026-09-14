# Tennis Prediction Game — Product and Technical Specification

**Status:** Draft v0.1
**Scope:** MVP definition and build plan
**Audience:** Product owner, implementing engineer, coding agents

---

## 1. Purpose

A web application for running a tennis prediction competition among a group of players. One competition covers one tournament. Participants predict the tournament outcome before play begins, then submit smaller predictions round by round while the tournament runs. Points accumulate into a leaderboard.

The concept is inspired by informal prediction games run among friends with a hand-maintained rulebook and a spreadsheet. The product replaces the spreadsheet, the manual scoring and the chat-message bet collection with a single application, and gives the organiser the ability to configure the rules per tournament rather than rewriting them each time.

### 1.1 Non-goals for the MVP

This is deliberately not a betting platform. No money, no odds, no payouts. See [Section 12](#12-out-of-scope) for the full exclusion list.

---

## 2. Glossary

| Term | Meaning |
|---|---|
| **Game** | One prediction competition, bound to exactly one tournament. Used interchangeably with *competition*. |
| **Tournament** | A real-world event (Grand Slam, ATP or WTA tour event) that a game is built around. |
| **Draw** | One singles bracket within a tournament. A Grand Slam game has two (ATP and WTA); a tour-level event has one. |
| **Section** | One eighth of a draw. Each section feeds exactly one quarter-final slot. |
| **Participant** | A signed-in user who has joined a specific game. |
| **Bet group** | A set of questions that share one deadline and lock together. |
| **Question** | A single predictable item. Either *typed* (draw-dependent, validated) or *generic* (admin-composed). |
| **Prediction** | A participant's submitted answer to a question. |
| **Outcome grid** | Per draw, the record of how far each player advanced. Drives all typed scoring. |
| **Organiser** | The admin role. Referred to as *admin* throughout. |

---

## 3. Users and roles

Two roles in the MVP, as a single global flag on the user record.

### 3.1 Participant

A registered user who joins games, submits predictions and views rankings. Cannot see other participants' predictions before a bet group locks.

### 3.2 Admin

A globally privileged user. Can do everything a participant can, plus manage users, create and configure tournaments, compose questions, set deadlines, enter results and trigger scoring.

**Assumption:** a single global admin role, not per-tournament ownership. Any admin can administer any game. Per-game delegation is a post-MVP concern.

---

## 4. Product requirements

### 4.1 Public landing page

Unauthenticated, single page, the entry point for new users.

| Block | Content | Source |
|---|---|---|
| Hero | Value proposition, primary call to action (sign up) | Static |
| How it works | Three to four steps explaining the game format | Static |
| Gallery | Screenshots and impressions from previous games | Static assets in the repo |
| Testimonials | Short quotes from past participants | Static |
| Upcoming game teaser | Next tournament, its start date, and the signup deadline | **Live from tournament data** |
| Footer | Legal notice, contact, privacy statement | Static |

The teaser block queries the next tournament whose signup deadline has not passed. If there is none, the block renders a neutral "no game currently open" state. All other content is maintained in a typed constants module in the frontend and changed by commit.

**Requirement:** the landing page must render without any authenticated call and must degrade gracefully if the teaser query fails.

### 4.2 Authentication and account

- **Sign up** with email, password and display name. Email verification required before joining a game.
- **Sign in** with email and password. Session established via HTTP-only cookie.
- **Password reset** by emailed token.
- **Profile page** showing display name, full name, email and account creation date, with an edit form. Email changes require re-verification.
- **Account deletion** available to the user. Deletes personal data; historical predictions and scores are retained in anonymised form so past leaderboards remain coherent.

Authentication sits behind an interface so that additional providers can be added later without touching call sites.

### 4.3 Game selection

A list of games visible to the signed-in user, grouped into three states:

1. **Open for signup** — signup deadline not passed. Shows a *Join* action.
2. **Running** — user is a participant. Shows current round, open bet groups and the user's rank.
3. **Finished** — read-only. Shows final leaderboard.

Public games are listed to everyone. Private games are hidden and joined by entering a join code.

Each card shows tournament name, category, surface, dates, participant count and the next relevant deadline.

### 4.4 Inside a game

Five views, reachable through a tab bar scoped to the game.

#### 4.4.1 Rules and key facts

Read-only. Tournament metadata (name, category, surface, location, dates, draw sizes, match format per draw), the game's scoring table rendered from its scoring profile, and a free-text rules section maintained by the admin in Markdown.

#### 4.4.2 Betting

The working surface. Lists every bet group for the game, ordered by deadline, each showing an open or locked state and a countdown.

- **Tournament bet group** — available before the tournament starts. Contains the typed questions (see [5.1](#51-tournament-bets)) for each draw.
- **Round bet groups** — one per round, per the admin's configuration. Contains an intro text, an optional featured-match question per draw, and any extra questions.

Behaviour:

- A participant may edit their predictions freely until the group's deadline.
- After the deadline, the form becomes read-only and submissions are rejected server-side.
- Partially completed groups are saved as drafts; validation for completeness runs on submit.
- Typed questions are validated against the draw (see [5.3](#53-validation-rules)). Invalid combinations are blocked in the UI and rejected by the API.

#### 4.4.3 My bets and scores

Per participant, a table of every question with: the participant's prediction, the correct answer (once settled), points awarded, and a short reason string explaining the award. Grouped by bet group, with a running total.

Before a group locks, only the participant's own predictions are visible. After it locks, a comparison view shows all participants' predictions for that group.

#### 4.4.4 Ranking

Leaderboard for the game, combining both draws where a tournament has two. Columns: position, display name, total points, points in the most recent settled group, movement since the previous round.

Ties share a position, and the next position skips accordingly. No tie-breaker in the MVP; total points is the only criterion.

An expandable row shows the per-bet-group breakdown for that participant.

#### 4.4.5 Draw

Per draw, the eight sections rendered as eight lists of entrants with seed numbers, plus each player's current round reached once the outcome grid has entries. A link field on the draw holds the URL of the official bracket for participants who want the full tree.

**Constraint:** the MVP does not model the bracket tree. It models section membership only. See decision D5.

### 4.5 Admin features

#### 4.5.1 User management

List, search, view, deactivate and reactivate users. Promote or demote the admin flag. Trigger a password reset on a user's behalf. No admin-initiated user creation in the MVP; users self-register.

#### 4.5.2 Tournament management

Create and edit a tournament: name, category (Grand Slam / ATP / WTA), surface, location, start and end date, signup deadline, visibility (public or private with join code), Markdown rules text, and the scoring profile.

Attach one or two draws. Per draw: tour, draw size, match format (best of three or best of five), official draw URL.

Populate each draw: assign entrants to sections with optional seed numbers. Entrants reference a global player registry, which the admin can add to inline.

Publish or unpublish the tournament. An unpublished tournament is invisible to participants.

#### 4.5.3 Question and deadline management

Per bet group: title, intro text, deadline, and the set of questions.

The tournament bet group is created with the typed questions for each draw. Round bet groups are created by the admin per round, each with:

- An intro text.
- Optionally one featured-match question per draw (predict the winner and the set score).
- Any number of extra questions using the generic engine, each with a prompt, an answer type, and a point value.

Generic answer types in the MVP: single player, match result, integer, single choice from a list.

#### 4.5.4 Results and scoring

Two entry surfaces, per decision D9:

1. **Outcome grid** — per draw, a table of entrants with a "round reached" selector. This single grid settles every typed question.
2. **Question answers** — per generic question, the correct answer in the shape of its answer type.

A **Recalculate scores** action rescores the game from current data and writes one score entry per participant per question, each with a reason string. Recalculation is idempotent and safe to run repeatedly.

Withdrawals and mid-match retirements are resolved by the admin adjusting the outcome grid or the relevant answer, with the reasoning captured in the reason string. See decision D12.

---

## 5. Game rules and scoring

The rules below are the **default profile** shipped with a new tournament. Every point value is editable per tournament through the scoring profile (decision D10). Structure is fixed; values are not.

### 5.1 Tournament bets

Submitted once per draw before the tournament begins.

| Question | Format | Default points |
|---|---|---|
| **Quarter-finalists** | One player per draw section (8 picks) | 1 per correct pick |
| **Semi-finalists** | 4 picks, each drawn from the quarter-final picks | 2 per correct pick |
| **Finalists** | 2 picks, each drawn from the semi-final picks | 3 per correct pick |
| **Champion** | 1 pick, drawn from the finalist picks | 5 |
| **Underperformer** | One player seeded in the top 10 | 3 / 2 / 1 for an exit in round 1 / 2 / 3, otherwise 0 |
| **Breakout** | One unseeded entrant | 2 / 3 / 4 / 5 / 7 for reaching round 4 / quarter-final / semi-final / final / winning |

A player may be nominated as the underperformer even if they also appear in the bracket picks. The two are scored independently.

### 5.2 Round bets

Per round, per draw, at the admin's discretion.

| Question | Format | Default points |
|---|---|---|
| **Featured match** | Winner and set score, e.g. a 3–1 win | 1 for the correct winner, 1 more for the exact set score |
| **Extra question** | Admin-composed, any generic answer type | Set per question by the admin |

The set-score point is awarded only when the winner is also correct. Round bets carry no consistency requirement against the tournament bets; a participant may contradict their own bracket.

Valid set scores derive from the draw's match format: 2–0 and 2–1 for best of three; 3–0, 3–1 and 3–2 for best of five.

### 5.3 Validation rules

Enforced in the API, mirrored in the UI:

- Quarter-final picks: exactly one player per section, eight in total.
- Semi-final picks: a subset of the quarter-final picks, size four.
- Finalist picks: a subset of the semi-final picks, size two.
- Champion pick: one of the finalist picks.
- Underperformer: must be an entrant with a seed of 10 or better.
- Breakout: must be an unseeded entrant.
- All predictions: the question's bet group must be open.
- Set score: must be a legal result for the draw's match format.

### 5.4 Scoring mechanics

- Scores are **persisted, not computed on read**. Each recalculation writes a score entry per participant per question with the points and a human-readable reason.
- The ranking query reads persisted totals, so it stays cheap as participants and questions grow.
- Editing a scoring profile does **not** retroactively rescore. It applies from the next recalculation onward, and the admin sees a warning to that effect before saving.

---

## 6. Domain model

### 6.1 Entities

```
User
  id, email, password_hash, display_name, full_name,
  is_admin, is_active, email_verified_at, created_at

Player                                  # global registry
  id, full_name, country_code, tour

Tournament
  id, name, category, surface, location,
  start_date, end_date, signup_deadline,
  visibility, join_code, status,
  rules_markdown, scoring_profile (JSON), created_at

Draw
  id, tournament_id, tour, draw_size, best_of, official_draw_url

DrawSection
  id, draw_id, index                    # 1..8

DrawEntry
  id, draw_id, section_id, player_id, seed                # seed nullable

Participation
  id, user_id, tournament_id, joined_at, status

BetGroup
  id, tournament_id, kind, round, title,
  intro_markdown, deadline, status

Question
  id, bet_group_id, draw_id, family, kind,
  prompt, answer_type, options (JSON),
  points_config (JSON), deadline_override, position

Prediction
  id, participation_id, question_id, payload (JSON),
  submitted_at, updated_at

OutcomeEntry                            # the outcome grid
  id, draw_id, player_id, round_reached, note

QuestionOutcome
  id, question_id, correct_answer (JSON), settled_at, note

ScoreEntry
  id, participation_id, question_id, points, reason, calculated_at
```

### 6.2 Key relationships

- `Tournament` has one or two `Draw`s. The draw is a first-class entity, not a field (decision D6).
- `Question` uses single-table inheritance. `family` is `TYPED` or `GENERIC`; `kind` narrows the typed case (`QF_PICKS`, `SF_PICKS`, `FINALIST_PICKS`, `CHAMPION`, `UNDERPERFORMER`, `BREAKOUT`) or is `null` for generic questions.
- `Prediction.payload` is a JSON document whose shape depends on the question's kind and answer type. Shapes are defined as discriminated unions in the OpenAPI schema and validated by Pydantic on the backend and Zod on the frontend.
- `ScoreEntry` is derived data. It can be deleted and rebuilt from predictions, the outcome grid and question outcomes at any time.

### 6.3 Enumerations

- `category`: `GRAND_SLAM`, `ATP`, `WTA`
- `tour`: `ATP`, `WTA`
- `surface`: `HARD`, `CLAY`, `GRASS`, `INDOOR_HARD`
- `round_reached`: `R128`, `R64`, `R32`, `R16`, `QF`, `SF`, `F`, `CHAMPION`, `WITHDREW`
- `bet_group.kind`: `TOURNAMENT`, `ROUND`
- `bet_group.status`: `DRAFT`, `OPEN`, `LOCKED`, `SETTLED`
- `answer_type`: `PLAYER`, `MATCH_RESULT`, `INTEGER`, `CHOICE`
- `tournament.status`: `DRAFT`, `PUBLISHED`, `RUNNING`, `FINISHED`

**Note on section sizes:** sections are assumed to be equal in size. Draws with byes or non-power-of-two sizes are handled by the admin distributing entrants sensibly; the application does not validate section balance.

---

## 7. Architecture

### 7.1 Principles

1. **Thin client.** All rules, validation and scoring live in the backend. The frontend enforces the same rules for user experience only, never as the authority.
2. **Every external dependency behind an interface.** Tennis data, authentication and email are each an interface with a mock implementation.
3. **Contract first from step 2 onward.** `openapi.yaml` at the repository root is the single agreement between frontend and backend.
4. **Derived data is rebuildable.** Scores can always be thrown away and recomputed from source data.
5. **One process.** No scheduler, no worker, no message queue in the MVP.

### 7.2 Frontend

| Concern | Choice |
|---|---|
| Framework | React 18, TypeScript, strict mode |
| Build | Vite |
| Routing | React Router |
| Server state | TanStack Query |
| Forms and validation | React Hook Form with Zod schemas |
| Styling | Tailwind CSS |
| Testing | Vitest, React Testing Library, Playwright for the critical path |

**Service layer.** Every backend interaction goes through `src/services/`. The layer exposes a single `ApiClient` interface. Two implementations:

- `MockApiClient` — in-memory fixtures, artificial latency, deterministic seed data covering a two-draw Grand Slam game mid-tournament. This is what step 1 runs on.
- `HttpApiClient` — generated types from `openapi.yaml`, `fetch` under the hood.

Selection is by environment variable. **No component, hook or page imports `fetch` or an HTTP library directly.** This is the constraint that makes step 1 meaningful and step 2 mechanical.

### 7.3 Backend

| Concern | Choice |
|---|---|
| Framework | FastAPI |
| Validation | Pydantic v2 |
| Persistence | In-memory repositories (step 3), SQLAlchemy 2.0 with SQLite (step 4) |
| Migrations | Alembic, introduced with step 4 |
| Auth | Session cookie, password hashing with Argon2 |
| Testing | pytest, httpx test client |

**Layering:**

```
api/          FastAPI routers, request/response schemas, auth dependencies
domain/       entities, scoring engine, validation rules — no framework imports
services/     use cases orchestrating domain + repositories
repositories/ persistence interfaces + implementations (memory, sqlalchemy)
providers/    tennis data, email — interfaces + mocks
```

The `domain/` package, and the scoring engine in particular, must be unit-testable without a database, an HTTP client or FastAPI. The scoring engine is a pure function of (predictions, outcome grid, question outcomes, scoring profile) to score entries.

### 7.4 The tennis data provider

Interface `TennisDataProvider`, with methods to fetch tournaments, draw entrants with seeds, and results. Implementations:

| Implementation | Step | Role |
|---|---|---|
| `MockTennisDataProvider` | 1 | Fixture data for development |
| `ManualTennisDataProvider` | 3 | Reads admin-entered data. **The only implementation the MVP requires.** |
| Vendor adapter | post-MVP | Pre-fills draws and the outcome grid for admin confirmation |

**Risk, stated explicitly:** there is no free, official, open tennis draw and results API. The realistic later options are freemium vendor APIs, scrapers of commercial score sites (with terms-of-use and stability risk), or open historical datasets that carry no live data. Any of these can break, rate-limit or change pricing mid-tournament. This is precisely why the MVP does not depend on one, and why admin-entered data remains the source of truth even after an adapter is added. **Verify the current state of any provider before committing to it.**

### 7.5 Non-functional requirements

- **Scale:** designed for tens of participants per game and a handful of games per year. SQLite is adequate and deliberate.
- **Performance:** ranking and betting pages under 300 ms server-side at expected scale.
- **Security:** Argon2 password hashing, HTTP-only cookies, CSRF protection on mutating requests, rate limiting on auth endpoints, server-side authorisation checks on every admin route.
- **Privacy:** personal data limited to email, display name and optional full name. Account deletion anonymises rather than cascades, so historical leaderboards remain intact.
- **Accessibility:** keyboard navigable, labelled form controls, sufficient contrast. The betting forms are the priority.
- **Responsive:** phone-first for participant views, since most predictions get submitted on a phone. Admin views may assume a desktop viewport.
- **Localisation:** English only. No i18n framework in the MVP.

---

## 8. API surface

Indicative resource list. The authoritative contract is `openapi.yaml`, produced in step 2.

```
POST   /auth/register
POST   /auth/login
POST   /auth/logout
POST   /auth/verify-email
POST   /auth/password-reset/request
POST   /auth/password-reset/confirm

GET    /me
PATCH  /me
DELETE /me

GET    /tournaments                       # filtered by visibility + participation
GET    /tournaments/{id}
POST   /tournaments/{id}/join             # body: optional join_code
GET    /tournaments/{id}/draws
GET    /tournaments/{id}/draws/{drawId}/entries
GET    /tournaments/{id}/bet-groups
GET    /tournaments/{id}/bet-groups/{groupId}/questions
GET    /tournaments/{id}/predictions      # own; all once groups are locked
PUT    /tournaments/{id}/questions/{qid}/prediction
GET    /tournaments/{id}/scores           # own breakdown
GET    /tournaments/{id}/ranking
GET    /public/next-game                  # landing page teaser, unauthenticated

GET    /admin/users
PATCH  /admin/users/{id}
POST   /admin/tournaments
PATCH  /admin/tournaments/{id}
POST   /admin/tournaments/{id}/draws
PATCH  /admin/draws/{id}
PUT    /admin/draws/{id}/entries
POST   /admin/tournaments/{id}/bet-groups
PATCH  /admin/bet-groups/{id}
POST   /admin/bet-groups/{id}/questions
PATCH  /admin/questions/{id}
PUT    /admin/draws/{id}/outcomes         # the outcome grid
PUT    /admin/questions/{id}/outcome
POST   /admin/tournaments/{id}/recalculate
GET    /admin/players
POST   /admin/players
```

Conventions: JSON throughout, ISO 8601 UTC timestamps, RFC 7807 problem details for errors, cursor-free pagination (offset and limit) where lists can grow.

---

## 9. Delivery plan

Four steps, each with a definition of done. No step starts before the previous one meets it.

### Step 1 — Frontend with a mocked backend

Build the complete React application against `MockApiClient`.

**Done when:**
- Every page in the **first-pass surface** (see [13.1](#131-deferred-from-the-first-pass)) renders and is navigable.
- A participant is walkable end to end on mock data, and an organiser can enter results and trigger a recalculation.
- Seed fixtures include a two-draw Grand Slam mid-tournament, a finished game and an open-for-signup game.
- No direct HTTP calls exist outside `src/services/`. Enforced by an ESLint rule.
- `ApiClient` is fully typed, with every method's request and response shape declared.

The original bar was every page in [Section 4](#4-product-requirements) and both
roles walkable in full. Decision D14 narrowed it; the deferred screens are listed
in [13.1](#131-deferred-from-the-first-pass) and the requirements in Section 4
still describe the intended product.

### Step 2 — API contract

Derive `openapi.yaml` from the `ApiClient` interface.

**Done when:**
- Every `ApiClient` method maps to exactly one documented operation.
- All schemas are named and reused; prediction payloads are modelled as discriminated unions.
- Errors are documented per operation.
- Frontend types are generated from the spec and the app still compiles against them.

### Step 3 — FastAPI backend, in-memory

Implement the contract with in-memory repositories.

**Done when:**
- Every operation in `openapi.yaml` is implemented. The contract carries only the
  operations the first-pass frontend uses (decision D14), so an endpoint that has
  no screen is not written twice before it is needed.
- FastAPI's generated schema matches the committed `openapi.yaml`; a CI check fails on drift.
- The scoring engine has unit tests covering every question kind, including zero-point and partial-credit cases.
- Validation rules from [5.3](#53-validation-rules) are enforced and tested.
- The frontend runs against `HttpApiClient` with no code changes beyond the environment variable.

### Step 4 — Persistence

Introduce SQLAlchemy and SQLite behind the existing repository interfaces.

**Done when:**
- Repository implementations are swapped; no service or domain code changes.
- Alembic migrations create the schema from empty.
- The existing test suite passes against both repository implementations.
- A seed script produces a realistic demo game.

---

## 10. Repository structure

```
/backend            FastAPI application and its tests
/docs               supporting documentation, including this file
/frontend           React application
AGENTS.md           instructions for coding agents
openapi.yaml        the API agreement
README.md           setup and run instructions
```

### 10.1 What belongs in AGENTS.md

`AGENTS.md` should encode the constraints that are easy for an agent to violate and expensive to unwind:

- The four-step plan and which step is currently active.
- **No HTTP calls outside the frontend service layer.**
- **No business logic in the frontend.** Validation there is duplicated for user experience; the backend is authoritative.
- `openapi.yaml` is the contract. Changing an endpoint means changing the spec first.
- The domain layer imports no framework.
- Scoring is a pure function and stays that way.
- Commands for install, run, test and lint, per package.
- Commit and branch conventions.
- The decision log in [Section 11](#11-decision-log) is binding. Reopening a decision is a conversation, not a commit.

---

## 11. Decision log

| # | Decision | Rationale |
|---|---|---|
| D1 | All external tennis data sits behind a `TennisDataProvider` interface | Keeps vendor risk at the edge of the system |
| D2 | Admin-entered data is the source of truth; the feed is an accelerator, not a dependency. No auto-scoring job | No free, reliable, open provider exists; the game must not break when a vendor does |
| D3 | Hybrid bet model: typed and validated for draw-dependent bets, generic engine for round bets and extras | Enforces the rules that matter; keeps improvised questions deploy-free |
| D4 | Self-join participation, with an optional join code for private games | One entity, supports public and private games, makes the ranking well-defined |
| D5 | Section-level draw model (8 sections per draw), not a full bracket tree | Most of the validation value at a fraction of the cost; upgrades to a full tree without an API break |
| D6 | `Draw` is a first-class child of `Tournament` (1..2 per game), with one combined ranking | Matches reality for Grand Slams; expensive to retrofit later |
| D7 | Deadlines per bet group, with an unexposed per-question override column. Predictions become visible once their group locks | Matches how the game is run; the column makes per-question deadlines a frontend change later |
| D8 | Email and password behind an `AuthProvider` interface; email sending behind its own interface with a console mock | No vendor needed for local development; OAuth becomes an added implementation |
| D9 | Outcome grid (player to round reached) drives typed scoring; generic questions get explicit answers. Scores persisted with an audit reason | One entry updates everything, stays internally consistent, and is exactly what a feed adapter would populate |
| D10 | Scoring profile as JSON per tournament, defaults pre-filled, no retroactive rescoring | The organiser tunes values without a deploy; no silent leaderboard rewrites |
| D11 | Transactional email only in the MVP; deadline reminders are the first post-MVP feature | Avoids a scheduler and its operational weight before there is evidence it is needed |
| D12 | Walkovers and retirements resolved by admin judgement through the outcome grid, explained in the audit reason | A human resolves these in seconds; a void-and-reopen mechanism can follow if it proves necessary |
| D13 | Static landing-page copy with a live teaser block. Ties share a position on total points. Finished games stay read-only | Only the part that goes stale is dynamic; no file storage decision needed |
| D14 | First pass builds a narrowed screen surface (see [13.1](#131-deferred-from-the-first-pass)). The architecture is not narrowed: the service layer, the contract, the backend layering, the pure scoring engine and the twice-implemented repository interface all stay | The product surface is what makes the build long; the architecture is what makes it correct. Every operation kept is built in the contract, the backend and the repository, so cutting screens compounds. The deferred items are a backlog, not an exclusion — Section 4 still describes the intended product |

---

## 12. Out of scope

Excluded from the MVP by explicit decision. Listed so that scope creep has to be deliberate.

**Product:**
- Entry fees, prize pots, payouts, any money handling
- Doubles, mixed doubles and qualifying draws
- Deadline reminders and any notification beyond transactional email
- Messaging, comments, chat, social feed
- Image and file upload, media storage
- Admin-editable marketing content
- Multi-admin roles or per-tournament admin delegation
- Tie-breakers in the ranking
- Cross-tournament season standings
- Public sharing of results outside the application

**Technical:**
- Live score polling, WebSockets, background jobs, schedulers
- OAuth, passwordless login, two-factor authentication
- Internationalisation
- Native mobile applications
- Full bracket tree modelling and automatic matchup derivation
- Retroactive rescoring after a scoring profile change

**Settled during the build, not up for reopening without a conversation:**
- **Token-based authentication.** Bearer tokens were raised while building the
  backend and rejected: decision D8 stands, and CSRF protection in 7.5 only
  makes sense with a cookie. Session cookies it is.
- **Deployment, containers and CI/CD.** Out of scope for this build by
  agreement — a later concern, not an MVP one. The contract drift check exists
  as a test so a pipeline has something to run when there is one.

---

## 13. Post-MVP backlog

One list, ordered by expected value rather than effort. The **Tier** column is
how near a thing is, not how important: *first pass* items were specified in
Section 4 and deliberately not built (decision D14), so the domain model, the
service layer and the API already accommodate them. *Post-MVP* items need
design before they need code.

| # | Item | Tier | Notes |
|---|---|---|---|
| 1 | **Admin screens** — user management, tournament creation, draw population, question composition | First pass | Roughly a third of the original step 1. The outcome grid and **Recalculate scores** were kept, because they close the loop from results to leaderboard; everything else is seeded by script. Spec 4.5.1–4.5.3 |
| 2 | **Account management** — email verification, password reset, profile editing, account deletion | First pass | Sign-up and sign-in were kept. Six endpoints and five screens for flows nothing yet exercises. Spec 4.2 |
| 3 | **Deadline reminders** | Post-MVP | The feature most likely to keep a casual game alive. Brings in a scheduler, which 7.1 principle 5 currently forbids |
| 4 | **The post-lock comparison view** — everyone's predictions once a group locks | First pass | A participant's own predictions and scores were kept. Spec 4.4.3, decision D7 |
| 5 | **The draw view** — eight sections with entrants and rounds reached | First pass | Section membership still drives pick validation; it is simply not rendered. Spec 4.4.5 |
| 6 | **Feed adapter** — pre-fill draws and the outcome grid from a vendor, organiser confirms | Post-MVP | Requires a provider evaluation first. Decision D2 means the game must keep working when it breaks |
| 7 | **Void and reopen** — question-level state allowing resubmission after a withdrawal | Post-MVP | Currently resolved by organiser judgement through the outcome grid (D12) |
| 8 | **Landing-page gallery and testimonials** | First pass | Hero, how it works and the live teaser were kept. Needs real photographs and real quotes before it is worth building. Spec 4.1 |
| 9 | **Full bracket model** — real matchup derivation, a rendered tree, per-match result entry | Post-MVP | Upgrades from the section model without an API break, by design (D5) |
| 10 | **Reusable scoring profiles** — named profiles as their own entity | Post-MVP | |
| 11 | **Per-question deadlines** | Post-MVP | Surface the override column already in the schema (D7) |
| 12 | **Season standings** — aggregate across tournaments | Post-MVP | |
| 13 | **Fees and pot** | Post-MVP | Only if the group ever wants it, with the legal implications examined first |

**Not deferred, and not negotiable:** the scoring engine and its unit tests, the
validation rules in 5.3, `openapi.yaml` as the contract with its drift check,
the framework-free domain layer, and the repository interface implemented
against both memory and SQLAlchemy. All of these are built.

Where the code stands against this document — unmet definitions of done, known
defects, open decisions — is tracked in [`status.md`](status.md), not here. This
section says what the product should be; that one says where it is.

---

## 14. Open questions

1. **Signup deadline versus tournament start.** Currently modelled as separate fields. Confirm whether late joiners should be allowed once a tournament is running, scoring zero for locked groups.
2. **Draw section imbalance.** Tournaments with byes produce uneven sections. Confirm that admin discretion is acceptable rather than validated.
3. **Player registry maintenance.** Entrants are typed once per draw. Confirm whether a name-matching helper is needed at MVP or whether manual entry for roughly 100 entrants twice a year is tolerable.
4. **Recalculation trigger.** Currently manual. Confirm whether saving the outcome grid should recalculate automatically.
5. **Legal footing.** A no-money prediction game among friends is low risk, but the privacy notice and terms on the landing page still need drafting. Not a technical question, but it blocks a public launch.
