"""The responder's only ways out of its own process.

Every external call goes through one of these three seams: an HTTP GET (Loki,
Tempo), a short command (git, gh, uv, docker) and the long-running agent. The
tests replace each with a fake; nothing else in the package starts a process
or opens a socket.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Dict, Mapping, Optional, Sequence


class Unreachable(Exception):
    """An HTTP source did not answer, or answered with something unusable."""


@dataclass(frozen=True)
class CommandResult:
    argv: Sequence[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class AgentExit:
    returncode: Optional[int]
    timed_out: bool


class Http:
    """GET a URL and decode JSON. Raises Unreachable on any failure."""

    def get_json(self, url: str, timeout: float = 10.0) -> Any:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                body = response.read()
        except urllib.error.HTTPError as error:
            raise Unreachable(f"HTTP {error.code} from {_origin(url)}") from error
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise Unreachable(f"no answer from {_origin(url)}: {error}") from error
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise Unreachable(f"not JSON from {_origin(url)}") from error


def _origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


class Commands:
    """Run a short command to completion and capture its output."""

    def run(
        self,
        argv: Sequence[str],
        cwd: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        timeout: float = 600.0,
        discard_stdout: bool = False,
    ) -> CommandResult:
        try:
            done = subprocess.run(
                list(argv),
                cwd=str(cwd) if cwd else None,
                env=dict(env) if env is not None else None,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL if discard_stdout else subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return CommandResult(argv, 127, "", f"{argv[0]}: command not found")
        except subprocess.TimeoutExpired:
            return CommandResult(argv, 124, "", f"{argv[0]}: timed out after {timeout:.0f} s")
        out = "" if discard_stdout else done.stdout.decode("utf-8", "replace")
        return CommandResult(argv, done.returncode, out, done.stderr.decode("utf-8", "replace"))


class AgentLauncher:
    """Start the agent in its own process group; kill the group on time-out."""

    def __init__(self) -> None:
        self._process: Optional[subprocess.Popen] = None  # type: ignore[type-arg]

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            _kill_group(self._process)

    def run(
        self,
        argv: Sequence[str],
        cwd: Path,
        env: Dict[str, str],
        stdin_text: str,
        stdout: IO[bytes],
        stderr: IO[bytes],
        timeout: float,
    ) -> AgentExit:
        try:
            process = subprocess.Popen(
                list(argv),
                cwd=str(cwd),
                env=env,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        except FileNotFoundError:
            stderr.write(f"{argv[0]}: command not found\n".encode())
            return AgentExit(127, False)
        self._process = process
        try:
            assert process.stdin is not None
            process.stdin.write(stdin_text.encode("utf-8"))
            process.stdin.close()
        except BrokenPipeError:
            pass
        try:
            return AgentExit(process.wait(timeout=timeout), False)
        except subprocess.TimeoutExpired:
            _kill_group(process)
            return AgentExit(process.returncode, True)


def _kill_group(process: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """SIGTERM the whole group, then SIGKILL whatever is left of it."""
    for sig, grace in ((signal.SIGTERM, 10.0), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
