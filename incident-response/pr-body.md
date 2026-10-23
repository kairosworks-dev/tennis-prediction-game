## On-call fix: $title

Opened by the **on-call responder** (`incident-response/`, #58) after the alert
**$title** fired. The fix and its regression test were written by the on-call
coding agent, headless, under `incident-response/mandate.md`; the responder,
ordinary code, checked the result and pushed this branch. Nobody has reviewed it
yet. **The author reviews and merges; nothing merges itself.**

### The alert

| | |
|---|---|
| Alert | `$title` |
| Endpoint | `$endpoint` |
| Firing since | $starts_at |
| Window | $window |
| Summary | $summary |
| Fingerprint | `$fingerprint` |
| Incident | `$incident_id` (local, gitignored folder on the author's machine) |

### What the responder checked (not the agent's claim)

- Agent's result line: `$result_line`
- At least one commit on `$branch` beyond `$base`
- A test added or changed under `backend/tests/`:
$tests
- No denied path touched (`.github/`, `agent-hooks/`, `.claude/`, `incident-response/`, `openapi.yaml`, `Dockerfile`, `docker-compose*.yml`, `backend/pyproject.toml`, `backend/uv.lock`)
- Nothing left uncommitted in the worktree
- Its own `uv run pytest` in the worktree is green: `$pytest_tail`
- `core.hooksPath` unchanged across the run

### Commits

$commits

### Files changed

$files

### Before merging

- [ ] The new test reproduces the alert's failing request, and was seen red before the fix (agent output in the incident folder)
- [ ] The fix removes the cause; it does not swallow an exception or change a status code
- [ ] CI is green on this branch
- [ ] After merging into `$base`: rebuild the app service, `make demo-trigger` answers 200, the alert returns to Normal

Label `on-call-agent`. The agent's commit carries a `Co-Authored-By:` trailer.
