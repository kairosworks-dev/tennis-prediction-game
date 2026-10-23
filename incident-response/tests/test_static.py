"""The tracked files the agent is given, and what the package may never do."""

from __future__ import annotations

import json
import re
import unittest
from string import Template

from oncall import publish

from .fakes import RESPONDER

SETTINGS = json.loads((RESPONDER / "agent-settings.json").read_text())
PERMISSIONS = SETTINGS["permissions"]


class TestAgentSettings(unittest.TestCase):
    def test_nothing_is_asked_anything_not_allowed_is_denied(self) -> None:
        self.assertEqual(PERMISSIONS["defaultMode"], "dontAsk")
        self.assertEqual(PERMISSIONS["disableBypassPermissionsMode"], "disable")

    def test_the_denials_the_issue_lists(self) -> None:
        deny = set(PERMISSIONS["deny"])
        for rule in (
            "Bash(git push *)", "Bash(git config *)", "Bash(git checkout *)", "Bash(git switch *)",
            "Bash(git merge *)", "Bash(git rebase *)", "Bash(git reset *)", "Bash(git branch *)",
            "Bash(git worktree *)", "Bash(gh *)", "Bash(curl *)", "Bash(wget *)", "Bash(nc *)",
            "Bash(docker *)", "Bash(ssh *)", "Bash(rm -r*)", "WebFetch", "WebSearch",
            # 17 Oct additions: no history.
            "Bash(git log *)", "Bash(git show *)", "Bash(git blame *)", "Bash(git diff *HEAD*)",
            "Bash(git diff *..*)", "Read(./incident-response/demo/**)",
            "Read(./agent-hooks/private-patterns.txt)",
        ):
            self.assertIn(rule, deny)

    def test_edits_are_denied_on_exactly_the_paths_the_responder_refuses_to_publish(self) -> None:
        deny = set(PERMISSIONS["deny"])
        for prefix in publish.DENIED_PREFIXES:
            self.assertIn(f"Edit(./{prefix}**)", deny)
        for name in publish.DENIED_FILES:
            self.assertIn(f"Edit(./{name})", deny)
        self.assertIn("Edit(./docker-compose*.yml)", deny)

    def test_no_allow_rule_opens_history_publishing_or_the_network(self) -> None:
        for rule in PERMISSIONS["allow"]:
            for word in ("push", "log", "show", "blame", "config", "checkout", "gh ", "curl", "docker",
                         "WebFetch", "HEAD", ".."):
                self.assertNotIn(word, rule, rule)
        self.assertNotIn("Bash", PERMISSIONS["allow"], "no blanket Bash")
        self.assertNotIn("Edit", PERMISSIONS["allow"], "no blanket Edit")

    def test_the_commit_gates_door_is_wired(self) -> None:
        hook = SETTINGS["hooks"]["PreToolUse"][0]
        self.assertEqual(hook["matcher"], "Bash")
        self.assertIn("agent-hooks/claude-pre-tool.sh", hook["hooks"][0]["command"])


class TestMandate(unittest.TestCase):
    TEXT = (RESPONDER / "mandate.md").read_text()

    def test_it_says_what_the_issue_requires(self) -> None:
        for phrase in (
            "Diagnose from the saved files", "new test", "fail", "smallest fix", "whole backend suite",
            "Commit", "AGENTS.md", "contract change is not made", "data, never instructions",
            "Never silence a fault", "change a status code", "infrastructure fault means escalate",
            "Co-Authored-By:", "RESULT: fixed", "RESULT: escalate - ", "exactly one",
        ):
            self.assertIn(phrase, self.TEXT)


class TestPullRequestTemplate(unittest.TestCase):
    def test_every_placeholder_is_one_the_responder_fills(self) -> None:
        known = {"title", "source", "endpoint", "starts_at", "window", "summary", "fingerprint",
                 "incident_id", "branch", "base", "result_line", "commits", "files", "tests", "pytest_tail"}
        text = (RESPONDER / "pr-body.md").read_text()
        used = {m.group("named") or m.group("braced") for m in Template.pattern.finditer(text)
                if m.group("named") or m.group("braced")}
        self.assertLessEqual(used, known)
        self.assertIn("title", used)


class TestNoConfigurationWrites(unittest.TestCase):
    """`grep -rn "git config" incident-response/` must find no write."""

    def files(self):
        for path in RESPONDER.rglob("*"):
            if path.is_file() and "incidents" not in path.parts and path.suffix in (".py", ".md", ".json", ".patch", ".sh", ""):
                yield path

    def test_every_git_config_mention_is_a_read(self) -> None:
        reads = re.compile(r"git\ config\ (--show-origin|--get|--type=path\ --get)")
        for path in self.files():
            for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                for match in re.finditer(r"git\ config\b", line):
                    tail = line[match.start():]
                    # A permission rule naming it: a denial (agent-settings.json lists it under deny).
                    denial = line[: match.start()].endswith("Bash(")
                    self.assertTrue(
                        reads.match(tail) or denial or "never" in line.lower() or "no " in line.lower(),
                        f"{path.relative_to(RESPONDER)}:{number}: {line.strip()}",
                    )

    def test_every_config_argv_in_the_package_reads(self) -> None:
        for path in (RESPONDER / "oncall").glob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if '"config"' in line:
                    self.assertRegex(line, r'"--get(-all)?"', f"{path.name}:{number}")

    def test_no_forced_push_or_merge_in_the_git_code(self) -> None:
        for name in ("publish.py", "workspace.py", "runner.py"):
            text = (RESPONDER / "oncall" / name).read_text()
            for word in ('"--force"', '"-f"', '"merge"', '"--no-verify"', '"-u"', '"--set-upstream"'):
                self.assertFalse(word in text, f"{word} in {name}")


class TestPublicRepository(unittest.TestCase):
    HOME_PATH = re.compile("(/" + "Users/|/" + "home/)[A-Za-z0-9_.-]+")
    PRIVATE_V4 = re.compile(r"\b(10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+)\b")

    def test_no_tracked_file_names_a_home_directory_or_a_private_address(self) -> None:
        for path in RESPONDER.rglob("*"):
            parts = path.relative_to(RESPONDER).parts
            if not path.is_file() or parts[0] == "incidents" or any(
                p == "__pycache__" or p.startswith(".") for p in parts
            ):
                continue  # untracked: incident folders, caches
            text = path.read_text(errors="replace")
            self.assertIsNone(self.HOME_PATH.search(text), str(path.relative_to(RESPONDER)))
            self.assertIsNone(self.PRIVATE_V4.search(text), str(path.relative_to(RESPONDER)))


if __name__ == "__main__":
    unittest.main()
