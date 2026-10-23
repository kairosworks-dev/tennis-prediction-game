"""Fakes for the three seams, and a throwaway layout for each test.

FakeHttp answers Loki and Tempo from canned bodies. FakeCommands records every
git, gh, uv and docker command and answers like a small scripted repository
(Scenario). The agent is a real subprocess, tests/fake_agent.py, started
through the real AgentLauncher, so argv, cwd, environment, stdin, the
time-out and the process-group kill are exercised for real.
"""

from __future__ import annotations

import json
import shlex
import shutil
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from oncall import config
from oncall.seams import CommandResult, Unreachable

HERE = Path(__file__).resolve().parent
RESPONDER = HERE.parent
FIXTURES = HERE / "fixtures"
FAKE_AGENT = HERE / "fake_agent.py"
#: A shared secret for tests only; built, so no assignment looks like a secret.
TEST_BEARER = "unit-test-" + "x" * 24
FIXED_NOW = datetime(2026, 10, 23, 10, 15, 0, tzinfo=timezone.utc)
SHA = "0123456789abcdef0123456789abcdef01234567"


def fixture(name: str) -> Dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def loki_body(lines: List[Any]) -> Dict[str, Any]:
    """A Loki query_range answer with one stream; each item is (ts_ns, line[, metadata])."""
    return {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {"service_name": "tennis-prediction-game"},
                    "values": [list(item) for item in lines],
                }
            ],
        },
    }


DEFAULT_LOKI_LINES = [
    (
        "1792750460000000000",
        "unhandled exception",
        {"severity_text": "ERROR", "exception_type": "IndexError", "trace_id": "01a4b234f394acc0093da023133ec03c"},
    ),
    (
        "1792750460100000000",
        "request completed",
        {
            "http_route": "/api/tournaments/{tournament_id}/questions/{question_id}/prediction",
            "http_request_method": "PUT",
            "http_response_status_code": "500",
            "trace_id": "01a4b234f394acc0093da023133ec03c",
        },
    ),
]

DEFAULT_TRACE = {
    "batches": [
        {
            "resource": {"attributes": []},
            "scopeSpans": [
                {
                    "spans": [
                        {
                            "traceId": "AaSyNPOUrMAJPaAjEz7APA==",
                            "name": "PUT /api/tournaments/{tournament_id}/questions/{question_id}/prediction",
                            "startTimeUnixNano": "1792750460000000000",
                            "endTimeUnixNano": "1792750460000800000",
                            "attributes": [
                                {"key": "http.route", "value": {"stringValue": "/api/tournaments/{tournament_id}/questions/{question_id}/prediction"}},
                                {"key": "http.response.status_code", "value": {"intValue": "500"}},
                                {"key": "url.path", "value": {"stringValue": "/api/tournaments/x/questions/y/prediction"}},
                            ],
                            "status": {"code": "STATUS_CODE_ERROR"},
                            "events": [
                                {"name": "exception", "attributes": [{"key": "exception.type", "value": {"stringValue": "IndexError"}}]}
                            ],
                        }
                    ]
                }
            ],
        }
    ]
}

DEFAULT_STDERR = """INFO:     Application startup complete.
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "/app/backend/app/services/play.py", line 177, in put_prediction
    validate_prediction(payload, self._validation_context(question, participation_id))
  File "/app/backend/app/domain/validation.py", line 197, in validate_prediction
    opponent_id = tie[tie.index(winner_id) + 1]
IndexError: tuple index out of range
"""


class FakeHttp:
    def __init__(self, loki: Any = None, tempo_search: Any = None, traces: Optional[Dict[str, Any]] = None,
                 loki_down: bool = False, tempo_down: bool = False) -> None:
        self.loki = loki if loki is not None else loki_body(DEFAULT_LOKI_LINES)
        self.tempo_search = tempo_search if tempo_search is not None else {"traces": []}
        self.traces = traces if traces is not None else {"01a4b234f394acc0093da023133ec03c": DEFAULT_TRACE}
        self.loki_down = loki_down
        self.tempo_down = tempo_down
        self.urls: List[str] = []

    def get_json(self, url: str, timeout: float = 10.0) -> Any:
        self.urls.append(url)
        if "/loki/" in url:
            if self.loki_down:
                raise Unreachable("no answer from http://127.0.0.1:3100: connection refused")
            return self.loki
        if self.tempo_down:
            raise Unreachable("no answer from http://127.0.0.1:3200: connection refused")
        if "/api/search" in url:
            return self.tempo_search
        trace_id = url.rsplit("/", 1)[-1]
        if trace_id in self.traces:
            return self.traces[trace_id]
        raise Unreachable("HTTP 404 from http://127.0.0.1:3200")


@dataclass
class Scenario:
    """How the scripted repository answers. Defaults: a clean, publishable fix."""

    hooks_path: str = "agent-hooks"
    commits: List[str] = field(default_factory=lambda: ["abc1234 fix: pick the other player of the tie"])
    changed: List[str] = field(
        default_factory=lambda: ["backend/app/domain/validation.py", "backend/tests/test_oncall_regression.py"]
    )
    added_or_modified: Optional[List[str]] = None
    status: List[str] = field(default_factory=list)
    pytest_rc: int = 0
    push_rc: int = 0
    gh_rc: int = 0
    uv_sync_rc: int = 0
    base_exists: bool = True
    hooks_change_after_agent: bool = False
    container: str = "c0ffee"
    docker_rc: int = 0
    stderr_text: str = DEFAULT_STDERR
    on_branch: Optional[str] = None


class FakeCommands:
    def __init__(self, main_root: Path, scenario: Optional[Scenario] = None) -> None:
        self.main_root = main_root
        self.scenario = scenario or Scenario()
        self.calls: List[Dict[str, Any]] = []
        self.hooks_reads = 0
        self.worktrees: List[Path] = []
        self.branch: Optional[str] = None

    def _ok(self, argv, out: str = "", err: str = "", rc: int = 0) -> CommandResult:
        return CommandResult(list(argv), rc, out, err)

    def run(self, argv, cwd=None, env=None, timeout=600.0, discard_stdout=False) -> CommandResult:
        argv = list(argv)
        self.calls.append({"argv": argv, "cwd": str(cwd) if cwd else None, "env": dict(env or {})})
        sc = self.scenario
        if argv[0] == "git":
            where, rest = Path(argv[2]), argv[3:]
            return self._git(argv, where, rest)
        if argv[:2] == ["uv", "sync"]:
            return self._ok(argv, rc=sc.uv_sync_rc, err="" if sc.uv_sync_rc == 0 else "uv: resolution failed")
        if argv[:3] == ["uv", "run", "pytest"]:
            out = "300 passed" if sc.pytest_rc == 0 else "1 failed, 299 passed"
            return self._ok(argv, out=out, rc=sc.pytest_rc)
        if argv[:3] == ["gh", "pr", "create"]:
            out = "https://github.com/OWNER/REPO/pull/99\n" if sc.gh_rc == 0 else ""
            return self._ok(argv, out=out, rc=sc.gh_rc, err="" if sc.gh_rc == 0 else "label not found")
        if argv[:2] == ["docker", "compose"]:
            return self._ok(argv, out=sc.container + "\n" if sc.container else "", rc=sc.docker_rc,
                            err="" if sc.docker_rc == 0 else "Cannot connect to the Docker daemon")
        if argv[:2] == ["docker", "logs"]:
            return self._ok(argv, out="", err=sc.stderr_text, rc=sc.docker_rc)
        return self._ok(argv, rc=127, err=f"{argv[0]}: not scripted")

    def _git(self, argv, where: Path, rest: List[str]) -> CommandResult:
        sc = self.scenario
        if rest == ["rev-parse", "--path-format=absolute", "--git-common-dir"]:
            return self._ok(argv, out=str(self.main_root / ".git") + "\n")
        if rest[:2] == ["config", "--show-origin"]:
            # Read before the agent (main, worktree), then after it (main, worktree).
            self.hooks_reads += 1
            value = sc.hooks_path
            if sc.hooks_change_after_agent and self.hooks_reads > 2:
                value = "somewhere-else"
            return self._ok(argv, out=f"local\tfile:.git/config\t{value}\n")
        if rest[:3] == ["rev-parse", "--verify", "--quiet"]:
            return self._ok(argv, out=SHA + "\n" if sc.base_exists else "", rc=0 if sc.base_exists else 1)
        if rest[:2] == ["worktree", "add"]:
            path = Path(rest[rest.index("-b") + 2])
            self.branch = rest[rest.index("-b") + 1]
            (path / "agent-hooks").mkdir(parents=True)
            (path / "backend" / "tests").mkdir(parents=True)
            self.worktrees.append(path)
            return self._ok(argv)
        if rest == ["config", "--type=path", "--get", "core.hooksPath"]:
            return self._ok(argv, out=sc.hooks_path + "\n" if sc.hooks_path else "", rc=0 if sc.hooks_path else 1)
        if rest == ["rev-parse", "--show-toplevel"]:
            return self._ok(argv, out=str(where) + "\n")
        if rest[:1] == ["symbolic-ref"]:
            return self._ok(argv, out=(sc.on_branch or self.branch or "") + "\n")
        if rest[:1] == ["log"]:
            return self._ok(argv, out="\n".join(sc.commits) + "\n")
        if rest[:1] == ["diff"]:
            if "--diff-filter=AM" in rest:
                items = sc.added_or_modified if sc.added_or_modified is not None else sc.changed
            else:
                items = sc.changed
            return self._ok(argv, out="\n".join(items) + "\n")
        if rest[:1] == ["status"]:
            return self._ok(argv, out="\n".join(sc.status) + ("\n" if sc.status else ""))
        if rest[:1] == ["push"]:
            return self._ok(argv, rc=sc.push_rc, err="" if sc.push_rc == 0 else "rejected")
        return self._ok(argv, rc=1, err="git: not scripted")

    # -- what the tests ask --------------------------------------------------

    def argvs(self) -> List[List[str]]:
        return [c["argv"] for c in self.calls]

    def ran(self, predicate: Callable[[List[str]], bool]) -> bool:
        return any(predicate(a) for a in self.argvs())


class Layout(unittest.TestCase):
    """A temp directory with a stand-in main checkout, incidents and worktrees."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="oncall-test-")).resolve()
        self.addCleanup(self._cleanup)
        self.main = self.tmp / "main"
        (self.main / "agent-hooks").mkdir(parents=True)
        (self.main / ".git").mkdir()
        responder = self.main / "incident-response"
        responder.mkdir()
        for name in ("agent-settings.json", "mandate.md", "pr-body.md"):
            shutil.copy(RESPONDER / name, responder / name)
        self.incidents = responder / "incidents"
        self.worktrees = self.tmp / "worktrees"
        self.record = self.tmp / "agent-record.json"

    def _cleanup(self) -> None:
        for path in self.tmp.rglob("*"):
            try:
                path.chmod(0o755 if path.is_dir() else 0o644)
            except OSError:
                pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def agent_cmd(self, result: str = "RESULT: fixed", extra: str = "") -> str:
        parts = [sys.executable, str(FAKE_AGENT), "--record", str(self.record)]
        if result:
            parts += ["--result", result]
        return " ".join(shlex.quote(p) for p in parts) + (" " + extra if extra else "") + (
            " -p --settings {settings} --add-dir {incident_dir} --permission-mode dontAsk"
            " --permission-prompts none --output-format stream-json"
        )

    def settings(self, **overrides: Any) -> config.Settings:
        environ = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.tmp / "home"),
            "USER": "tester",
            "LANG": "C.UTF-8",
            "TMPDIR": str(self.tmp),
            "RESPONDER_TOKEN": TEST_BEARER,
            "GH_TOKEN": "must-not-reach-the-agent",
            "SSH_AUTH_SOCK": "must-not-reach-the-agent",
        }
        environ.update(overrides.pop("environ", {}))
        values = dict(
            token=TEST_BEARER,
            repo_root=self.main,
            incidents_dir=self.incidents,
            worktree_dir=self.worktrees,
            base_ref="demo/oncall-fault",
            agent_cmd=self.agent_cmd(),
            timeout_min=1.0,
            environ=environ,
        )
        values.update(overrides)
        return config.Settings(**values)

    def agent_record(self) -> Optional[Dict[str, Any]]:
        if not self.record.exists():
            return None
        return json.loads(self.record.read_text(encoding="utf-8"))

    def incident_folders(self) -> List[Path]:
        return sorted(p for p in self.incidents.iterdir()) if self.incidents.exists() else []

    def assert_nothing_started(self, commands: FakeCommands) -> None:
        """No incident folder, no worktree, no branch, no agent process."""
        self.assertEqual(self.incident_folders(), [])
        self.assertFalse(self.worktrees.exists() and any(self.worktrees.iterdir()))
        self.assertFalse(commands.ran(lambda a: "worktree" in a or "branch" in a))
        self.assertIsNone(self.agent_record())
