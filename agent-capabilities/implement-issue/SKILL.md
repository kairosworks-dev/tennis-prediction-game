---
name: implement-issue
description: Run one GitHub issue through the project's process - PM grooms, the author reviews, the engineer builds on an issue branch, QA verifies, then a pull request. Use when asked to implement, work on or ship issue #N.
---

You are the orchestrator for issue #$ARGUMENTS. Follow `docs/process.md`; do not groom, implement or test yourself.

1. `gh issue view $ARGUMENTS`. If it carries the label `by-hand`, stop and say the issue belongs to the author.
2. If it does not carry the label `groomed`: launch the `pm` subagent to groom it. Show the author the groomed body and **wait for their approval** before going on.
3. Launch the `software-engineer` subagent with the issue number. It works on `issue-$ARGUMENTS/<short-description>`.
4. Launch the `qa-engineer` subagent with the issue number. Read its verdict from the issue comments.
5. On `FAIL`: relaunch the engineer with the QA comment as input, then QA again. After the third `FAIL`, stop and hand the issue to the author with a summary.
6. On `PASS`: if the change touched `openapi.yaml`, `backend/app/api` or `frontend/src/services`, launch `api-reviewer` first and treat its `FAIL` like a QA `FAIL`. Then push the branch and open the pull request: `gh pr create --fill --body "Closes #$ARGUMENTS"`. Report the PR link to the author. The author reviews and merges; merging closes the issue.

Never close the issue yourself, never merge without the author's go, never commit secrets or private infrastructure names (`AGENTS.md`, *Public repository*).
