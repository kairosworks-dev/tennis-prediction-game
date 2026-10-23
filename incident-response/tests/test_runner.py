"""The run: worktree, agent, and the publish decision, one test per branch.

The agent is tests/fake_agent.py, run for real; git, gh, uv and docker are the
recorder in fakes.py.
"""

from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path

from oncall import config, publish
from oncall.incident import BRANCH_PATTERN
from oncall.runner import final_text, result_line
from oncall.workspace import Workspace

from .fakes import SHA, FakeHttp, Scenario
from .test_context import RunCase


class TestTheAgentRun(RunCase):
    def test_argv_cwd_environment_and_stdin_of_the_agent(self) -> None:
        result, folder, commands = self.run_incident(FakeHttp())
        record = self.agent_record()
        worktree = self.worktrees / folder.name
        self.assertEqual(os.path.realpath(record["cwd"]), os.path.realpath(str(worktree)))
        argv = record["argv"]
        self.assertIn("--settings", argv)
        self.assertEqual(argv[argv.index("--settings") + 1], str(self.main / "incident-response" / "agent-settings.json"))
        self.assertEqual(argv[argv.index("--add-dir") + 1], str(folder))
        env = record["env"]
        allowed = set(config.AGENT_ENV_ALLOW) | {"UV_OFFLINE", "__CF_USER_TEXT_ENCODING"}
        self.assertLessEqual(set(env), allowed, "only the allow-listed variables reach the agent")
        self.assertEqual(env["UV_OFFLINE"], "1")
        for never in ("RESPONDER_TOKEN", "GH_TOKEN", "SSH_AUTH_SOCK"):
            self.assertNotIn(never, env)

    def test_the_extra_environment_list_is_honoured_but_never_the_token(self) -> None:
        settings = {"agent_env_extra": ("SIGNING_HELPER_VAR", "RESPONDER_TOKEN"),
                    "environ": {"SIGNING_HELPER_VAR": "1"}}
        self.run_incident(FakeHttp(), **settings)
        env = self.agent_record()["env"]
        self.assertEqual(env.get("SIGNING_HELPER_VAR"), "1")
        self.assertNotIn("RESPONDER_TOKEN", env)

    def test_the_incident_folder_is_read_only_during_the_run(self) -> None:
        _, folder, _ = self.run_incident(FakeHttp())
        record = self.agent_record()
        self.assertTrue(record["incident_write_refused"])
        self.assertTrue(record["prompt_write_refused"])
        self.assertFalse((folder / "agent-was-here.txt").exists())
        self.assertTrue(os.access(str(folder), os.W_OK), "writable again after the run")

    def test_the_worktree_is_outside_the_repository_on_an_oncall_branch(self) -> None:
        _, folder, commands = self.run_incident(FakeHttp())
        add = next(a for a in commands.argvs() if a[3:5] == ["worktree", "add"])
        self.assertEqual(add[2], str(self.main), "created from the main checkout")
        self.assertIn("--no-track", add)
        branch = add[add.index("-b") + 1]
        self.assertRegex(branch, BRANCH_PATTERN)
        self.assertFalse(add[-2].startswith(str(self.main)))
        self.assertEqual(add[-1], SHA, "from the base's commit id")
        self.assertTrue(commands.ran(lambda a: a[:2] == ["uv", "sync"]))

    def test_the_private_pattern_list_is_linked_when_the_main_checkout_has_one(self) -> None:
        (self.main / "agent-hooks" / "private-patterns.txt").write_text("example-pattern\n")
        _, folder, _ = self.run_incident(FakeHttp())
        link = self.worktrees / folder.name / "agent-hooks" / "private-patterns.txt"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.path.realpath(str(link)), os.path.realpath(str(self.main / "agent-hooks" / "private-patterns.txt")))
        ctx = json.loads((folder / "context.json").read_text())
        self.assertIn("linked", ctx["workspace"]["private_patterns"])

    def test_no_private_pattern_list_is_noted(self) -> None:
        _, folder, _ = self.run_incident(FakeHttp())
        ctx = json.loads((folder / "context.json").read_text())
        self.assertIn("absent", ctx["workspace"]["private_patterns"])

    def test_hooks_path_before_and_after_are_recorded(self) -> None:
        result, folder, _ = self.run_incident(FakeHttp())
        text = (folder / "hooks-path.txt").read_text()
        self.assertIn("unchanged: yes", text)
        data = json.loads((folder / "result.json").read_text())
        self.assertEqual(data["hooks_path_before"], data["hooks_path_after"])

    def test_the_agent_output_is_saved(self) -> None:
        _, folder, _ = self.run_incident(FakeHttp())
        output = (folder / "agent-output.jsonl").read_text()
        self.assertIn('"type": "result"', output)
        data = json.loads((folder / "result.json").read_text())
        self.assertEqual(data["permission_denials"], [{"tool": "Bash", "input": {"command": "git log"}}])


class TestDecision(RunCase):
    """One test per branch of the publish decision."""

    def assert_not_published(self, commands) -> None:
        self.assertFalse(commands.ran(lambda a: "push" in a))
        self.assertFalse(commands.ran(lambda a: a[:1] == ["gh"]))

    def test_published_when_every_check_holds(self) -> None:
        result, folder, commands = self.run_incident(FakeHttp())
        self.assertEqual(result.outcome, "published")
        self.assertEqual(result.details["pr_url"], "https://github.com/OWNER/REPO/pull/99")
        push = next(a for a in commands.argvs() if "push" in a)
        branch = result.details["branch"]
        self.assertEqual(push[-2:], ["origin", f"refs/heads/{branch}:refs/heads/{branch}"])
        pr = next(a for a in commands.argvs() if a[:3] == ["gh", "pr", "create"])
        self.assertEqual(pr[pr.index("--base") + 1], "demo/oncall-fault")
        self.assertEqual(pr[pr.index("--head") + 1], branch)
        self.assertEqual(pr[pr.index("--label") + 1], "on-call-agent")
        body = (folder / "pr-body.md").read_text()
        self.assertIn("Prediction submit 5xx", body)
        self.assertNotIn(str(self.tmp), body, "no local path in the public pull request")

    def test_escalated_without_a_commit(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), Scenario(commits=[], changed=[]))
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("no commit", result.reason)
        self.assert_not_published(commands)

    def test_escalated_without_a_test(self) -> None:
        result, _, commands = self.run_incident(
            FakeHttp(), Scenario(changed=["backend/app/domain/validation.py"])
        )
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("no test", result.reason)
        self.assert_not_published(commands)

    def test_a_deleted_test_does_not_count_as_a_test(self) -> None:
        result, _, commands = self.run_incident(
            FakeHttp(),
            Scenario(
                changed=["backend/app/domain/validation.py", "backend/tests/test_validation.py"],
                added_or_modified=["backend/app/domain/validation.py"],
            ),
        )
        self.assertEqual(result.outcome, "escalated")
        self.assert_not_published(commands)

    def test_escalated_when_a_denied_path_is_touched(self) -> None:
        for path in (".github/workflows/ci.yml", "agent-hooks/commit-gate.sh", "openapi.yaml",
                     "incident-response/agent-settings.json", "docker-compose.telemetry.yml",
                     "backend/uv.lock", ".claude/settings.json"):
            with self.subTest(path=path):
                self.setUp()
                scenario = Scenario(changed=["backend/tests/test_x.py", path])
                result, _, commands = self.run_incident(FakeHttp(), scenario)
                self.assertEqual(result.outcome, "escalated")
                self.assertIn("denied paths", result.reason)
                self.assert_not_published(commands)

    def test_escalated_when_something_is_left_uncommitted(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), Scenario(status=[" M backend/app/main.py"]))
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("uncommitted", result.reason)
        self.assert_not_published(commands)

    def test_escalated_when_the_responders_own_pytest_is_red(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), Scenario(pytest_rc=1))
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("pytest", result.reason)
        self.assert_not_published(commands)

    def test_escalated_when_the_branch_was_switched(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), Scenario(on_branch="main"))
        self.assertEqual(result.outcome, "escalated")
        self.assert_not_published(commands)

    def test_escalated_when_the_agent_escalates_even_with_a_commit(self) -> None:
        result, _, commands = self.run_incident(
            FakeHttp(), agent_cmd=self.agent_cmd("RESULT: escalate - the database is down")
        )
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("the database is down", result.reason)
        self.assertFalse(commands.ran(lambda a: a[:3] == ["uv", "run", "pytest"]))
        self.assert_not_published(commands)

    def test_agent_failed_without_a_result_line(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), agent_cmd=self.agent_cmd(result=""))
        self.assertEqual(result.outcome, "agent_failed")
        self.assertIn("RESULT", result.reason)
        self.assert_not_published(commands)

    def test_agent_failed_on_a_non_zero_exit(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), agent_cmd=self.agent_cmd(extra="--exit 3"))
        self.assertEqual(result.outcome, "agent_failed")
        self.assert_not_published(commands)

    def test_timed_out_kills_the_whole_process_group(self) -> None:
        began = time.monotonic()
        result, _, commands = self.run_incident(
            FakeHttp(), agent_cmd=self.agent_cmd(extra="--sleep 60 --spawn-child"), timeout_min=0.03
        )
        self.assertLess(time.monotonic() - began, 30)
        self.assertEqual(result.outcome, "timed_out")
        record = self.agent_record()
        for pid in (record["pid"], record["child_pid"]):
            deadline = time.monotonic() + 5
            while _alive(pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertFalse(_alive(pid), f"process {pid} survived the time-out")
        self.assert_not_published(commands)

    def test_escalated_without_an_agent_when_hooks_do_not_resolve_to_the_worktree(self) -> None:
        for value in ("", "/elsewhere/agent-hooks"):
            with self.subTest(hooks_path=value):
                self.setUp()
                result, _, commands = self.run_incident(FakeHttp(), Scenario(hooks_path=value))
                self.assertEqual(result.outcome, "escalated")
                self.assertIn("core.hooksPath", result.reason)
                self.assertIsNone(self.agent_record())
                self.assert_not_published(commands)

    def test_escalated_when_hooks_path_changed_during_the_run(self) -> None:
        result, folder, commands = self.run_incident(FakeHttp(), Scenario(hooks_change_after_agent=True))
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("changed during the run", result.reason)
        self.assertIn("unchanged: NO", (folder / "hooks-path.txt").read_text())
        self.assert_not_published(commands)

    def test_escalated_when_the_base_ref_is_missing(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), Scenario(base_exists=False))
        self.assertEqual(result.outcome, "escalated")
        self.assertIsNone(self.agent_record())

    def test_escalated_when_uv_sync_fails(self) -> None:
        result, _, _ = self.run_incident(FakeHttp(), Scenario(uv_sync_rc=1))
        self.assertEqual(result.outcome, "escalated")
        self.assertIn("uv sync", result.reason)
        self.assertIsNone(self.agent_record())

    def test_publish_failed_when_the_push_is_refused(self) -> None:
        result, _, commands = self.run_incident(FakeHttp(), Scenario(push_rc=1))
        self.assertEqual(result.outcome, "publish_failed")
        self.assertFalse(commands.ran(lambda a: a[:1] == ["gh"]))

    def test_publish_failed_when_the_pull_request_cannot_be_opened(self) -> None:
        result, _, _ = self.run_incident(FakeHttp(), Scenario(gh_rc=1))
        self.assertEqual(result.outcome, "publish_failed")
        self.assertIn("branch is pushed", result.reason)

    def test_the_outcome_is_printed_loudly(self) -> None:
        from io import StringIO

        from oncall.alerts import classify
        from oncall.runner import Responder

        from .fakes import FIXED_NOW, FakeCommands, fixture

        out = StringIO()
        responder = Responder(self.settings(), http=FakeHttp(loki_down=True),
                              commands=FakeCommands(self.main), clock=lambda: FIXED_NOW, out=out)
        responder.submit(classify(fixture("firing.json"), FIXED_NOW))
        responder.join(30)
        self.assertIn("ON-CALL RESULT: ESCALATED", out.getvalue())


class TestRecorder(unittest.TestCase):
    """No command the publishing builds names main, uses --force, merge or config."""

    def commands(self, base_ref: str):
        ws = Workspace(path=Path("/tmp/wt"), branch="oncall/prediction-submit-5xx-20261022T173830Z",
                       base_ref=base_ref, base_sha=SHA, main_root=Path("/tmp/main"))
        return publish.built_commands(ws, "fix(oncall): x", Path("/tmp/body.md"))

    def test_with_the_demo_base_no_command_names_main(self) -> None:
        for argv in self.commands("demo/oncall-fault"):
            joined = " ".join(argv)
            self.assertNotIn("main", joined)
            for word in ("--force", "-f", "--force-with-lease", "merge", "config", "--mirror", "--all", "--delete"):
                self.assertNotIn(word, argv)
            self.assertFalse(any(a.startswith("+") for a in argv), "no forced refspec")

    def test_with_the_default_base_main_is_only_the_pull_requests_base(self) -> None:
        push, pr = self.commands("origin/main")
        self.assertFalse(any("main" in a for a in push), "the push never names main")
        mentions = [i for i, a in enumerate(pr) if "main" in a]
        self.assertEqual(mentions, [pr.index("--base") + 1])

    def test_a_branch_that_is_not_an_oncall_branch_is_never_pushed(self) -> None:
        class Refuse:
            def run(self, *a, **k):  # pragma: no cover - must not be called
                raise AssertionError("no command may run")

        ws = Workspace(path=Path("/tmp/wt"), branch="main", base_ref="origin/main",
                       base_sha=SHA, main_root=Path("/tmp/main"))
        published = publish.publish(Refuse(), ws, "t", Path("/tmp/b"), {})
        self.assertFalse(published.ok)


class TestResultLine(unittest.TestCase):
    def test_parsing(self) -> None:
        stream = "\n".join(
            [json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "x"}]}}),
             json.dumps({"type": "result", "result": "Done.\nRESULT: escalate - the database is down"})]
        )
        self.assertEqual(result_line(final_text(stream)), "RESULT: escalate - the database is down")
        self.assertEqual(result_line("text\nRESULT: fixed\n"), "RESULT: fixed")
        self.assertIsNone(result_line("RESULT: fixed\nand more"))
        self.assertIsNone(result_line("RESULT: fixed!"))
        self.assertIsNone(result_line("RESULT: escalate"))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A zombie child of ours would still answer; reap it if it is ours.
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == 0
    except ChildProcessError:
        return _not_zombie(pid)


def _not_zombie(pid: int) -> bool:
    try:
        import subprocess

        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout
    except OSError:
        return True
    return bool(state.strip()) and not state.strip().startswith("Z")


if __name__ == "__main__":
    unittest.main()
