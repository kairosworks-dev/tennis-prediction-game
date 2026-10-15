#!/usr/bin/env bash
# Commit gate: refuse a commit whose staged changes contain secrets or private
# infrastructure names. Runs as git's pre-commit hook (agent-hooks/pre-commit)
# and from the coding agent's pre-tool hook (agent-hooks/claude-pre-tool.sh).
#
# Two pattern lists:
#   - generic, below: things that are never right in a public repo
#   - agent-hooks/private-patterns.txt (gitignored, optional): the author's own
#     names, one extended regex per line, '#' comments allowed
#
# Only ADDED lines are scanned, so removing a leak is never blocked.
# Prints file and pattern name on a hit, never the matching line itself.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
status=0

hit() { printf 'commit-gate: %s  (%s)\n' "$1" "$2" >&2; status=1; }

# 1. Files that must not be committed at all.
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    *.env|*/.env|.env.*|*/.env.*)
      case "$f" in *.env.example|*/.env.example) ;; *) hit "$f" "environment file";; esac;;
    *.pem|*.key|*id_rsa*|*id_ed25519*) hit "$f" "private key file";;
  esac
done < <(git diff --cached --name-only --diff-filter=AM)

# 2. Generic patterns in added lines. name|regex
generic='ipv4 address|\b([0-9]{1,3}\.){3}[0-9]{1,3}\b
1password reference|op://
private key block|-----BEGIN [A-Z ]*PRIVATE KEY-----
home directory path|(/Users/|/home/)[A-Za-z0-9_.-]+
github token|\bgh[pousr]_[A-Za-z0-9]{20,}
aws access key|\bAKIA[0-9A-Z]{16}\b
bearer or api key assignment|(api[_-]?key|secret|token|password)\s*[:=]\s*["'"'"'][^"'"'"']{8,}'
allow_ips='127\.0\.0\.1|0\.0\.0\.0|255\.255\.255\.|\b(10|172|192)\.(0|16|168)\.[0-9]+\.[0-9]+'

scan() { # $1 name, $2 regex, $3 extra exclusions (regex) or empty
  local name="$1" re="$2" excl="${3:-}"
  git diff --cached --diff-filter=AM -U0 -- . ':!agent-hooks/' \
    | awk '/^\+\+\+ b\//{f=substr($0,7)} /^\+/ && !/^\+\+\+/{print f "\t" substr($0,2)}' \
    | { if [ -n "$excl" ]; then grep -Ev -e "$excl" || true; else cat; fi; } \
    | grep -E -e "$re" | cut -f1 | sort -u \
    | while IFS= read -r f; do hit "$f" "$name"; done
}

while IFS='|' read -r name re; do
  [ -z "$name" ] && continue
  if [ "$name" = "ipv4 address" ]; then out=$(scan "$name" "$re" "$allow_ips"); else out=$(scan "$name" "$re"); fi
  [ -n "$out" ] && { printf '%s\n' "$out" >&2; status=1; }
done <<< "$generic"

# 3. The author's private list, if present. Scanned everywhere, including agent-hooks/.
private="$here/private-patterns.txt"
if [ -f "$private" ]; then
  while IFS= read -r re; do
    case "$re" in ''|'#'*) continue;; esac
    out=$(git diff --cached --diff-filter=AM -U0 \
      | awk '/^\+\+\+ b\//{f=substr($0,7)} /^\+/ && !/^\+\+\+/{print f "\t" substr($0,2)}' \
      | grep -E -- "$re" | cut -f1 | sort -u)
    [ -n "$out" ] && { while IFS= read -r f; do hit "$f" "private pattern"; done <<< "$out"; }
  done < "$private"
fi

if [ $status -ne 0 ]; then
  echo 'commit-gate: blocked. Remove the content above (or move it out of the public repo) and commit again.' >&2
fi
exit $status
