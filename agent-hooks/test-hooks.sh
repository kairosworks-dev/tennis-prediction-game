#!/usr/bin/env bash
# Tests for the commit gate: the pre-tool flag policy (claude-pre-tool.sh) and
# the content gate (commit-gate.sh). Plain bash, no dependency beyond python3.
#
# Works in a fresh clone: `make hooks` need not have been run and
# private-patterns.txt need not exist. The hook under test is pointed at this
# repository's agent-hooks directory through GIT_CONFIG_COUNT. Content cases run
# in a throwaway git repository; the real index is never touched, and the
# private pattern list is never read (the gate runs from a copy without it).
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hook="$here/claude-pre-tool.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fails=0 total=0

report() { # name, ok
  total=$((total + 1))
  if [ "$2" = 1 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fails=$((fails + 1)); fi
}

# run_pre <hooksPath value> <command> -> exit code of the pre-tool hook
run_pre() {
  local json
  json=$(CMD="$2" python3 -c 'import json,os; print(json.dumps({"tool_input":{"command":os.environ["CMD"]}}))')
  printf '%s' "$json" \
    | GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$1" "$hook" >/dev/null 2>"$tmp/err"
}

allow()  { run_pre "$here" "$1"; [ $? -eq 0 ] && report "allow   $1" 1 || report "allow   $1" 0; }
refuse() {
  run_pre "$here" "$1"; local rc=$?
  [ $rc -eq 2 ] && [ -s "$tmp/err" ] && report "refuse  $1" 1 || report "refuse  $1" 0
}
refuse_naming() { # command, token that the message must name verbatim
  run_pre "$here" "$1"; local rc=$?
  if [ $rc -eq 2 ] && grep -qF -- "$2" "$tmp/err"; then report "names   $2  in  $1" 1; else report "names   $2  in  $1" 0; fi
}

echo "== pre-tool: original findings"
allow  "sed -n 150,160p README.md && git commit -a -m 'x'"
allow  "git commit -m 'docs: mention the -n flag'"
allow  "git commit -m 'docs: explain why --no-verify is refused'"
refuse "git commit -m x -n"
refuse "git commit -nm x"
refuse "git -c core.hooksPath=/dev/null commit -m x"
refuse "git add . && git commit -nm x"

echo "== pre-tool: option values are not flags"
allow  "git commit -m -n"
allow  "git commit -mn"
allow  'git commit -m "x" --author=n'
allow  "git commit --author n -m x"
allow  "git commit -F -n"
allow  "git commit -m x -- -n"
allow  "git commit --message --no-verify"
allow  $'git commit -m "$(cat <<\'EOF\'\nfix: stuff && more\n\nProse about -n and --no-verify and && chains.\nEOF\n)"'
allow  "git status && ls -n"
allow  "git log -n 5"
allow  "echo git commit -nm x"

echo "== pre-tool: refused forms"
refuse_naming "git commit --no-verify -m x" "--no-verify"
refuse_naming "git commit --no-verif -m x" "--no-verif"
refuse_naming "git commit --no-ver -m x" "--no-ver"
refuse_naming "git commit --no-v -m x" "--no-v"
refuse_naming "git commit -nm x" "-nm"
refuse_naming "git commit -an" "-an"
refuse_naming "git commit -anm x" "-anm"
refuse_naming "git commit -ann" "-ann"
refuse_naming "git commit -n" "-n"
refuse_naming "git commit -m x -n" "-n"
refuse "git commit -m x; git commit --no-verify"
refuse "git commit -m x || git commit -n"
refuse "ls | git commit -n"
refuse $'echo hi\ngit commit -n -m x'
refuse "git -C /somewhere commit -nm x"
refuse "git --no-pager commit -n"
refuse "git -c core.hooksPath=/dev/null -c user.name=a commit -m x"
refuse "git -c user.name=a -c core.hookspath=/x commit -m x"
refuse "git -ccore.hooksPath=/x commit -m x"
refuse_naming "git -c core.hooksPath=/x commit -m x" "core.hooksPath=/x"
refuse "git --config-env=core.hooksPath=SOMEVAR commit -m x"
refuse "git --config-env core.hooksPath=SOMEVAR commit -m x"
allow  "git -c user.name=a commit -m x"
allow  "git -C /somewhere commit -m x"
allow  "git --no-pager commit -m x"

echo "== pre-tool: unparseable commands"
refuse_naming "git commit -m 'unbalanced" "parse"
allow  "echo 'unbalanced and nothing to do with it"
allow  "ls -n"

echo "== pre-tool: hooks-enabled check"
for v in "" "/nonexistent/hooks" "$tmp"; do
  run_pre "$v" "git commit -m x"; rc=$?
  if [ $rc -eq 2 ] && grep -q "make hooks" "$tmp/err"; then report "refuse  git commit, core.hooksPath='${v:+set to a wrong path}${v:-unset}'" 1
  else report "refuse  git commit, core.hooksPath='${v:+set to a wrong path}${v:-unset}'" 0; fi
done
run_pre "" "git status && ls"; [ $? -eq 0 ] && report "allow   non-commit command when hooks are off" 1 || report "allow   non-commit command when hooks are off" 0

echo "== pre-tool: relative hooksPath and a linked worktree"
wt="$tmp/wt"
mkdir -p "$tmp/main/agent-hooks"
cp "$here/claude-pre-tool.sh" "$here/pre_tool_check.py" "$tmp/main/agent-hooks/"
(cd "$tmp/main" && git init -q && git add -A \
  && git -c user.name=t -c user.email=t@example.com -c core.hooksPath=/dev/null commit -q -m init \
  && git worktree add -q "$wt") >/dev/null 2>&1
json='{"tool_input":{"command":"git commit -m x"}}'
printf '%s' "$json" | (cd "$wt" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=agent-hooks "$wt/agent-hooks/claude-pre-tool.sh") >/dev/null 2>&1
[ $? -eq 0 ] && report "allow   linked worktree, relative core.hooksPath=agent-hooks" 1 || report "allow   linked worktree, relative core.hooksPath=agent-hooks" 0
printf '%s' "$json" | (cd "$wt" && GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0="$tmp/main/agent-hooks" "$wt/agent-hooks/claude-pre-tool.sh") >/dev/null 2>&1
[ $? -eq 2 ] && report "refuse  linked worktree, hooksPath pointing at another checkout" 1 || report "refuse  linked worktree, hooksPath pointing at another checkout" 0

echo "== content gate (throwaway repository)"
gate="$tmp/gatecopy"
mkdir -p "$gate"
cp "$here/commit-gate.sh" "$here/ipv4_scan.py" "$gate/"   # deliberately without private-patterns.txt
repo="$tmp/repo"
mkdir -p "$repo" && (cd "$repo" && git init -q)

# content_case <expect: allow|block> <label> <added line>
content_case() {
  local expect="$1" label="$2" line="$3" rc
  (cd "$repo" && git reset -q 2>/dev/null; printf '%s\n' "$line" > sample.txt && git add sample.txt) >/dev/null 2>&1
  (cd "$repo" && "$gate/commit-gate.sh") >/dev/null 2>&1; rc=$?
  if [ "$expect" = allow ] && [ $rc -eq 0 ]; then report "gate allow  $label" 1
  elif [ "$expect" = block ] && [ $rc -ne 0 ]; then report "gate block  $label" 1
  else report "gate $expect  $label (exit $rc)" 0; fi
}
content_case allow "loopback 127.0.0.1"          "host 127.0.0.1"
content_case allow "loopback 127.8.9.10"         "host 127.8.9.10"
content_case allow "unspecified 0.0.0.0"         "bind 0.0.0.0"
content_case allow "netmask 255.255.255.0"       "mask 255.255.255.0"
content_case allow "netmask 255.255.255.252"     "mask 255.255.255.252"
content_case allow "doc range 192.0.2.10"        "host 192.0.2.10"
content_case allow "doc range 198.51.100.7"      "host 198.51.100.7"
content_case allow "doc range 203.0.113.7"       "host 203.0.113.7"
content_case block "private 10.x"                "host 10.1.2.3"
content_case block "private 172.16/12"           "host 172.20.0.5"
content_case block "private 192.168/16"          "host 192.168.1.10"
content_case block "public 8.8.8.8"              "dns 8.8.8.8"
content_case block "allowed and disallowed on one line" "from 127.0.0.1 to 8.8.4.4"
content_case allow "five-part 1.2.3.4.5 is not an address" "version 1.2.3.4.5"
content_case allow "out-of-range 300.1.1.1"      "value 300.1.1.1"
content_case allow "plain prose"                 "nothing to see here"
content_case block "environment file content: home path" "/Users/example/notes"
content_case block "secret assignment"           'api_key = "abcdefghijklmnop"'
# removing a leak is never blocked: only added lines are scanned
(cd "$repo" && git reset -q && printf 'host 8.8.8.8\n' > old.txt && git add old.txt \
  && git -c user.name=t -c user.email=t@example.com commit -q --no-verify -m seed \
  && git rm -q old.txt) >/dev/null 2>&1
(cd "$repo" && "$gate/commit-gate.sh") >/dev/null 2>&1 && report "gate allow  removing a line with a public address" 1 || report "gate allow  removing a line with a public address" 0

echo
echo "$((total - fails))/$total passed"
[ "$fails" -eq 0 ]
