"""One folder per incident, under incident-response/incidents/ (gitignored).

Every write goes through `write`, which redacts. The folder also answers "has
this incident been seen before?", so one incident gets one run even across a
restart of the responder.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Iterable, List, Optional

from .incident import Incident, iso
from .redact import redact, redact_data

MARKER = "incident.json"


class IncidentFolder:
    def __init__(self, path: Path, secrets: Iterable[str] = ()) -> None:
        self.path = path
        self._secrets = tuple(secrets)

    @classmethod
    def create(cls, root: Path, incident: Incident, secrets: Iterable[str] = ()) -> IncidentFolder:
        root.mkdir(parents=True, exist_ok=True)
        path = root / incident.id
        suffix = 1
        while True:
            try:
                path.mkdir()
                break
            except FileExistsError:
                suffix += 1
                path = root / f"{incident.id}-{suffix}"
        folder = cls(path, secrets)
        folder.write_json(
            MARKER,
            {
                "id": path.name,
                "key": incident.key,
                "source": incident.source,
                "title": incident.title,
                "received_at": iso(incident.received_at),
                "endpoint": incident.endpoint,
                "window": [iso(incident.window[0]), iso(incident.window[1])]
                if incident.window
                else None,
                "branch": incident.branch,
            },
        )
        return folder

    def write(self, name: str, text: str) -> Path:
        target = self.path / name
        target.write_text(redact(text, self._secrets), encoding="utf-8")
        return target

    def write_json(self, name: str, data: Any) -> Path:
        """Redacted value by value, then serialised: always valid JSON."""
        target = self.path / name
        clean = redact_data(json.loads(json.dumps(data, default=str)), self._secrets)
        target.write_text(json.dumps(clean, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return target

    def redact_in_place(self, name: str) -> None:
        """For the agent's output: a line that is JSON is redacted value by value
        and stays JSON; any other line is redacted as text."""
        target = self.path / name
        if not target.is_file():
            return
        lines = []
        for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                parsed = json.loads(line) if line.lstrip().startswith(("{", "[")) else None
            except ValueError:
                parsed = None
            if parsed is None:
                lines.append(redact(line, self._secrets))
            else:
                lines.append(json.dumps(redact_data(parsed, self._secrets)))
        target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def files(self) -> List[str]:
        return sorted(p.name for p in self.path.iterdir() if p.is_file())

    def lock_inputs(self, keep_writable: Iterable[str] = ()) -> None:
        """Make the evidence read-only for the agent's run: files 0444, folder 0555."""
        keep = set(keep_writable)
        for item in self.path.iterdir():
            if item.is_file() and item.name not in keep:
                item.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        self.path.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)

    def unlock(self) -> None:
        """The folder writable again for the responder's own results (files stay 0444)."""
        self.path.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)


def find_by_key(root: Path, key: str) -> Optional[Path]:
    if not root.is_dir():
        return None
    for entry in sorted(root.iterdir()):
        marker = entry / MARKER
        if not marker.is_file():
            continue
        try:
            if json.loads(marker.read_text(encoding="utf-8")).get("key") == key:
                return entry
        except (OSError, ValueError):
            continue
    return None


def is_writable(path: Path) -> bool:
    return os.access(str(path), os.W_OK)
