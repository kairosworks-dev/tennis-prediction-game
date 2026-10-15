#!/usr/bin/env bash
# Claude Code PreToolUse adapter. Receives the tool call as JSON on stdin.
# Flag policy for `git commit` (no hook-skipping flags, no hooksPath override)
# plus a check that git's own pre-commit hook is enabled (make hooks). It does
# not scan content: that is git's pre-commit hook (commit-gate.sh).
# Exit 2 = block the tool call and show stderr to the agent; exit 0 = continue.
# Any failure of the checker itself also blocks (fail closed).
python3 "$(dirname "$0")/pre_tool_check.py"
rc=$?
[ "$rc" -eq 0 ] && exit 0
[ "$rc" -ne 2 ] && echo 'commit-gate: the pre-tool check failed to run; refusing.' >&2
exit 2
