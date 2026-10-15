# Agent hooks

One guardrail, two doors.

| File | Role |
|---|---|
| `commit-gate.sh` | The gate. Scans the **added** lines of the staged diff for secrets and private infrastructure names; blocks the commit on a hit and prints file and pattern name, never the line |
| `pre-commit` | Git's door. Active after `make hooks` (`git config core.hooksPath agent-hooks`), for every commit by anyone, agent or human |
| `claude-pre-tool.sh` | The coding agent's door (Claude Code `PreToolUse`, wired in `.claude/settings.json`). Runs the gate before the agent's `git commit` and refuses `--no-verify`. Other agents use git's door |
| `private-patterns.example.txt` | Template for the gitignored `private-patterns.txt`: the author's own names, never committed |

What it does not catch: personal prose without a pattern. That is the author's review at pull-request time. Details and the roles' permissions: `docs/permissions.md`.
