"""The trigger-neutral incident: what any trigger hands the runner.

The alert webhook (alerts.py) is one way to make an Incident; a red CI run
(#16) can be another. Nothing below knows about Grafana.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

SLUG_MAX = 40


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:SLUG_MAX].rstrip("-")) or "incident"


def utc_stamp(moment: datetime) -> str:
    """20261022T173750Z: sorts, and is safe in a folder or branch name."""
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Incident:
    #: How the same incident is recognised again (one run per incident).
    key: str
    #: Where it came from, for the record: "alert", later "ci".
    source: str
    #: A short human name: the alert name, the failing job.
    title: str
    received_at: datetime
    #: The affected endpoint, when the trigger knows one.
    endpoint: Optional[str] = None
    #: The time window to collect evidence for, when the trigger has one.
    window: Optional[Tuple[datetime, datetime]] = None
    #: Allow-listed, short facts for the prompt: (name, value) pairs.
    facts: Tuple[Tuple[str, str], ...] = ()
    #: The trigger's original body, saved as received (redacted), never sent as is.
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def id(self) -> str:
        """The incident folder's name: UTC time, then the slug."""
        return f"{utc_stamp(self.received_at)}-{self.slug}"

    @property
    def branch(self) -> str:
        return f"oncall/{self.slug}-{utc_stamp(self.received_at)}"


BRANCH_PATTERN = re.compile(rf"^oncall/[a-z0-9][a-z0-9-]{{0,{SLUG_MAX - 1}}}-\d{{8}}T\d{{6}}Z$")
