# Process

How a work item moves from open to closed in this repository. `AGENTS.md` links here; the role files in `docs/team/` and the workflows in `agent-capabilities/` implement it.

## The system of record

- Work items are **GitHub Issues** in this repository, one per gradable unit of work. Nothing is tracked in a file.
- New issues follow [`task-template.md`](task-template.md): goal, acceptance criteria, out of scope, constraints.
- An issue is worked on **one at a time** unless the worktree rule below applies.

## Roles

| Role | Does | Must not | Defined in |
|---|---|---|---|
| **Orchestrator** | The main session. Picks the issue, launches the roles below as subagents, opens and merges the pull request, closes the issue | Groom, implement or test itself | this file |
| **PM** | Grooms one issue against the template; files follow-ups for what moves out of scope | Write code | [`team/pm.md`](team/pm.md) |
| **Engineer** | Implements one groomed issue on its branch, with tests; commits; comments | Close the issue; edit the acceptance criteria | [`team/software-engineer.md`](team/software-engineer.md) |
| **QA** | Checks the result against the acceptance criteria and the running code; posts `PASS` or `FAIL` with evidence | Change any file | [`team/qa-engineer.md`](team/qa-engineer.md) |
| **API reviewer** | Reviews a change against `openapi.yaml` (hard rule 3) | Change any file | [`../agent-capabilities/subagents/api-reviewer.md`](../agent-capabilities/subagents/api-reviewer.md) |
| **Author** | Reviews the groomed issue before anyone builds; reviews the pull request; pushes `main`; does the `by-hand` issues | — | — |

Each role runs in a **fresh context** (a subagent), so the engineer's reasoning never leaks into QA's verdict and nobody grades their own work.

## Lifecycle, per issue

```
issue → PM grooms → author reviews → engineer builds → QA verifies
                                           ↑                │ FAIL (≤ 3)
                                           └────────────────┘
                                     PASS → orchestrator merges PR, closes
```

1. Orchestrator picks the next open issue (dependency order in `status.md`).
2. PM grooms it. The author reads the groomed issue and corrects it if needed.
3. Engineer creates the branch `issue-<n>/<short-description>` from `main`, implements, writes tests, commits on the branch, comments on the issue.
4. QA verifies on that branch and posts `PASS` or `FAIL`.
5. On `FAIL`: back to step 3 with the QA comment as input. After three `FAIL`s, stop and hand the issue to the author.
6. On `PASS`: orchestrator opens a pull request (`Closes #n` in the body), CI runs, the author reviews, the orchestrator merges. Merging closes the issue.
7. The author pushes `main`; the pipeline deploys.

## Rules

- Do not skip grooming. **Groom once**: a `FAIL` returns to the engineer, never to the PM. Only an acceptance criterion that is wrong, impossible or self-contradicting reopens grooming, and that is reported by the engineer or QA as a comment, not fixed silently.
- The engineer does not close issues. QA does not fix code. The orchestrator closes only after `PASS`.
- A task labelled **`by-hand`** is the author's. Agents do not implement it, script it or close it; they may check its written evidence for leaks when asked.
- No PM acceptance step on this project: the author's review of the groomed issue and of the pull request covers it.

## Branching and commits

- **Trunk-based.** `main` is always deployable; the pipeline deploys what `main` points to.
- One short-lived branch per issue, `issue-<n>/<short-description>`, merged by pull request after `PASS`. Documentation-only changes commit straight to `main`.
- Who commits: the engineer on the issue branch; the orchestrator merges; the author pushes `main`.
- Conventional commits, one logical change per commit (see `AGENTS.md`).
- **Worktrees:** two issues run in parallel only when they touch disjoint files, each in its own git worktree; the orchestrator merges one at a time and deletes the worktree. Default is sequential.

## Issue states and labels

| State | How you see it |
|---|---|
| Open | No `groomed` label |
| Groomed | Label `groomed` |
| In progress | A branch `issue-<n>/…` exists |
| Done | Closed by a merged pull request |

| Label | Meaning |
|---|---|
| `criterion-N` | The course criterion (final rubric, numbered 1 to 12, see `docs/status.md`) this item earns points for |
| `pack` | Agent extension pack item |
| `security` | Security, audit or hardening artefact |
| `docs` | README, spec, status, reports |
| `by-hand` | Done by the author, not by an agent; see `AGENTS.md` |
| `ungraded` | Not graded by the final rubric (D18); kept for learning, done last |

The milestone **Project 1 — 27 Oct** holds the open issues to finish before submission, graded or not. The ungraded issues, which are done after submission, are not in it, and closed issues are not in it.

## Decisions behind this process

- **Trunk-based with a PR per issue**, not direct commits to `main`: a PR is what CI gates and what the PR audit (issue #18) reviews. Two deployed environments, dev and production (D19, #55): a green `main` deploys to dev, production is promoted by hand.
- **No PM acceptance step**: it is the fourth agent per issue on a one-person project with ten days; the author reviews the groomed issue and the PR instead.
- **Worktrees only on demand**: the first week's issues depend on each other in sequence.
- **Agent-agnostic**: the role files, workflows and hooks are plain folders; `.claude/` only links to them, so another coding agent is pointed at the same files.
