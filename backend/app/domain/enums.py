"""Enumerations from spec section 6.3.

No framework imports anywhere in `domain/` (AGENTS.md hard rule 4).
"""

from enum import StrEnum


class TournamentCategory(StrEnum):
    GRAND_SLAM = "GRAND_SLAM"
    ATP = "ATP"
    WTA = "WTA"


class Tour(StrEnum):
    ATP = "ATP"
    WTA = "WTA"


class Surface(StrEnum):
    HARD = "HARD"
    CLAY = "CLAY"
    GRASS = "GRASS"
    INDOOR_HARD = "INDOOR_HARD"


class RoundReached(StrEnum):
    """How far a player advanced. `WITHDREW` sits outside the order."""

    R128 = "R128"
    R64 = "R64"
    R32 = "R32"
    R16 = "R16"
    QF = "QF"
    SF = "SF"
    F = "F"
    CHAMPION = "CHAMPION"
    WITHDREW = "WITHDREW"


#: Earliest exit first. A later index means a deeper run.
ADVANCEMENT_ORDER: tuple[RoundReached, ...] = (
    RoundReached.R128,
    RoundReached.R64,
    RoundReached.R32,
    RoundReached.R16,
    RoundReached.QF,
    RoundReached.SF,
    RoundReached.F,
    RoundReached.CHAMPION,
)


def round_rank(round_reached: RoundReached | None) -> int:
    """Position in the advancement order. A withdrawal never advanced."""
    if round_reached is None or round_reached is RoundReached.WITHDREW:
        return -1
    return ADVANCEMENT_ORDER.index(round_reached)


class TournamentStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


class TournamentVisibility(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"


class BetGroupKind(StrEnum):
    TOURNAMENT = "TOURNAMENT"
    ROUND = "ROUND"


class BetGroupStatus(StrEnum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    LOCKED = "LOCKED"
    SETTLED = "SETTLED"


class QuestionFamily(StrEnum):
    TYPED = "TYPED"
    GENERIC = "GENERIC"


class TypedQuestionKind(StrEnum):
    QF_PICKS = "QF_PICKS"
    SF_PICKS = "SF_PICKS"
    FINALIST_PICKS = "FINALIST_PICKS"
    CHAMPION = "CHAMPION"
    UNDERPERFORMER = "UNDERPERFORMER"
    BREAKOUT = "BREAKOUT"


class AnswerType(StrEnum):
    PLAYER = "PLAYER"
    MATCH_RESULT = "MATCH_RESULT"
    INTEGER = "INTEGER"
    CHOICE = "CHOICE"


class ParticipationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"


class GameListState(StrEnum):
    OPEN_FOR_SIGNUP = "OPEN_FOR_SIGNUP"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"


#: Legal set scores per match format (spec 5.3).
SET_SCORES_BEST_OF_THREE: tuple[str, ...] = ("2-0", "2-1")
SET_SCORES_BEST_OF_FIVE: tuple[str, ...] = ("3-0", "3-1", "3-2")


def legal_set_scores(best_of: int) -> tuple[str, ...]:
    """The results a match of this format can actually end in."""
    return SET_SCORES_BEST_OF_THREE if best_of == 3 else SET_SCORES_BEST_OF_FIVE
