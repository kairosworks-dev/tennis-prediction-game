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

Every commit, by any agent or by the author, passes `agent-hooks/commit-gate.sh` (git `pre-commit`, enabled by `make hooks`). Claude Code additionally runs it before executing a `git commit` and refuses the flag that would skip git's hook. The gate scans the **added** lines of the staged diff for:

- files that are never committed: environment files other than the example, private key files
- generic patterns: public IP addresses, 1Password secret references, private key blocks, home-directory paths, GitHub and AWS tokens, inline secret assignments
- the author's **private pattern list**, a gitignored file next to the script, holding the names of his server, backup storage, private notes and similar. The repository shows that the list exists, never its contents.

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
