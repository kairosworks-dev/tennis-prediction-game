#!/usr/bin/env bash
# Claude Code PreToolUse adapter. Receives the tool call as JSON on stdin.
# For a `git commit`, refuses --no-verify (the way to skip git's own hook) and
# runs the same gate, so the agent sees the reason before the commit is attempted.
# Exit 2 = block the tool call and show stderr to the agent; exit 0 = continue.
cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)
case "$cmd" in
  *"git commit"*|*"git "*" commit"*) ;;
  *) exit 0;;
esac
case "$cmd" in *--no-verify*|*" -n "*)
  echo 'commit-gate: --no-verify is not allowed in this repository.' >&2; exit 2;;
esac
if ! "$(dirname "$0")/commit-gate.sh"; then exit 2; fi
exit 0
