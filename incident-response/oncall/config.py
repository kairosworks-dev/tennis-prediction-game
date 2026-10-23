"""Settings, read once from the environment.

Every value has a loopback or temp-directory default except the shared secret
RESPONDER_TOKEN, without which the responder refuses to start. The defaults are
small, named constants so that each choice is one line to change.
"""

from __future__ import annotations

import os
import shlex
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

#: The responder only ever listens here: it starts an agent that edits the
#: repository, so nothing beyond this machine may reach it. Not configurable.
HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_LOKI_URL = "http://127.0.0.1:3100"
DEFAULT_TEMPO_URL = "http://127.0.0.1:3200"
DEFAULT_SERVICE_NAME = "tennis-prediction-game"
DEFAULT_BASE_REF = "origin/main"
DEFAULT_TIMEOUT_MIN = 20.0
MIN_TOKEN_LENGTH = 16
REMOTE = "origin"
PR_LABEL = "on-call-agent"

#: Claude Code's print mode, flags checked against `claude --help` (2.1.303).
#: {settings} and {incident_dir} are filled in per run. The prompt goes on stdin.
#: --setting-sources project,local keeps the author's user-level settings (and
#: any allow rules in them) out of the agent's run; the project settings stay,
#: because they wire the commit gate's pre-tool door.
DEFAULT_AGENT_CMD = (
    "claude -p --settings {settings} --add-dir {incident_dir}"
    " --setting-sources project,local"
    " --permission-mode dontAsk --permission-prompts none"
    " --output-format stream-json --verbose --no-session-persistence --strict-mcp-config"
)

#: Flags that would switch a guardrail off: hooks (the commit gate's door),
#: project settings, or permission checks. A command naming one is refused.
FORBIDDEN_AGENT_FLAGS = (
    "--bare",
    "--restricted",
    "--safe-mode",
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "bypassPermissions",
)

#: The agent's environment is this allow-list (plus RESPONDER_AGENT_ENV_EXTRA).
AGENT_ENV_ALLOW = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "TERM", "TMPDIR")
AGENT_ENV_FIXED = {"UV_OFFLINE": "1"}
#: Never handed to the agent, whatever the extra list says.
AGENT_ENV_NEVER = ("RESPONDER_TOKEN",)

#: The checkout this code lives in: incident-response/oncall/config.py -> root.
CODE_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    """A setting the responder cannot start with."""


@dataclass(frozen=True)
class Settings:
    token: str
    port: int = DEFAULT_PORT
    loki_url: str = DEFAULT_LOKI_URL
    tempo_url: str = DEFAULT_TEMPO_URL
    service_name: str = DEFAULT_SERVICE_NAME
    app_container: Optional[str] = None
    repo_root: Path = CODE_ROOT
    incidents_dir: Path = CODE_ROOT / "incident-response" / "incidents"
    worktree_dir: Path = Path(tempfile.gettempdir()) / "tennis-oncall-worktrees"
    base_ref: str = DEFAULT_BASE_REF
    agent_cmd: str = DEFAULT_AGENT_CMD
    agent_env_extra: Tuple[str, ...] = ()
    timeout_min: float = DEFAULT_TIMEOUT_MIN
    #: The environment the responder was started with; the agent gets a subset.
    environ: Mapping[str, str] = field(default_factory=dict)

    @property
    def responder_dir(self) -> Path:
        return self.repo_root / "incident-response"

    @property
    def settings_file(self) -> Path:
        return self.responder_dir / "agent-settings.json"

    @property
    def mandate_file(self) -> Path:
        return self.responder_dir / "mandate.md"

    @property
    def pr_template(self) -> Path:
        return self.responder_dir / "pr-body.md"

    @property
    def timeout_seconds(self) -> float:
        return self.timeout_min * 60.0

    def agent_argv(self, incident_dir: Path) -> List[str]:
        """The agent command, split like a shell would, placeholders filled."""
        values = {"{settings}": str(self.settings_file), "{incident_dir}": str(incident_dir)}
        parts = []
        for part in shlex.split(self.agent_cmd):
            for placeholder, value in values.items():  # plain replace: other braces stay
                part = part.replace(placeholder, value)
            parts.append(part)
        return parts

    def agent_env(self) -> Dict[str, str]:
        names = list(AGENT_ENV_ALLOW) + [n for n in self.agent_env_extra if n]
        env = {n: self.environ[n] for n in names if n in self.environ and n not in AGENT_ENV_NEVER}
        env.update(AGENT_ENV_FIXED)
        return env

    def tool_env(self) -> Dict[str, str]:
        """The environment for the responder's own git, gh, uv and docker calls."""
        return {k: v for k, v in self.environ.items() if k not in AGENT_ENV_NEVER}

    def secrets(self) -> Tuple[str, ...]:
        """Values that must never be written anywhere."""
        return (self.token,) if self.token else ()


def check_agent_cmd(cmd: str) -> None:
    try:
        parts = shlex.split(cmd)
    except ValueError as error:
        raise ConfigError(f"RESPONDER_AGENT_CMD cannot be parsed: {error}") from error
    if not parts:
        raise ConfigError("RESPONDER_AGENT_CMD is empty.")
    for part in parts:
        for flag in FORBIDDEN_AGENT_FLAGS:
            if part == flag or part.startswith(flag + "=") or part.endswith(flag):
                raise ConfigError(
                    f"RESPONDER_AGENT_CMD names {flag}, which switches a guardrail off "
                    "(hooks, project settings or permission checks). Refusing to start."
                )


def load(environ: Optional[Mapping[str, str]] = None) -> Settings:
    env = dict(os.environ if environ is None else environ)

    token = env.get("RESPONDER_TOKEN", "")
    if not token:
        raise ConfigError(
            "RESPONDER_TOKEN is not set. The responder refuses to start without it. "
            "Generate one with `openssl rand -hex 32`, export it here and in the shell "
            "that starts Grafana."
        )
    if len(token) < MIN_TOKEN_LENGTH:
        raise ConfigError(f"RESPONDER_TOKEN must be at least {MIN_TOKEN_LENGTH} characters.")

    try:
        port = int(env.get("RESPONDER_PORT", "") or DEFAULT_PORT)
    except ValueError as error:
        raise ConfigError("RESPONDER_PORT must be a number.") from error
    if not 1 <= port <= 65535:
        raise ConfigError("RESPONDER_PORT must be between 1 and 65535.")

    try:
        timeout_min = float(env.get("RESPONDER_TIMEOUT_MIN", "") or DEFAULT_TIMEOUT_MIN)
    except ValueError as error:
        raise ConfigError("RESPONDER_TIMEOUT_MIN must be a number of minutes.") from error
    if timeout_min <= 0:
        raise ConfigError("RESPONDER_TIMEOUT_MIN must be positive.")

    agent_cmd = env.get("RESPONDER_AGENT_CMD", "") or DEFAULT_AGENT_CMD
    check_agent_cmd(agent_cmd)

    repo_root = CODE_ROOT
    incidents = env.get("RESPONDER_INCIDENTS_DIR")
    worktrees = env.get("RESPONDER_WORKTREE_DIR")
    extra = tuple(n for n in env.get("RESPONDER_AGENT_ENV_EXTRA", "").replace(",", " ").split() if n)

    return Settings(
        token=token,
        port=port,
        loki_url=(env.get("LOKI_URL") or DEFAULT_LOKI_URL).rstrip("/"),
        tempo_url=(env.get("TEMPO_URL") or DEFAULT_TEMPO_URL).rstrip("/"),
        service_name=env.get("RESPONDER_SERVICE_NAME") or DEFAULT_SERVICE_NAME,
        app_container=env.get("RESPONDER_APP_CONTAINER") or None,
        repo_root=repo_root,
        incidents_dir=Path(incidents).resolve()
        if incidents
        else repo_root / "incident-response" / "incidents",
        worktree_dir=Path(worktrees).resolve()
        if worktrees
        else Path(tempfile.gettempdir()) / "tennis-oncall-worktrees",
        base_ref=env.get("RESPONDER_BASE_REF") or DEFAULT_BASE_REF,
        agent_cmd=agent_cmd,
        agent_env_extra=extra,
        timeout_min=timeout_min,
        environ=env,
    )
