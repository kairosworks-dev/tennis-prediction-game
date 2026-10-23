"""After the agent: decide from the repository, then publish or not.

The agent's RESULT line is a claim. The responder publishes only if, in the
worktree: the branch is still the oncall branch, it has at least one commit
beyond the base, the diff adds or changes a test under backend/tests/, it
touches no denied path, nothing is left uncommitted, and the responder's own
`uv run pytest` is green. Then it pushes that one branch with an explicit
refspec and opens the pull request with `gh pr create`. Never --force, never
a merge, never a configuration write, never the base branch.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .config import PR_LABEL, REMOTE
from .incident import BRANCH_PATTERN
from .seams import CommandResult, Commands
from .workspace import Workspace

#: Paths the agent may not change (the same list as agent-settings.json denies).
DENIED_PREFIXES = (".github/", "agent-hooks/", ".claude/", "incident-response/")
DENIED_FILES = ("openapi.yaml", "Dockerfile", "backend/pyproject.toml", "backend/uv.lock")
DENIED_GLOBS = ("docker-compose*.yml", "docker-compose*.yaml")
TEST_PREFIX = "backend/tests/"
PYTEST = ("uv", "run", "pytest", "-q")
PYTEST_TIMEOUT = 1800.0


def is_denied(path: str) -> bool:
    return (
        path.startswith(DENIED_PREFIXES)
        or path in DENIED_FILES
        or any(fnmatch.fnmatch(path, g) for g in DENIED_GLOBS)
    )


@dataclass
class Checks:
    on_branch: bool = False
    commits: List[str] = field(default_factory=list)
    changed: List[str] = field(default_factory=list)
    tests: List[str] = field(default_factory=list)
    denied: List[str] = field(default_factory=list)
    uncommitted: List[str] = field(default_factory=list)
    pytest_ran: bool = False
    pytest_ok: bool = False
    pytest_tail: str = ""
    reasons: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.reasons

    def as_dict(self) -> Dict[str, object]:
        return {
            "on_branch": self.on_branch,
            "commits": self.commits,
            "changed_files": self.changed,
            "tests_added_or_changed": self.tests,
            "denied_paths_touched": self.denied,
            "uncommitted": self.uncommitted,
            "pytest_ran": self.pytest_ran,
            "pytest_green": self.pytest_ok,
            "pytest_tail": self.pytest_tail,
            "reasons": self.reasons,
        }


def _git(commands: Commands, ws: Workspace, env: Dict[str, str], *args: str) -> CommandResult:
    return commands.run(["git", "-C", str(ws.path), *args], env=env, timeout=120)


def _lines(result: CommandResult) -> List[str]:
    return [line for line in result.stdout.splitlines() if line.strip()] if result.ok else []


def check(commands: Commands, ws: Workspace, env: Dict[str, str]) -> Checks:
    checks = Checks()

    head = _git(commands, ws, env, "symbolic-ref", "--quiet", "--short", "HEAD")
    checks.on_branch = head.ok and head.stdout.strip() == ws.branch
    if not checks.on_branch:
        checks.reasons.append(f"the worktree is no longer on {ws.branch}")

    span = f"{ws.base_sha}..HEAD"
    checks.commits = _lines(_git(commands, ws, env, "log", "--no-decorate", "--format=%h %s", span))
    if not checks.commits:
        checks.reasons.append("no commit on the branch beyond the base")

    checks.changed = _lines(
        _git(commands, ws, env, "diff", "--name-only", "--no-renames", ws.base_sha, "HEAD")
    )
    added_or_modified = _lines(
        _git(
            commands, ws, env, "diff", "--name-only", "--no-renames", "--diff-filter=AM",
            ws.base_sha, "HEAD",
        )
    )
    checks.tests = [p for p in added_or_modified if p.startswith(TEST_PREFIX) and p.endswith(".py")]
    if checks.commits and not checks.tests:
        checks.reasons.append("the diff adds or changes no test under backend/tests/")

    checks.denied = [p for p in checks.changed if is_denied(p)]
    if checks.denied:
        checks.reasons.append("the diff touches denied paths: " + ", ".join(checks.denied))

    status = _git(commands, ws, env, "status", "--porcelain", "--untracked-files=normal")
    checks.uncommitted = _lines(status)
    if not status.ok:
        checks.reasons.append("git status failed in the worktree")
    elif checks.uncommitted:
        checks.reasons.append("the worktree has uncommitted or untracked changes")

    if checks.reasons:
        return checks

    checks.pytest_ran = True
    result = commands.run(list(PYTEST), cwd=ws.path / "backend", env=env, timeout=PYTEST_TIMEOUT)
    checks.pytest_ok = result.ok
    tail = (result.stdout + "\n" + result.stderr).strip().splitlines()
    checks.pytest_tail = "\n".join(tail[-15:])
    if not result.ok:
        checks.reasons.append("the responder's own `uv run pytest` is not green")
    return checks


def pr_base(base_ref: str) -> str:
    """The branch name GitHub knows: origin/main -> main, refs/heads/x -> x."""
    for prefix in ("refs/heads/", f"refs/remotes/{REMOTE}/", f"{REMOTE}/"):
        if base_ref.startswith(prefix):
            return base_ref[len(prefix):]
    return base_ref


def push_command(ws: Workspace) -> List[str]:
    ref = f"refs/heads/{ws.branch}"
    return ["git", "-C", str(ws.path), "push", REMOTE, f"{ref}:{ref}"]


def pr_command(ws: Workspace, title: str, body_file: Path) -> List[str]:
    return [
        "gh", "pr", "create",
        "--base", pr_base(ws.base_ref),
        "--head", ws.branch,
        "--label", PR_LABEL,
        "--title", title,
        "--body-file", str(body_file),
    ]


@dataclass
class Published:
    ok: bool
    url: Optional[str]
    log: List[Dict[str, object]]
    reason: str = ""


def _record(result: CommandResult) -> Dict[str, object]:
    return {
        "argv": list(result.argv),
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
    }


def publish(commands: Commands, ws: Workspace, title: str, body_file: Path, env: Dict[str, str]) -> Published:
    if not BRANCH_PATTERN.match(ws.branch):
        return Published(False, None, [], f"refusing to push {ws.branch}: not an oncall/ branch name")
    log: List[Dict[str, object]] = []
    pushed = commands.run(push_command(ws), env=env, timeout=300)
    log.append(_record(pushed))
    if not pushed.ok:
        return Published(False, None, log, "git push failed")
    opened = commands.run(pr_command(ws, title, body_file), cwd=ws.path, env=env, timeout=300)
    log.append(_record(opened))
    if not opened.ok:
        return Published(False, None, log, "gh pr create failed (the branch is pushed)")
    url = next((w for w in opened.stdout.split() if w.startswith("https://")), None)
    return Published(True, url, log)


def built_commands(ws: Workspace, title: str, body_file: Path) -> Sequence[List[str]]:
    """Every command publishing can run, for the recorder test."""
    return (push_command(ws), pr_command(ws, title, body_file))
