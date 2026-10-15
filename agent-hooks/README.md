# Agent hooks

One guardrail, two doors, two jobs.

| File | Role |
|---|---|
| `commit-gate.sh` | The **content gate**. Scans the **added** lines of the staged diff for secrets and private infrastructure names; blocks the commit on a hit and prints file and pattern name, never the line. It is the only place content is scanned, because only git's door sees exactly what is committed |
| `ipv4_scan.py` | The IPv4 check used by `commit-gate.sh` (python3 standard library) |
| `pre-commit` | Git's door. Active after `make hooks` (`git config core.hooksPath agent-hooks`), for every commit by anyone, agent or human |
| `claude-pre-tool.sh`, `pre_tool_check.py` | The coding agent's door (Claude Code `PreToolUse`, wired in `.claude/settings.json`). **Flag policy plus a hooks-enabled check; it never scans content.** Other agents use git's door |
| `test-hooks.sh` | Tests for both doors; run by `make check`. Works in a fresh clone, uses a throwaway repository, never reads `private-patterns.txt` |
| `private-patterns.example.txt` | Template for the gitignored `private-patterns.txt`: the author's own names, never committed |

## The pre-tool door

A guardrail against the agent skipping git's hook by accident, **not a security boundary**. Git's own `pre-commit` hook is the backstop, and it is the only thing that scans content.

The command is split into segments on `&&`, `||`, `;`, `|`, `&`, unquoted newlines, unquoted `$(...)` and backticks, parentheses and braces (python3 `shlex`). For each segment the checker:

1. skips leading `VAR=value` assignments, shell keywords (`{`, `!`, `then`, ...) and a fixed list of wrapper words with their options: `env`, `command`, `builtin`, `exec`, `sudo`, `nohup`, `time`, `nice`, `setsid`, `xargs`. It looks at the first word after those, not at any `git` token anywhere;
2. for `bash`/`sh`/`zsh`/`dash`/`ksh` with a `-c` flag (also `-lc`), and for `eval` with literal arguments, **recurses** into the string with the same rules, up to 3 levels; deeper nesting is refused with a stated reason;
3. for `git`, skips global options and takes the verb. A verb that is `commit`, or an alias that resolves to `commit` (defined by `git -c alias.x=...`, by an earlier `git config alias.x ...` in the same command, or in the repository's git configuration; alias arguments such as `commit -n` count), has its arguments inspected. Shell aliases (`!...`) are not followed.

Only the arguments of a commit are inspected, and option values (`-m`, `-F`, `-C`, `-c`, `--author`, `--date` and the like) are never read as flags, so prose in a commit message cannot trip it. It refuses:

- `--no-verify` and its unambiguous abbreviations, and `-n` alone or inside a short-flag group (`-nm x`, `-an`)
- `git -c core.hooksPath=...` and `git --config-env=core.hooksPath=...`
- in a command that contains a commit: an assignment (inline, after `env`, or after `export`) of `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_*`, `GIT_CONFIG_VALUE_*`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_SYSTEM` or `GIT_DIR`, whatever the key; and a `git config` that sets or unsets `core.hooksPath` (reading it is fine)
- a command that mentions `git` but cannot be parsed
- any `git commit` when `core.hooksPath` does not resolve to this checkout's `agent-hooks` directory. **Without `make hooks` the content gate is off, so the pre-tool door refuses `git commit`; run `make hooks`.**

## IPv4 policy

Private infrastructure detail stays out of the public repository, so RFC 1918 addresses (10/8, 172.16/12, 192.168/16) are **blocked** like any public address. Allowed: loopback `127.0.0.0/8`, `0.0.0.0`, the `255.255.255.x` netmask forms and the documentation ranges `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`. Use the documentation ranges in examples. A match needs four octets of 0-255 not adjacent to another digit or `.digit`.

## Remaining limits

- **Version numbers.** There is no exemption: an in-range four-part version such as `1.2.3.4` still matches and is blocked. Reword it or write it in a form that is not four dotted numbers.
- **Accepted limits of the pre-tool door** (it is a guardrail, not a security boundary; git's pre-commit hook is the backstop): variable or built-string indirection (`$GIT commit`, `eval "$cmd"`, command substitution inside double quotes); pipes into a shell (`... | sh`) and heredocs fed to a shell; interpreters running git (`python3 -c ...`); other ways to disable the hook (deleting or `chmod`-ing it, editing `.git/config`); `git -C <other repo>` and `--git-dir`, which are not judged against the target repository's hooks; shell aliases (`!...`); and commit-creating verbs other than `commit` (`merge`, `cherry-pick`, `revert`, `rebase`, `am`).
- Personal prose without a pattern. That is the author's review at pull-request time.

Details and the roles' permissions: `docs/permissions.md`.
