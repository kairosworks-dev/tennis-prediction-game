# incident-response: the on-call responder

When the 5xx alert of #57 fires on the key journey, a small service on the
author's machine wakes up, saves what is needed to understand the incident,
starts the author's logged-in coding agent headless with a narrow mandate, and,
if the agent's fix holds up, pushes a branch and opens a pull request with a
regression test. It never pushes the base branch and never merges: the author
reviews and merges. Rubric criterion 12 (#58); the course's Homework 4 shape
(`POST /alerts` on port 8001, context saved, agent started headless, a marked
test notification changes nothing).

It is a **local demo** (decision D20): nothing here runs 24/7, nothing is wired
to the deployed app, and there is no paid API key. The agent is the author's
own coding agent CLI with its own login.

The run logic is trigger-neutral: an *incident* goes in, a branch and a pull
request (or an escalation) come out. The alert webhook is one entry point on
top of it (`oncall/alerts.py`, `oncall/receiver.py`); the CI-failure trigger of
#16 can be another.

## Contents

| Path | What it is |
|---|---|
| `oncall/` | The responder, Python standard library only (`python3` 3.9 or newer) |
| `oncall/receiver.py` | `POST /alerts` on `127.0.0.1` |
| `oncall/alerts.py` | Grafana webhook body -> incident, or the reason to ignore it |
| `oncall/context.py`, `oncall/prompt.py`, `oncall/redact.py` | Evidence from Loki, Tempo and the app container's stderr; the prompt; redaction |
| `oncall/workspace.py`, `oncall/runner.py`, `oncall/publish.py` | The worktree, the agent run, the publish decision |
| `mandate.md` | What the agent is told to do (the start of every prompt) |
| `agent-settings.json` | The agent's permissions, passed to the CLI with `--settings` |
| `pr-body.md` | The pull request body template |
| `demo/` | The demo fault (`fault.patch`, an inert text file) and the demo scripts |
| `tests/` | `make test-responder`: unit tests with a fake agent; no network, no CLI, no GitHub |
| `incidents/` | One folder per incident. **Gitignored**; it stays on the author's machine |

## Why it listens on 127.0.0.1 only

The responder starts a coding agent that edits this repository and, through the
responder, pushes a branch with the author's GitHub login. Anything that can
reach `POST /alerts` can make that happen. So it binds the loopback interface
only, and the port is the only thing that can be changed; there is no setting
for the address. It also checks a shared secret (next section). If Grafana's
container cannot reach a loopback-bound port on the host, that is reported on
#57; the responder is not rebound to `0.0.0.0`.

## The shared secret

The responder refuses to start without `RESPONDER_TOKEN` (at least 16
characters). Every `POST /alerts` must carry `Authorization: Bearer <the same
value>`; anything else is answered 401 before the body is read. The comparison
is constant-time (`hmac.compare_digest`). The value lives in your shell only,
never in a file:

```bash
export RESPONDER_TOKEN="$(openssl rand -hex 32)"
```

Export the same value in the shell that starts the telemetry stack, so that
Grafana's contact point (#57) sends it. The token is never written into an
incident folder, the prompt, the log or the agent's environment.

## Settings

All from the environment; every default is loopback or the temp directory.

| Variable | Default | What it sets |
|---|---|---|
| `RESPONDER_TOKEN` | none: required | The shared secret |
| `RESPONDER_PORT` | `8001` | The port on `127.0.0.1` |
| `LOKI_URL` | `http://127.0.0.1:3100` | Loki (#56), queried with `query_range` |
| `TEMPO_URL` | `http://127.0.0.1:3200` | Tempo (#56), search and trace API |
| `RESPONDER_SERVICE_NAME` | `tennis-prediction-game` | `service_name` in the log and trace queries |
| `RESPONDER_APP_CONTAINER` | found with `docker compose -f docker-compose.yml -f docker-compose.telemetry.yml ps -q app` in the main checkout | The container whose stderr holds the traceback |
| `RESPONDER_BASE_REF` | `origin/main` | The base of the `oncall/...` branch; the demo sets `demo/oncall-fault` |
| `RESPONDER_WORKTREE_DIR` | `<system temp>/tennis-oncall-worktrees` | Where the worktrees go; must be outside the repository |
| `RESPONDER_INCIDENTS_DIR` | `incident-response/incidents` | Where the incident folders go |
| `RESPONDER_AGENT_CMD` | see below | The agent command, one setting |
| `RESPONDER_AGENT_ENV_EXTRA` | empty | Names of extra variables the agent may see (space or comma separated) |
| `RESPONDER_TIMEOUT_MIN` | `20` | The run's time limit in minutes; then the agent's process group is killed |

The default agent command is Claude Code's print mode, every flag checked
against `claude --help` of version 2.1.303; the prompt goes on stdin:

```
claude -p --settings {settings} --add-dir {incident_dir}
  --setting-sources project,local
  --permission-mode dontAsk --permission-prompts none
  --output-format stream-json --verbose --no-session-persistence --strict-mcp-config
```

`{settings}` becomes this folder's `agent-settings.json`, `{incident_dir}` the
incident folder. `--setting-sources project,local` loads the project settings
(they wire the commit gate's pre-tool door) and leaves your user-level settings,
and any allow rules in them, out of the agent's run. `--permission-prompts none`
means nobody answers a prompt:
anything not allowed is denied. Not used, on purpose, and refused at start-up
if a custom command names them: `--bare` and `--safe-mode` (they switch hooks
off, and with them the commit gate's door), `--restricted` (it ignores the
project settings that wire that door), `--dangerously-skip-permissions`,
`--allow-dangerously-skip-permissions` and `bypassPermissions`.

At start the responder also checks `agent-settings.json`: it must exist, parse
as JSON and hold `permissions.allow` and `permissions.deny` as lists of rules.
Otherwise it refuses to start, with the reason and exit code 2. Claude Code's
print mode silently ignores a settings file that fails its own validation, so a
broken file must stop the responder before any agent runs.

The agent's environment is an allow-list: `PATH`, `HOME`, `USER`, `LOGNAME`,
`LANG`, `TERM`, `TMPDIR`, plus `UV_OFFLINE=1` (uv never downloads), plus the
names in `RESPONDER_AGENT_ENV_EXTRA`. If your commits are signed and the
signing needs a variable the list drops, add its name there; nothing about it
belongs in this repository.

## Prerequisites

- Docker with the compose plugin, `uv`, `python3`, `git`.
- `gh` logged in (`gh auth status`) with access to this repository; the
  responder uses it for `gh pr create`, and `git` with your login for the push.
- The coding agent CLI installed and logged in (`claude --version`).
- The commit gate enabled in the main checkout (`make hooks`). The agent's
  commits pass both doors of the gate. The pre-tool door runs
  `$CLAUDE_PROJECT_DIR/agent-hooks/claude-pre-tool.sh` and accepts a commit
  only when `core.hooksPath`, read with `git -C` in the script's own folder,
  resolves to that same folder. The headless CLI runs in the responder's
  worktree, which is its project dir, so `core.hooksPath` read there must
  resolve to the worktree's own `agent-hooks/`. That is why the responder
  creates the worktree with `git -C <main worktree> worktree add` (it inherits
  the relative `agent-hooks`), then checks it, and escalates without an agent
  otherwise. This is the expected behaviour, to be confirmed by the refusal
  check under *Author steps*. Your private pattern list, if your
  checkout has one, is linked into the worktree (a gitignored symlink, gone
  with the worktree), so the gate sees it; the agent's settings deny reading it.
- #56 (telemetry stack) and #57 (the alert rule and its webhook contact point)
  on the branch you run the stack from. The contact point calls
  `http://host.docker.internal:8001/alerts` with
  `Authorization: Bearer ${RESPONDER_TOKEN}`.
- The label `on-call-agent` exists on GitHub (Author steps).

## Checks that need no stack

```bash
make test-responder                     # unit tests, also part of make check
export RESPONDER_TOKEN="$(openssl rand -hex 32)"
echo "$RESPONDER_TOKEN"                 # to copy into the second shell
make responder                          # shell 1: stays in the foreground
```

In a second shell, export the same value first
(`export RESPONDER_TOKEN=<the value printed in shell 1>`), then send the
Homework 4 test notification. It answers 200 with `ignored: test notification`, and
afterwards there is no new incident folder, no worktree, no branch and no
agent process:

```bash
curl -sS -X POST http://127.0.0.1:8001/alerts \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $RESPONDER_TOKEN" \
  -d '{"alerts":[{"status":"firing","labels":{"alertname":"ResponderTest","test":"true"},"annotations":{"summary":"Test notification"}}]}'
```

A malformed body answers 400, a missing token 401, a non-JSON content type
415; none of them saves or starts anything. A firing payload
(`tests/fixtures/firing.json`) answers 202 with an incident id; without the
telemetry stack, Loki is unreachable and the run escalates at once, before any
worktree or agent.

## What a run does

| Answer | When | What happens |
|---|---|---|
| 415 | Content type is not `application/json` | Nothing |
| 401 | Missing or wrong bearer token | Nothing |
| 400 | Body is not JSON, or has no `alerts` list of objects | Nothing |
| 200 `ignored` | A test notification (label `test` = `"true"`, or alertname `ResponderTest` or `TestAlert`); only `resolved` alerts; only `DatasourceError` / `DatasourceNoData` (or a `grafana_state_reason` label) | Nothing |
| 200 `busy` | A run is in progress | Nothing; logged |
| 200 `duplicate` | The incident (`fingerprint` + `startsAt`) already has a folder | Nothing |
| 202 `accepted` | Otherwise | The run starts in the background |

The run, in order:

1. The incident folder `incidents/<UTC time>-<alert name>/` gets the raw body
   (`alert.json`; never a request header) and `incident.json` (endpoint from the
   route label, time window from `startsAt` and the `window` annotation, plus a
   minute either side).
2. **Loki**: the window's `unhandled exception` records and 5xx `request
   completed` records, allow-listed fields only (`logs.json`). **Unreachable
   means the outcome is `escalated`, before any worktree or agent.**
3. **Tempo**: the failing traces, by the log records' trace ids and a TraceQL
   search, summarised to allow-listed span fields (`traces.json`). Unreachable
   is noted in `context.json`; the run goes on.
4. **The app container's stderr** for the window (decision A, 22 Oct):
   telemetry carries the exception type only, so the traceback comes from
   `docker logs --since --until` of the overlay's app container, stderr only
   (`app-stderr.txt`, `tracebacks.txt`). Unavailable is noted; the run goes on.
5. `context.json` says what was reachable; `prompt.txt` is the exact prompt:
   `mandate.md`, then the allow-listed facts, with all alert and log text
   between `<<<BEGIN UNTRUSTED INCIDENT DATA ...>>>` and `<<<END ...>>>`
   markers. Every file in the folder, and the prompt, is redacted (session
   cookie values, e-mail addresses, bearer tokens, the responder's token).
6. A git worktree outside the repository, created with
   `git -C <main worktree> worktree add` on a new branch
   `oncall/<alert-slug>-<UTC timestamp>` from `RESPONDER_BASE_REF` (`--no-track`,
   from the base's commit id, so git records no upstream). The responder checks
   that the worktree's `core.hooksPath` resolves to its own `agent-hooks/` (what
   the pre-tool door will require, see *Prerequisites*), links the private
   pattern list, and runs `uv sync` in `backend/`.
7. The agent runs in the worktree, the incident folder added with `--add-dir`
   and made read-only for the run, with the allow-listed environment and the
   time limit. Its whole output is saved (`agent-output.jsonl`,
   `agent-stderr.txt`); `agent-command.json` records argv, cwd and the names of
   the variables it got.
8. The responder decides from the repository, not from the agent's
   `RESULT:` line. It publishes only if the agent said `RESULT: fixed` **and**
   the branch has at least one commit beyond the base, the diff adds or
   changes a test under `backend/tests/`, touches no denied path
   (`.github/`, `agent-hooks/`, `.claude/`, `incident-response/`,
   `openapi.yaml`, `Dockerfile`, `docker-compose*.yml`, `backend/pyproject.toml`,
   `backend/uv.lock`), nothing is left uncommitted, `core.hooksPath` is the
   same as before the run, and the responder's own `uv run pytest` in the
   worktree is green. Then it pushes only that branch with an explicit refspec
   (`git push origin refs/heads/oncall/X:refs/heads/oncall/X`) and opens the pull
   request (`gh pr create --base <base> --head oncall/X --label on-call-agent
   --body-file <pr-body.md rendered>`).
9. The outcome goes to `result.json` and is printed in a banner on the
   responder's console: `published`, `escalated`, `agent_failed`, `timed_out`
   or `publish_failed`. Nothing is pushed unless it is `published` (or
   `publish_failed` after the push itself succeeded). `hooks-path.txt` holds
   `core.hooksPath` of the main checkout and the worktree, before and after.

The worktree stays after the run, for inspection; `make demo-reset` removes it.

Permissions, credentials and residual risks: [`docs/permissions.md`](../docs/permissions.md),
*The on-call agent*.

## The demo (author)

The deliberate bug is never on `main`. `demo/fault.patch` is applied on a local
branch, `demo/oncall-fault`, and the stack is built from that branch. Run from
the main checkout, in this order. Port 8000 may be taken on your machine; the
commands use `APP_PORT=8080`, change it to any free port.

1. **Demo branch.** On `main`, clean tree: `make demo-fault` (creates
   `demo/oncall-fault`, applies the patch, commits it, so the commit gate
   runs), then `git push origin demo/oncall-fault` (the pull request's base must
   exist on GitHub). CI runs on that push and is green: the existing tests do
   not catch the fault.
2. **Token.** `export RESPONDER_TOKEN="$(openssl rand -hex 32)"` in two shells.
3. **Stack** (shell 1, on `demo/oncall-fault`): `APP_PORT=8080 make telemetry-up`.
   Grafana on `http://localhost:3000`; the alert rule is **Normal**.
4. **Responder** (shell 2): `git fetch origin`, then
   `RESPONDER_BASE_REF=demo/oncall-fault make responder`.
5. **Contact point test.** In Grafana, *Alerting > Contact points*, the
   responder's contact point, *Test*. The responder logs
   `200 ignored: test notification`; nothing else happens.
6. **Fault.** `make demo-trigger BASE_URL=http://127.0.0.1:8080`: every answer is
   `500`.
7. **Alert.** In Grafana the rule goes from Normal to **Firing** (within about
   90 seconds).
8. **Run.** The responder logs `202 accepted`, the sources it reached, the
   worktree and the agent's start. The agent reads the folder, writes a test
   that fails, fixes the code, sees the test and the backend suite pass, and
   commits. The responder checks, pushes `oncall/...` and opens the pull
   request; the banner prints `ON-CALL RESULT: PUBLISHED` and the link.
9. **CI** runs on the pushed `oncall/...` branch (the `push` trigger covers every
   branch). Note the run's link.
10. **Review** the pull request; its base is `demo/oncall-fault`, so the diff is
    the fix and its test only. Merge it on GitHub, then in shell 1:
    `git pull --ff-only origin demo/oncall-fault`.
11. **Rebuild the app only:**
    `APP_PORT=8080 docker compose -f docker-compose.yml -f docker-compose.telemetry.yml up -d --build --no-deps app`.
12. **Fixed.** `make demo-trigger BASE_URL=http://127.0.0.1:8080`: every answer is
    `200`. About two minutes after the last 500 the rule is **Normal** again;
    the responder logs the resolved notification as ignored.
13. **Second run, escalating** (the infrastructure fault of #57): wait until
    the rule is Normal, then
    `make demo-trigger BASE_URL=http://127.0.0.1:8080 WAIT=1`; when it pauses
    after signing in, stop Postgres
    (`docker compose -f docker-compose.yml -f docker-compose.telemetry.yml stop postgres`)
    and press Enter. The answers are `500`, the alert fires again (a new
    `startsAt`, so a new incident), the agent finds `OperationalError` and ends
    `RESULT: escalate - ...`; no branch is pushed, no pull request. Start
    Postgres again (`... start postgres`).
14. **Cleanup** (below).

## Cleanup

Locally: `make demo-reset` (refuses on a dirty tree). It switches to `main`,
removes every worktree on an `oncall/` branch, deletes the local `oncall/*`
branches and `demo/oncall-fault`. Then `make telemetry-down` and unset
`RESPONDER_TOKEN`.

On GitHub, by hand (not scripted):

```bash
gh pr list --label on-call-agent --state all      # the responder's pull requests
gh pr close <number> --delete-branch              # one that was not merged
git push origin --delete oncall/<name>            # a pushed oncall branch that is left
git push origin --delete demo/oncall-fault        # the demo base, last
```

## Author steps

The checks marked **(author)** in #58, and what needs the live stack, the CLI
login or GitHub:

- [ ] Create the label once:
  `gh label create on-call-agent --description "Opened by the on-call responder"`.
- [ ] Capture the real *Test* button payload and replace the provisional
  fixture `tests/fixtures/grafana-test-button.json` (trim it to the fields it
  has; keep `alertname` and the labels). With the responder stopped, run a
  one-shot listener on the same port, press *Test*, then `make test-responder`:
  ```bash
  python3 -c 'import http.server as s
  class H(s.BaseHTTPRequestHandler):
      def do_POST(self):
          open("grafana-test-button.json", "wb").write(self.rfile.read(int(self.headers["Content-Length"])))
          self.send_response(200); self.end_headers()
  s.HTTPServer(("127.0.0.1", 8001), H).handle_request()'
  ```
  Also compare #57's recorded *Error* (DatasourceError) body with
  `tests/fixtures/datasource-error.json`.
- [ ] **Refusal check (author).** In a responder worktree (or any scratch
  worktree made from the main checkout), run the CLI with the shipped settings
  and ask it to run one allowed command and then push; the output must show
  `git status` run and the push denied (the first proves the settings file was
  loaded: in print mode a settings file that fails validation is silently
  ignored):
  ```bash
  echo 'Run exactly these two shell commands, one after the other, and show their output: git status, then git push --dry-run origin HEAD' \
    | claude -p --settings "<main checkout>/incident-response/agent-settings.json" \
        --setting-sources project,local \
        --permission-mode dontAsk --permission-prompts none \
        --output-format stream-json --verbose --no-session-persistence --strict-mcp-config \
    | tee refusal.jsonl
  ```
  The final `result` event lists the call under `permission_denials`. Record it
  under *Recorded run*. This also confirms the flags and the rule syntax of
  `agent-settings.json` on the installed CLI.
- [ ] **Watch the demo end to end (author)**, steps 1 to 12 above, and comment
  on #58 with the date and "watched end to end".
- [ ] The second, escalating run (step 13).
- [ ] Fill in *Recorded run* below, sanitised, and let the commit gate run on it.

## Recorded run

Not yet recorded. Filled in by the author after the live demo, sanitised: no
hostnames, addresses, credentials or personal paths; loopback URLs only.

### The alert

<!-- trimmed payload: alertname, labels, annotations, startsAt -->

### The agent's final message

<!-- including its RESULT: line -->

### Denied actions

<!-- permission_denials from result.json, or "none" -->

### The pull request and CI

<!-- PR link; CI run link on the oncall/... branch -->

### Red, then green

<!-- the new test failing before the fix, passing after -->

### Before and after: make demo-trigger

<!-- 500s before, 200s after -->

### core.hooksPath before and after

<!-- from hooks-path.txt -->

### Refusal check

<!-- the denied git push --dry-run origin HEAD -->

### Second run: escalated

<!-- the Postgres-stopped alert: RESULT: escalate - ..., no branch pushed, no pull request -->
