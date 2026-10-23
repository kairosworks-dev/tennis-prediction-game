# Permissions and security note

What the agents in this repository may do, what stops them, and what remains a human decision. Part of the agent extension pack (`docs/agent-extension-pack.md`).

## Who may change what

| Role | Reads | Writes | Closes issues | Merges |
|---|---|---|---|---|
| Orchestrator (main session) | everything | nothing in the tree; opens PRs | after QA `PASS`, by merging | after the author's go |
| PM | issue, spec, status, process | the issue body and labels, via `gh`; follow-up issues | no | no |
| Engineer | everything | files named in the issue's Constraints, on the issue branch | no | no |
| QA | everything | an issue comment only | no | no |
| API reviewer | everything | nothing; reports only | no | no |
| On-call agent (#58; headless, started by the responder) | its worktree and the incident folder, minus `incident-response/demo/` and the private pattern list | files in its own worktree outside the denied paths; commits on its `oncall/...` branch; never pushes, never opens the pull request (the responder does, after its own checks) | no | no |
| Author | everything | everything; pushes `main`; the `by-hand` issues | yes | yes |

In Claude Code the read-only roles have no file-editing tools (the `tools:` line in `agent-capabilities/subagents/`). Other coding agents enforce the same restriction through the role text, which says it in words.

## The commit gate

Two doors, two jobs.

- **Content gate: git's `pre-commit` hook** (`agent-hooks/commit-gate.sh`, enabled by `make hooks`). Every commit, by any agent or by the author, passes it. It is the only place content is scanned, because it sees exactly what is committed. It scans the **added** lines of the staged diff for:

  - files that are never committed: environment files other than the example, private key files
  - generic patterns: IPv4 addresses outside a short allowlist, 1Password secret references, private key blocks, home-directory paths, GitHub and AWS tokens, inline secret assignments
  - the author's **private pattern list**, a gitignored file next to the script, holding the names of his server, backup storage, private notes and similar. The repository shows that the list exists, never its contents.

  IPv4 policy: private infrastructure detail stays out of the public repository, so RFC 1918 private ranges are blocked like public addresses. Allowed are loopback, `0.0.0.0`, the `255.255.255.x` netmask forms and the documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`); examples use those. There is no version-number exemption, so an in-range four-part version still matches.

- **Flag policy: Claude Code's pre-tool hook** (`agent-hooks/claude-pre-tool.sh`). It inspects the arguments of a `git commit` only and refuses `--no-verify` (and abbreviations), `-n`, `core.hooksPath` overrides, and `GIT_CONFIG_*`/`GIT_DIR` assignments or a `git config core.hooksPath` write in the same command. It follows `bash -c`/`eval` strings (up to 3 levels), `$(...)`, backticks, wrapper words (`env`, `sudo`, `xargs`, ...) and git aliases that resolve to `commit`. It also refuses `git commit` unless `core.hooksPath` points at this checkout's `agent-hooks`. It does not scan content.

Without `make hooks` the content gate is off, and the pre-tool door then refuses the agent's `git commit` until it is run. Remaining limits: the pre-tool door is a guardrail against skipping the hook by accident, not a security boundary, and git's pre-commit hook is the backstop. Accepted, not detected: variable or built-string indirection (`$GIT commit`, `eval "$cmd"`), pipes into a shell (`... | sh`), interpreters running git, other ways to disable the hook (deleting or `chmod`-ing it, editing `.git/config`), `git -C <other repo>` / `--git-dir`, shell aliases, commit-creating verbs other than `commit`; and the version-number limit above. `agent-hooks/test-hooks.sh`, run by `make check`, covers both doors.

On a hit the gate prints the file and the pattern name, not the line, and the commit does not happen.

## What no gate covers

- Personal or infrastructure detail written as ordinary prose. The author reviews every pull request for it.
- Secrets at runtime. They live in the deployment platform's environment store and in the author's password manager; the repository holds names of variables, never values.
- The `by-hand` issues. Agents do not act on the server; the author does, and records sanitised evidence in `ops/`.

## Tokens and scopes

| Credential | Scope | Where it lives |
|---|---|---|
| Deploy token for the pipeline | deploy only, one application | repository secret on GitHub |
| `gh` CLI used by the roles | the author's own login, issues and PRs on this repository | the author's machine, not the repo |
| Database and session secrets | the running app | the platform's environment store |
| The coding agent CLI's own login | the on-call agent's model calls; no API key | the author's machine, not the repo |
| `gh` and `git` as the author, used by the responder (#58) | push one `oncall/...` branch, open one pull request | the author's machine, not the repo |
| `RESPONDER_TOKEN` | the shared secret between Grafana's contact point and the responder | the author's shell, for one demo; never in a file |

Issue #15 (MCP server) and #16 (custom agent) add their own rows here when they land.

## The on-call agent (#58)

A local demo on the author's machine (D20). When the 5xx alert fires, the
responder in `incident-response/` (ordinary code, standard-library Python) saves
the evidence, creates a git worktree outside the repository on a new
`oncall/...` branch, and starts the author's logged-in coding agent headless in
it. The agent fixes and commits; the responder decides from the repository
whether to publish, and publishes itself. Full description:
[`incident-response/README.md`](../incident-response/README.md).

**How it is started.** `claude -p --settings incident-response/agent-settings.json
--add-dir <incident folder> --setting-sources project,local
--permission-mode dontAsk --permission-prompts none
--output-format stream-json --verbose --no-session-persistence
--strict-mcp-config`, prompt on stdin, working directory the worktree, an
allow-listed environment (`PATH`, `HOME`, `USER`, `LOGNAME`, `LANG`, `TERM`,
`TMPDIR`, `UV_OFFLINE=1`, plus names the author adds in
`RESPONDER_AGENT_ENV_EXTRA`; never `RESPONDER_TOKEN`), a time limit (20
minutes, then the process group is killed). `dontAsk` with `--permission-prompts
none`: whatever is not allowed is denied, nobody is asked. The responder
refuses to start with `--bare`, `--safe-mode`, `--restricted` or a permission
bypass in the command, because each switches the commit gate's door or the
permission checks off. It also refuses to start when `agent-settings.json` is
missing, is not valid JSON or lacks the `permissions.allow` and
`permissions.deny` lists: in print mode the CLI would silently ignore a broken
settings file.

**The settings file** (`incident-response/agent-settings.json`), line by line in groups:

| Rules | Effect |
|---|---|
| `defaultMode: dontAsk`, `disableBypassPermissionsMode: disable` | Anything not allowed below is denied; bypass mode cannot be turned on |
| allow `Read(./**)`, `Edit(./**)` | Read and edit files inside the worktree (`./` is the working directory) |
| allow `Bash(git status ...)`, `Bash(git diff)`, `--stat`, `--cached`/`--staged` (with `--stat` or `-- <path>`), `Bash(git diff -- *)` | Look at its own changes, and nothing older |
| allow `Bash(git add *)`, `Bash(git commit *)` | Commit on its branch; the commit passes git's `pre-commit` and the pre-tool door, both wired as for any agent (the door also in this file's `hooks`). The door, run from `<worktree>/agent-hooks`, accepts a commit only when `core.hooksPath` read there resolves to that folder; the responder creates the worktree from the main checkout so it does, checks it, and escalates otherwise (expected; confirmed by the author's refusal check) |
| allow `Bash(make test-backend)`, `Bash(uv run --directory backend pytest ...)`, `Bash(uv run --directory backend ruff ...)`, `Bash(uv run pytest ...)`, `Bash(uv run ruff ...)` | Run the backend tests and the linter |
| deny `Bash(git push ...)` | No push; the responder pushes after its checks |
| deny `Bash(git config ...)`, `Bash(git -c *)`, `Bash(git -C *)`, `--git-dir`, `--work-tree`, `--config-env` | No configuration change, no pointing git at another repository |
| deny `Bash(git log ...)`, `show`, `blame`, `reflog`, `cat-file`, `rev-list`, `grep`, `shortlog`, `whatchanged`, `ls-tree`, `archive`, `format-patch`, `restore`, a `git diff` naming `HEAD`, `..`, `~`, `^` or `@{` | No history: the fix comes from the evidence and the code as it is (anti-cheat, 17 Oct) |
| deny `Bash(git checkout ...)`, `switch`, `merge`, `rebase`, `reset`, `branch`, `worktree`, `stash`, `cherry-pick`, `revert`, `apply`, `am`, `tag`, `fetch`, `pull`, `remote`, `clone`, `update-ref`, `symbolic-ref`, `notes`, `clean` | No branch or ref changes, nothing from elsewhere; the stash is shared by every worktree |
| deny `Bash(gh ...)` | No GitHub |
| deny `curl`, `wget`, `nc`, `ncat`, `socat`, `telnet`, `ftp`, `rsync`, `ssh`, `scp`, `sftp`, `WebFetch`, `WebSearch` | No network clients |
| deny `docker`, `docker-compose`, `podman` | No containers |
| deny `rm -r`, `rm -R`, `rm -fr`, `rm -fR` (and with the flag later), `sudo` | No recursive deletion, no privilege |
| deny `uv add`, `uv remove`, `uv lock`, `uv sync`, `uv pip`, `pip`, `pip3`, `npm` | No dependency changes (a fix that needs one is escalated) |
| deny `Edit(./.github/**)`, `./agent-hooks/**`, `./.claude/**`, `./incident-response/**`, `./openapi.yaml`, `./Dockerfile`, `./docker-compose*.yml`, `./backend/pyproject.toml`, `./backend/uv.lock`, `./.git` | Not the pipeline, the gate, the agent configuration, the responder, the contract, the images or the dependencies. Edit rules cover every file-writing tool |
| deny `Read(./incident-response/demo/**)`, `Read(./agent-hooks/private-patterns.txt)`, `Read(~/.ssh/**)`, `Read(~/.config/gh/**)`, `Read(~/.gitconfig)`, `Read(~/.config/git/**)` | Not the demo fault (anti-cheat), not the author's private patterns, not credentials |

The deny list is mostly a second wall: under `dontAsk` anything not allowed is
already refused. The author's user-level settings are not loaded
(`--setting-sources project,local`); should another source ever allow more, a
deny rule wins over an allow rule from any source. The responder enforces the important lines again in ordinary code: it
publishes only a branch whose diff touches none of the denied paths, adds or
changes a test, has nothing uncommitted, and passes its own `uv run pytest`; it
pushes only that branch with an explicit refspec and never with `--force`; and
`core.hooksPath` must read the same before and after the run.

**What it uses.** The CLI's own login on the author's machine (no API key);
the author's `gh` and `git` login, used by the responder alone, for the push of
one `oncall/...` branch and one `gh pr create`. The agent never sees a token.

**Residual risks, stated plainly.**

- The responder's only guard besides the loopback binding is the shared secret
  `RESPONDER_TOKEN`. A leaked token, or any local process that has it, can start
  a run (which still ends in a reviewed pull request at most).
- **Known limit.** The agent may edit tests and run pytest, so code it writes
  runs outside the deny list: the list limits the commands the agent types,
  not the code it runs through the test runner (also on the responder's own
  re-run, which uses the agent's allow-listed environment). An OS-level
  sandbox is a follow-up; today it would block commit signing. Until then the
  bounds are the environment allow-list, the worktree, the responder's checks
  and the author's review.
- A prompt-injection attempt in alert or log text is bounded by this
  configuration and by the responder's checks, not by the prompt. The prompt
  marks that text as data, but that is advice to the model, not enforcement.
- The app container's stderr traceback goes into the incident folder and the
  prompt (decision A). An exception message can carry request data. The
  responder redacts session cookie values, e-mail addresses and bearer tokens,
  and this is accepted because the demo runs on demo data only.
- `Read` deny rules apply to the search tools on a best-effort basis, so a
  search across the worktree could still show lines of `incident-response/demo/`.
  The saved transcript (`agent-output.jsonl`) shows every tool call, which is
  how a run is checked for it.
- The exact matching of these rules is the CLI's. They were checked against
  `claude --help` and the documented rule syntax; the author's refusal check
  (a `git push --dry-run` the CLI must deny) confirms them on the installed
  version.
