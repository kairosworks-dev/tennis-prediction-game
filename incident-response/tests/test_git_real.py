"""The workspace and the publish decision against real git, in throwaway repositories.

Isolation: every git subprocess here runs with HOME set to a temp directory and
the identity in GIT_AUTHOR_*/GIT_COMMITTER_*, so the user's own git settings
are never read. No test writes git configuration: the repositories come from
`git init` and `git clone`, and the origin is a local bare clone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List

from oncall import publish, workspace
from oncall.seams import CommandResult, Commands

BRANCH = "oncall/5xx-on-the-place-a-prediction-journey-20261023T101500Z"


class GitOnly(Commands):
    """Real git; uv and gh are answered here (no network, no CLI)."""

    def __init__(self) -> None:
        self.calls: List[List[str]] = []

    def run(self, argv, cwd=None, env=None, timeout=600.0, discard_stdout=False) -> CommandResult:
        argv = list(argv)
        self.calls.append(argv)
        if argv[0] in ("uv", "gh"):
            out = "https://github.com/OWNER/REPO/pull/1\n" if argv[0] == "gh" else "5 passed"
            return CommandResult(argv, 0, out, "")
        return super().run(argv, cwd=cwd, env=env, timeout=timeout, discard_stdout=discard_stdout)


class RealGit(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="oncall-git-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        home = self.tmp / "home"
        home.mkdir()
        self.env: Dict[str, str] = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(home),
            "LANG": "C",
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Test Author",
            "GIT_COMMITTER_EMAIL": "author@example.invalid",
        }
        seed = self.tmp / "seed"
        self.git(self.tmp, "init", "-q", "-b", "main", str(seed))
        self.write(seed, "README.md", "seed\n")
        self.write(seed, "openapi.yaml", "openapi: 3.1.0\n")
        self.write(seed, "backend/app/rules.py", "def other(tie, winner):\n    return tie[tie.index(winner) + 1]\n")
        self.write(seed, "backend/tests/test_rules.py", "def test_nothing():\n    assert True\n")
        self.write(seed, ".gitignore", "agent-hooks/private-patterns.txt\n")
        self.write(seed, "agent-hooks/pre-commit", "#!/bin/sh\nexit 0\n")
        self.git(seed, "add", "-A")
        self.git(seed, "commit", "-q", "-m", "seed")
        self.origin = self.tmp / "origin.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(seed), str(self.origin))
        self.main = self.tmp / "main"
        self.git(self.tmp, "clone", "-q", str(self.origin), str(self.main))
        self.config_before = (self.main / ".git" / "config").read_bytes()
        self.worktrees = self.tmp / "worktrees"

    def git(self, where: Path, *args: str) -> str:
        done = subprocess.run(["git", "-C", str(where), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def write(self, root: Path, name: str, text: str) -> None:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def prepare_expecting_the_hooks_refusal(self, commands: Commands) -> Path:
        with self.assertRaises(workspace.WorkspaceError) as caught:
            workspace.prepare(
                commands, repo_root=self.main, worktree_root=self.worktrees, name="incident-1",
                branch=BRANCH, base_ref="origin/main", env=self.env,
            )
        self.assertIn("core.hooksPath", str(caught.exception))
        return self.worktrees / "incident-1"

    def test_the_worktree_is_made_outside_from_the_base_and_no_config_is_written(self) -> None:
        commands = GitOnly()
        path = self.prepare_expecting_the_hooks_refusal(commands)
        self.assertTrue((path / "README.md").is_file())
        self.assertEqual(self.git(path, "symbolic-ref", "--short", "HEAD").strip(), BRANCH)
        self.assertEqual(self.git(path, "rev-parse", "HEAD"), self.git(self.main, "rev-parse", "origin/main"))
        self.assertEqual(self.git(self.main, "symbolic-ref", "--short", "HEAD").strip(), "main",
                         "the main checkout's own branch is untouched")
        self.assertEqual((self.main / ".git" / "config").read_bytes(), self.config_before)
        self.assertFalse(any(a[3:4] == ["config"] and "--get" not in " ".join(a) for a in commands.calls))
        self.assertFalse(any(a[:2] == ["uv", "sync"] for a in commands.calls), "no uv sync before the check")

    def test_the_main_worktree_is_found_from_a_linked_worktree(self) -> None:
        path = self.prepare_expecting_the_hooks_refusal(GitOnly())
        self.assertEqual(
            os.path.realpath(str(workspace.main_worktree(GitOnly(), path, self.env))),
            os.path.realpath(str(self.main)),
        )

    def worktree_with_fix(self, extra_change: str = "") -> workspace.Workspace:
        path = self.prepare_expecting_the_hooks_refusal(GitOnly())
        self.write(path, "backend/app/rules.py", "def other(tie, winner):\n    return tie[1 - tie.index(winner)]\n")
        self.write(path, "backend/tests/test_oncall.py", "def test_second_player():\n    assert True\n")
        if extra_change:
            self.write(path, extra_change, "changed\n")
        self.git(path, "add", "-A")
        self.git(path, "commit", "-q", "-m", "fix: pick the other player")
        base = self.git(self.main, "rev-parse", "origin/main").strip()
        return workspace.Workspace(path=path, branch=BRANCH, base_ref="origin/main", base_sha=base, main_root=self.main)

    def test_the_decision_reads_the_real_repository(self) -> None:
        ws = self.worktree_with_fix()
        checks = publish.check(GitOnly(), ws, self.env)
        self.assertEqual(checks.reasons, [])
        self.assertEqual(len(checks.commits), 1)
        self.assertEqual(checks.tests, ["backend/tests/test_oncall.py"])
        self.assertTrue(checks.pytest_ran)

    def test_a_denied_path_is_found_in_the_real_diff(self) -> None:
        ws = self.worktree_with_fix(extra_change="openapi.yaml")
        checks = publish.check(GitOnly(), ws, self.env)
        self.assertEqual(checks.denied, ["openapi.yaml"])
        self.assertFalse(checks.pytest_ran)

    def test_publishing_pushes_only_the_oncall_branch(self) -> None:
        ws = self.worktree_with_fix()
        main_before = self.git(self.origin, "rev-parse", "refs/heads/main")
        commands = GitOnly()
        published = publish.publish(commands, ws, "fix(oncall): x", self.tmp / "body.md", self.env)
        self.assertTrue(published.ok, published.log)
        heads = self.git(self.origin, "for-each-ref", "--format=%(refname)", "refs/heads").split()
        self.assertEqual(sorted(heads), sorted(["refs/heads/main", f"refs/heads/{BRANCH}"]))
        self.assertEqual(self.git(self.origin, "rev-parse", "refs/heads/main"), main_before)
        self.assertEqual(self.git(self.origin, "rev-parse", f"refs/heads/{BRANCH}"), self.git(ws.path, "rev-parse", "HEAD"))
        self.assertEqual((self.main / ".git" / "config").read_bytes(), self.config_before,
                         "the push set no upstream")
        pr = next(a for a in commands.calls if a[0] == "gh")
        self.assertEqual(pr[pr.index("--base") + 1], "main")


if __name__ == "__main__":
    unittest.main()
