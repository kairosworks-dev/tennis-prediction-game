"""The current time behind an interface (AGENTS.md hard rule 6).

Whether a bet group is still open depends on "now", and a rule that reads the
wall clock cannot be tested on either side of a deadline. Services take a
`Clock`; the domain takes the instant it returns as an argument.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """The current instant, timezone-aware, in UTC."""


class SystemClock(Clock):
    """The real clock. The only implementation the running app uses."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """A clock that stands still until told otherwise, for tests."""

    def __init__(self, instant: datetime) -> None:
        self._instant = self._utc(instant)

    @staticmethod
    def _utc(instant: datetime) -> datetime:
        if instant.tzinfo is None:
            raise ValueError("A FixedClock needs a timezone-aware instant.")
        return instant.astimezone(UTC)

    def now(self) -> datetime:
        return self._instant

    def set(self, instant: datetime) -> None:
        self._instant = self._utc(instant)

    def advance(self, delta: timedelta) -> None:
        self._instant += delta
