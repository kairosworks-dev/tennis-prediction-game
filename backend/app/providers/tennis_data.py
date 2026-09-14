"""Tennis data behind an interface (decisions D1 and D2).

There is no free, reliable, open tennis draw and results API, so the MVP does
not depend on one: admin-entered data is the source of truth and a vendor
adapter would only ever be an accelerator. `ManualTennisDataProvider` is the
only implementation the MVP requires (spec 7.4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities import DrawEntry, OutcomeEntry
from app.repositories.interfaces import Repositories


class TennisDataProvider(ABC):
    @abstractmethod
    def draw_entries(self, draw_id: str) -> list[DrawEntry]: ...

    @abstractmethod
    def outcomes(self, draw_id: str) -> list[OutcomeEntry]: ...


class ManualTennisDataProvider(TennisDataProvider):
    """Reads what the organiser entered. Cannot be rate-limited or deprecated."""

    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def draw_entries(self, draw_id: str) -> list[DrawEntry]:
        return self._repos.draws.list_entries(draw_id)

    def outcomes(self, draw_id: str) -> list[OutcomeEntry]:
        return self._repos.outcomes.list_for_draw(draw_id)
