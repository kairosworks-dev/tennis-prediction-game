"""Prediction payloads, as a tagged union keyed on question kind.

The same discriminated union the frontend declares and `openapi.yaml`
documents. Plain dataclasses, no Pydantic — `domain/` imports no framework
(AGENTS.md hard rule 4), and the API layer converts at its own boundary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SectionPick:
    """One quarter-finalist pick, bound to the section it answers for."""

    section_index: int
    player_id: str


@dataclass(frozen=True, slots=True)
class QuarterFinalPicks:
    picks: tuple[SectionPick, ...]
    kind: str = "QF_PICKS"

    @property
    def player_ids(self) -> tuple[str, ...]:
        return tuple(pick.player_id for pick in self.picks)


@dataclass(frozen=True, slots=True)
class SemiFinalPicks:
    player_ids: tuple[str, ...]
    kind: str = "SF_PICKS"


@dataclass(frozen=True, slots=True)
class FinalistPicks:
    player_ids: tuple[str, ...]
    kind: str = "FINALIST_PICKS"


@dataclass(frozen=True, slots=True)
class ChampionPick:
    player_id: str
    kind: str = "CHAMPION"


@dataclass(frozen=True, slots=True)
class UnderperformerPick:
    player_id: str
    kind: str = "UNDERPERFORMER"


@dataclass(frozen=True, slots=True)
class BreakoutPick:
    player_id: str
    kind: str = "BREAKOUT"


@dataclass(frozen=True, slots=True)
class GenericPlayer:
    player_id: str
    kind: str = "GENERIC_PLAYER"


@dataclass(frozen=True, slots=True)
class GenericMatchResult:
    winner_id: str
    set_score: str
    kind: str = "GENERIC_MATCH_RESULT"


@dataclass(frozen=True, slots=True)
class GenericInteger:
    value: int
    kind: str = "GENERIC_INTEGER"


@dataclass(frozen=True, slots=True)
class GenericChoice:
    option_id: str
    kind: str = "GENERIC_CHOICE"


PredictionPayload = (
    QuarterFinalPicks
    | SemiFinalPicks
    | FinalistPicks
    | ChampionPick
    | UnderperformerPick
    | BreakoutPick
    | GenericPlayer
    | GenericMatchResult
    | GenericInteger
    | GenericChoice
)

#: A settled answer takes the same shape as the prediction it is compared with.
QuestionOutcomePayload = PredictionPayload
