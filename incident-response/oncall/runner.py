"""The trigger-neutral run: an Incident in, a pull request or an escalation out.

One run at a time (in memory). A second incident while one runs answers busy;
an incident whose key already has a folder answers duplicate. The run itself
happens in a background thread so the trigger's request returns at once.

Outcomes: published, escalated, agent_failed, timed_out, publish_failed.
Every outcome is written to the incident folder (result.json) and printed.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Callable, Dict, List, Optional, TextIO

from . import context as context_mod
from . import prompt as prompt_mod
from . import publish as publish_mod
from . import workspace as workspace_mod
from .config import Settings
from .folder import IncidentFolder, find_by_key
from .incident import Incident, iso
from .redact import redact, scrub_paths
from .seams import AgentLauncher, Commands, Http

RESULT_LINE = re.compile(r"^RESULT: (fixed|escalate - \S.*)$")

PUBLISHED = "published"
ESCALATED = "escalated"
AGENT_FAILED = "agent_failed"
TIMED_OUT = "timed_out"
PUBLISH_FAILED = "publish_failed"

AGENT_OUTPUT = "agent-output.jsonl"
AGENT_STDERR = "agent-stderr.txt"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Submission:
    status: str  # accepted, busy, duplicate
    incident_id: Optional[str] = None


@dataclass
class RunResult:
    outcome: str
    reason: str
    incident_id: str
    details: Dict[str, Any] = field(default_factory=dict)


def final_text(output: str) -> str:
    """The agent's final message: the `result` of stream-json, else the raw text."""
    last_result: Optional[str] = None
    last_assistant: Optional[str] = None
    json_seen = False
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        json_seen = True
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            last_result = event["result"]
        elif event.get("type") == "assistant":
            content = (event.get("message") or {}).get("content") or []
            texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            if any(t.strip() for t in texts):
                last_assistant = "\n".join(texts)
    if last_result is not None:
        return last_result
    if last_assistant is not None:
        return last_assistant
    return "" if json_seen else output


def result_line(text: str) -> Optional[str]:
    """The RESULT line, if it is the last non-empty line of the final message."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and RESULT_LINE.match(lines[-1]):
        return lines[-1]
    return None


def permission_denials(output: str) -> List[Dict[str, Any]]:
    """What the CLI refused, from its stream-json result event (best effort)."""
    denials: List[Dict[str, Any]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            for item in event.get("permission_denials") or []:
                if isinstance(item, dict):
                    denials.append(
                        {"tool": item.get("tool_name"), "input": item.get("tool_input")}
                    )
    return denials


class Responder:
    def __init__(
        self,
        settings: Settings,
        *,
        http: Optional[Http] = None,
        commands: Optional[Commands] = None,
        agent: Optional[AgentLauncher] = None,
        clock: Callable[[], datetime] = _now,
        out: TextIO = sys.stderr,
    ) -> None:
        self.settings = settings
        self.http = http or Http()
        self.commands = commands or Commands()
        self.agent = agent or AgentLauncher()
        self.clock = clock
        self.out = out
        self._slot = threading.Lock()
        self._state = threading.Lock()
        self._current: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self.last_result: Optional[RunResult] = None

    # -- logging ----------------------------------------------------------------

    def log(self, message: str) -> None:
        line = f"{iso(self.clock())} responder: {message}"
        print(redact(line, self.settings.secrets()), file=self.out, flush=True)

    def _banner(self, result: RunResult, folder: IncidentFolder) -> None:
        bar = "=" * 72
        lines = [
            bar,
            f"ON-CALL RESULT: {result.outcome.upper()}",
            f"incident: {result.incident_id}",
            f"reason:   {result.reason}",
        ]
        if result.details.get("pr_url"):
            lines.append(f"pull request: {result.details['pr_url']}")
        lines += [f"folder:   {folder.path}", bar]
        print(redact("\n".join(lines), self.settings.secrets()), file=self.out, flush=True)

    # -- submission (called by a trigger) ---------------------------------------

    @property
    def current(self) -> Optional[str]:
        with self._state:
            return self._current

    def submit(self, incident: Incident) -> Submission:
        if not self._slot.acquire(blocking=False):
            current = self.current
            self.log(f"busy: run {current} in progress; ignored {incident.title} ({incident.key})")
            return Submission("busy", current)
        try:
            existing = find_by_key(self.settings.incidents_dir, incident.key)
            if existing is not None:
                self.log(f"duplicate: {incident.key} already has {existing.name}; nothing started")
                self._slot.release()
                return Submission("duplicate", existing.name)
            folder = IncidentFolder.create(
                self.settings.incidents_dir, incident, self.settings.secrets()
            )
            folder.write_json("alert.json" if incident.source == "alert" else "trigger.json", incident.raw)
        except BaseException:
            self._slot.release()
            raise
        with self._state:
            self._current = folder.path.name
        self.log(f"accepted: {incident.title} -> incident {folder.path.name}")
        thread = threading.Thread(
            target=self._run_and_release, args=(incident, folder), name=f"run-{folder.path.name}",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        return Submission("accepted", folder.path.name)

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run_and_release(self, incident: Incident, folder: IncidentFolder) -> None:
        try:
            self.run(incident, folder)
        except Exception as error:  # the slot must come free whatever happens
            folder.unlock()
            result = RunResult(ESCALATED, f"the responder failed: {type(error).__name__}: {error}",
                               folder.path.name, {"traceback": traceback.format_exc()})
            self._finish(result, folder)
        finally:
            with self._state:
                self._current = None
            self._slot.release()

    # -- the run ----------------------------------------------------------------

    def run(self, incident: Incident, folder: IncidentFolder) -> RunResult:
        s = self.settings
        tool_env = s.tool_env()
        record: Dict[str, Any] = {"started_at": iso(self.clock())}

        try:
            main_root = workspace_mod.main_worktree(self.commands, s.repo_root, tool_env)
        except workspace_mod.WorkspaceError as error:
            return self._finish(RunResult(ESCALATED, str(error), folder.path.name, record), folder)
        record["hooks_path_before"] = workspace_mod.read_hooks_path(self.commands, main_root, tool_env)

        self.log(f"collecting context for {folder.path.name}")
        ctx = context_mod.collect(
            incident,
            folder,
            http=self.http,
            commands=self.commands,
            loki_url=s.loki_url,
            tempo_url=s.tempo_url,
            service=s.service_name,
            compose_dir=main_root,
            container=s.app_container,
            env=tool_env,
        )
        for source in (ctx.loki, ctx.tempo, ctx.traceback):
            self.log(f"  {source.name}: {source.detail}")
        if not ctx.loki.reachable:
            reason = f"no error logs to diagnose from ({ctx.loki.detail}); no worktree, no agent"
            return self._finish(RunResult(ESCALATED, reason, folder.path.name, record), folder,
                                main_root=main_root)

        mandate = s.mandate_file.read_text(encoding="utf-8")
        files = sorted(set(folder.files()) | {"prompt.txt"})
        prompt = prompt_mod.build(mandate, incident, str(folder.path), ctx, files, s.secrets())
        folder.write("prompt.txt", prompt)

        self.log(f"preparing worktree {incident.branch} from {s.base_ref}")
        try:
            ws = workspace_mod.prepare(
                self.commands,
                repo_root=s.repo_root,
                worktree_root=s.worktree_dir,
                name=folder.path.name,
                branch=incident.branch,
                base_ref=s.base_ref,
                env=tool_env,
            )
        except workspace_mod.WorkspaceError as error:
            record["worktree"] = str(s.worktree_dir / folder.path.name)
            return self._finish(RunResult(ESCALATED, str(error), folder.path.name, record), folder,
                                main_root=main_root)
        record.update(
            {"worktree": str(ws.path), "branch": ws.branch, "base_ref": ws.base_ref, "base_sha": ws.base_sha}
        )
        record["hooks_path_worktree_before"] = workspace_mod.read_hooks_path(self.commands, ws.path, tool_env)
        ctx.extra["workspace"] = {
            "branch": ws.branch,
            "base_ref": ws.base_ref,
            "base_sha": ws.base_sha,
            "hooks_path_resolves_to_worktree_agent_hooks": True,
            "private_patterns": ws.private_patterns,
            "notes": ws.notes,
        }
        folder.write_json("context.json", ctx.as_dict(incident, folder))

        argv = s.agent_argv(folder.path)
        env = s.agent_env()
        folder.write_json(
            "agent-command.json",
            {"argv": argv, "cwd": str(ws.path), "env_names": sorted(env), "timeout_min": s.timeout_min},
        )
        self.log(f"starting the agent in {ws.path} (limit {s.timeout_min:g} min)")
        with open(folder.path / AGENT_OUTPUT, "wb") as stdout, open(folder.path / AGENT_STDERR, "wb") as stderr:
            folder.lock_inputs(keep_writable=(AGENT_OUTPUT, AGENT_STDERR))
            try:
                exit_ = self.agent.run(argv, ws.path, env, prompt, stdout, stderr, s.timeout_seconds)
            finally:
                folder.unlock()
        for name in (AGENT_OUTPUT, AGENT_STDERR):
            folder.redact_in_place(name)
        output = (folder.path / AGENT_OUTPUT).read_text(encoding="utf-8", errors="replace")
        final = final_text(output)
        claim = result_line(final)
        record.update(
            {
                "agent_returncode": exit_.returncode,
                "agent_timed_out": exit_.timed_out,
                "agent_result_line": claim,
                "agent_final_message": final[-4000:],
                "permission_denials": permission_denials(output),
            }
        )
        record["hooks_path_after"] = workspace_mod.read_hooks_path(self.commands, main_root, tool_env)
        record["hooks_path_worktree_after"] = workspace_mod.read_hooks_path(self.commands, ws.path, tool_env)
        hooks_same = (
            record["hooks_path_before"] == record["hooks_path_after"]
            and record["hooks_path_worktree_before"] == record["hooks_path_worktree_after"]
        )
        record["hooks_path_unchanged"] = hooks_same
        folder.write(
            "hooks-path.txt",
            "\n".join(
                [
                    "main checkout, before: " + record["hooks_path_before"],
                    "main checkout, after:  " + record["hooks_path_after"],
                    "worktree, before:      " + record["hooks_path_worktree_before"],
                    "worktree, after:       " + record["hooks_path_worktree_after"],
                    "unchanged: " + ("yes" if hooks_same else "NO"),
                ]
            )
            + "\n",
        )

        def done(outcome: str, reason: str) -> RunResult:
            return self._finish(RunResult(outcome, reason, folder.path.name, record), folder,
                                main_root=main_root, ws=ws)

        if exit_.timed_out:
            return done(TIMED_OUT, f"the agent ran past {s.timeout_min:g} min and was killed")
        if not hooks_same:
            return done(ESCALATED, "core.hooksPath changed during the run; nothing published")
        if exit_.returncode != 0:
            return done(AGENT_FAILED, f"the agent exited with {exit_.returncode}")
        if claim is None:
            return done(AGENT_FAILED, "the agent's final message has no RESULT line")
        if claim.startswith("RESULT: escalate"):
            return done(ESCALATED, "the agent escalated: " + claim[len("RESULT: escalate - "):])

        self.log("the agent claims a fix; checking the repository")
        checks = publish_mod.check(self.commands, ws, env)
        record["checks"] = checks.as_dict()
        if not checks.passed:
            return done(ESCALATED, "the agent claimed a fix, but: " + "; ".join(checks.reasons))

        title = f"fix(oncall): {incident.title}" + (f" on {incident.endpoint}" if incident.endpoint else "")
        body = self._render_pr_body(incident, folder, ws, checks, claim, main_root)
        body_file = folder.write("pr-body.md", body)
        published = publish_mod.publish(self.commands, ws, title, body_file, tool_env)
        record["publish"] = {"log": published.log, "url": published.url}
        if not published.ok:
            return done(PUBLISH_FAILED, published.reason)
        record["pr_url"] = published.url
        return done(PUBLISHED, "fixed, checked by the responder, pushed, pull request opened")

    def _render_pr_body(
        self,
        incident: Incident,
        folder: IncidentFolder,
        ws: workspace_mod.Workspace,
        checks: publish_mod.Checks,
        claim: str,
        main_root: Path,
    ) -> str:
        template = Template(self.settings.pr_template.read_text(encoding="utf-8"))
        facts = dict(incident.facts)
        bullet = lambda items: "\n".join(f"- `{i}`" for i in items) or "- (none)"  # noqa: E731
        body = template.safe_substitute(
            title=incident.title,
            source=incident.source,
            endpoint=incident.endpoint or "(not given)",
            starts_at=facts.get("startsAt", "(not given)"),
            window=facts.get("annotation.window", "(not given)"),
            summary=facts.get("annotation.summary", "(not given)"),
            fingerprint=facts.get("fingerprint", "(not given)"),
            incident_id=folder.path.name,
            branch=ws.branch,
            base=publish_mod.pr_base(ws.base_ref),
            result_line=claim,
            commits=bullet(checks.commits),
            files=bullet(checks.changed),
            tests=bullet(checks.tests),
            pytest_tail=checks.pytest_tail.splitlines()[-1] if checks.pytest_tail else "(no output)",
        )
        home = self.settings.environ.get("HOME", "")
        body = scrub_paths(
            body,
            [
                (str(folder.path), "<incident folder>"),
                (str(ws.path), "<worktree>"),
                (str(main_root), "<checkout>"),
                (home, "~"),
            ],
        )
        return redact(body, self.settings.secrets())

    def _finish(
        self,
        result: RunResult,
        folder: IncidentFolder,
        main_root: Optional[Path] = None,
        ws: Optional[workspace_mod.Workspace] = None,
    ) -> RunResult:
        details = dict(result.details)
        details["finished_at"] = iso(self.clock())
        if main_root is not None and "hooks_path_after" not in details:
            details["hooks_path_after"] = workspace_mod.read_hooks_path(
                self.commands, main_root, self.settings.tool_env()
            )
        payload = {"outcome": result.outcome, "reason": result.reason, "incident": result.incident_id}
        payload.update(details)
        folder.write_json("result.json", payload)
        result = RunResult(result.outcome, result.reason, result.incident_id, details)
        self.last_result = result
        self._banner(result, folder)
        return result

