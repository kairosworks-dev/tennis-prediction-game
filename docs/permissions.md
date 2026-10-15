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

Issue #15 (MCP server) and #16 (custom agent) add their own rows here when they land.
