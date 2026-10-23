#!/usr/bin/env bash
# make demo-reset: undo the demo locally. Switches back to main, removes the
# responder's worktrees (every linked worktree on an oncall/ branch), deletes the
# local oncall/* branches and demo/oncall-fault. Never touches the remote; the
# remote cleanup commands are in incident-response/README.md.
set -euo pipefail

demo="demo/oncall-fault"
cd "$(git rev-parse --show-toplevel)"

if [ -n "$(git status --porcelain)" ]; then
  echo "demo-reset: the working tree has changes; commit or set them aside first." >&2
  exit 1
fi
current="$(git symbolic-ref --quiet --short HEAD || true)"
case "$current" in
  "$demo"|oncall/*) git switch main ;;
esac

git worktree prune
git worktree list --porcelain \
  | awk '/^worktree /{path=substr($0, 10)} /^branch refs\/heads\/oncall\//{print path}' \
  | while IFS= read -r path; do
      echo "removing worktree $path"
      git worktree remove --force "$path"
    done
git worktree prune

git for-each-ref --format='%(refname:short)' 'refs/heads/oncall/' \
  | while IFS= read -r b; do git branch -D "$b"; done
if git show-ref --verify --quiet "refs/heads/$demo"; then
  git branch -D "$demo"
fi

echo ""
echo "  Local demo state removed. Remote branches, if you pushed them: incident-response/README.md, Cleanup."
