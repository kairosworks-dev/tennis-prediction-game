"""The isolated checkout the agent works in.

A git worktree outside the repository, on a new `oncall/...` branch, created
from the main checkout so that it inherits the relative `core.hooksPath` and
the commit gate's two doors accept it. The author's checkout, branch and
uncommitted work are never touched, and no git configuration is written: the
branch starts from the base's commit id with --no-track, so git records no
upstream for it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .seams import Commands

PRIVATE_PATTERNS = Path("agent-hooks") / "private-patterns.txt"
HOOKS_DIR = "agent-hooks"


class WorkspaceError(Exception):
    """The worktree could not be prepared; the run escalates without an agent."""


@dataclass
class Workspace:
    path: Path
    branch: str
    base_ref: str
    base_sha: str
    main_root: Path
    notes: List[str] = field(default_factory=list)
    private_patterns: str = "absent"


def _git(commands: Commands, where: Path, env: Dict[str, str], *args: str, timeout: float = 120):
    return commands.run(["git", "-C", str(where), *args], env=env, timeout=timeout)


def main_worktree(commands: Commands, repo_root: Path, env: Dict[str, str]) -> Path:
    """The main checkout: the parent of the shared git directory."""
    result = _git(commands, repo_root, env, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not result.ok or not result.stdout.strip():
        raise WorkspaceError(f"not a git checkout: {repo_root.name} ({result.stderr.strip()[:200]})")
    common = Path(result.stdout.strip())
    if common.name != ".git":
        raise WorkspaceError("the repository has no main worktree (bare repository)")
    return common.parent


def read_hooks_path(commands: Commands, where: Path, env: Dict[str, str]) -> str:
    """`core.hooksPath` with origin and scope, for the record. Read only."""
    result = _git(
        commands, where, env, "config", "--show-origin", "--show-scope", "--get-all", "core.hooksPath"
    )
    return result.stdout.strip() if result.ok else "(unset)"


def hooks_resolve_to_own(commands: Commands, worktree: Path, env: Dict[str, str]) -> bool:
    """The same test the pre-tool door makes: hooksPath is this checkout's agent-hooks."""
    result = _git(commands, worktree, env, "config", "--type=path", "--get", "core.hooksPath")
    value = result.stdout.strip() if result.ok else ""
    if not value:
        return False
    path = Path(value)
    if not path.is_absolute():
        top = _git(commands, worktree, env, "rev-parse", "--show-toplevel")
        if not top.ok:
            return False
        path = Path(top.stdout.strip()) / path
    return os.path.realpath(str(path)) == os.path.realpath(str(worktree / HOOKS_DIR))


def _inside(child: Path, parent: Path) -> bool:
    child_real, parent_real = os.path.realpath(str(child)), os.path.realpath(str(parent))
    return child_real == parent_real or child_real.startswith(parent_real + os.sep)


def prepare(
    commands: Commands,
    *,
    repo_root: Path,
    worktree_root: Path,
    name: str,
    branch: str,
    base_ref: str,
    env: Dict[str, str],
) -> Workspace:
    main = main_worktree(commands, repo_root, env)

    resolved = _git(commands, main, env, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}")
    if not resolved.ok or not resolved.stdout.strip():
        raise WorkspaceError(f"the base ref {base_ref} does not exist in the main checkout")
    base_sha = resolved.stdout.strip()

    if _inside(worktree_root, main):
        raise WorkspaceError("RESPONDER_WORKTREE_DIR is inside the repository; it must be outside")
    worktree_root.mkdir(parents=True, exist_ok=True)
    path = worktree_root / name
    if path.exists():
        raise WorkspaceError(f"the worktree directory {path.name} already exists")

    added = _git(
        commands, main, env, "worktree", "add", "--no-track", "-b", branch, str(path), base_sha,
        timeout=300,
    )
    if not added.ok:
        raise WorkspaceError(f"git worktree add failed: {added.stderr.strip()[:300]}")
    ws = Workspace(path=path, branch=branch, base_ref=base_ref, base_sha=base_sha, main_root=main)

    if not hooks_resolve_to_own(commands, path, env):
        raise WorkspaceError(
            "core.hooksPath in the new worktree does not resolve to its own agent-hooks, so "
            "the commit gate's pre-tool door would refuse every commit (run `make hooks` in "
            "the main checkout). No agent was started."
        )

    source = main / PRIVATE_PATTERNS
    if source.is_file():
        (path / PRIVATE_PATTERNS).symlink_to(source)
        ws.private_patterns = "linked from the main checkout (gitignored symlink)"
    else:
        ws.private_patterns = "absent: the main checkout has none; generic patterns only"

    synced = commands.run(["uv", "sync"], cwd=path / "backend", env=env, timeout=900)
    if not synced.ok:
        raise WorkspaceError(f"uv sync failed in the worktree: {synced.stderr.strip()[-300:]}")
    ws.notes.append("uv sync done in backend/")
    return ws
