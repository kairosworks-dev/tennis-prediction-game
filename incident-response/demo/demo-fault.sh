#!/usr/bin/env bash
# make demo-fault: create the local branch demo/oncall-fault from main, apply the
# on-call demo fault (incident-response/demo/fault.patch) and commit it, so the
# commit gate runs on it like on any commit. The fault is never on main; this
# script never pushes. Undo with: make demo-reset
set -euo pipefail

branch="demo/oncall-fault"
patch="incident-response/demo/fault.patch"
cd "$(git rev-parse --show-toplevel)"

current="$(git symbolic-ref --quiet --short HEAD || true)"
if [ "$current" != "main" ]; then
  echo "demo-fault: switch to main first (this checkout is on ${current:-a detached HEAD})." >&2
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "demo-fault: the working tree has changes; commit or set them aside first." >&2
  exit 1
fi
if git show-ref --verify --quiet "refs/heads/$branch"; then
  echo "demo-fault: $branch already exists; run make demo-reset first." >&2
  exit 1
fi
git apply --check "$patch"

git switch -c "$branch" main
git apply --index "$patch"
if ! git commit -q -m "chore(demo): plant the on-call demo fault, never merge" \
    -m "Applied from $patch by make demo-fault, on the local branch $branch only."; then
  echo "demo-fault: the commit did not happen; the patch is staged on $branch." >&2
  echo "  Fix the cause and run: git commit -m 'chore(demo): plant the on-call demo fault, never merge'" >&2
  echo "  Or give up: git restore --staged --worktree backend && git switch main && git branch -D $branch" >&2
  exit 1
fi

echo ""
echo "  $branch: $(git log -1 --format='%h %s')"
echo "  Next: git push origin $branch   (the pull request's base must exist on GitHub)"
echo "        then start the stack from this branch (incident-response/README.md, The demo)."
