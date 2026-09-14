"""Domain entities (spec 6.1). Plain dataclasses, no framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.domain.enums import (
    AnswerType,
    BetGroupKind,
    BetGroupStatus,
    ParticipationStatus,
    QuestionFamily,
    RoundReached,
    Surface,
    Tour,
    TournamentCategory,
    TournamentStatus,
    TournamentVisibility,
    TypedQuestionKind,
)
from app.domain.predictions import QuestionOutcomePayload


@dataclass(slots=True)
class User:
    id: str
    email: str
    password_hash: str
    display_name: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    email_verified_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Player:
    id: str
    full_name: str
    country_code: str
    tour: Tour


@dataclass(frozen=True, slots=True)
class ScoringProfile:
    """Point values per tournament, editable by the organiser (decision D10)."""

    quarter_finalist_points: int = 1
    semi_finalist_points: int = 2
    finalist_points: int = 3
    champion_points: int = 5
    #: Exit in round 1, 2 and 3 respectively.
    underperformer_points: tuple[int, int, int] = (3, 2, 1)
    #: Reaching R16, QF, SF, F and winning respectively.
    breakout_points: tuple[int, int, int, int, int] = (2, 3, 4, 5, 7)
    featured_match_winner_points: int = 1
    featured_match_set_score_points: int = 1


@dataclass(slots=True)
class Tournament:
    id: str
    name: str
    category: TournamentCategory
    surface: Surface
    location: str
    start_date: date
    end_date: date
    signup_deadline: datetime
    visibility: TournamentVisibility
    join_code: str | None
    status: TournamentStatus
    rules_markdown: str
    created_at: datetime
    scoring_profile: ScoringProfile = field(default_factory=ScoringProfile)


@dataclass(frozen=True, slots=True)
class Draw:
    id: str
    tournament_id: str
    tour: Tour
    draw_size: int
    best_of: int
    official_draw_url: str | None


@dataclass(frozen=True, slots=True)
class DrawSection:
    id: str
    draw_id: str
    index: int


@dataclass(frozen=True, slots=True)
class DrawEntry:
    id: str
    draw_id: str
    section_id: str
    player_id: str
    seed: int | None


@dataclass(frozen=True, slots=True)
class Participation:
    id: str
    user_id: str
    tournament_id: str
    joined_at: datetime
    status: ParticipationStatus


@dataclass(slots=True)
class BetGroup:
    id: str
    tournament_id: str
    kind: BetGroupKind
    round: int | None
    title: str
    intro_markdown: str
    deadline: datetime
    status: BetGroupStatus


@dataclass(frozen=True, slots=True)
class QuestionChoiceOption:
    id: str
    label: str


@dataclass(slots=True)
class Question:
    id: str
    bet_group_id: str
    draw_id: str | None
    family: QuestionFamily
    kind: TypedQuestionKind | None
    prompt: str
    answer_type: AnswerType
    options: tuple[QuestionChoiceOption, ...] | None
    matchup: tuple[str, str] | None
    points_hint: str
    deadline_override: datetime | None
    position: int


@dataclass(slots=True)
class Prediction:
    id: str
    participation_id: str
    question_id: str
    payload: object
    submitted_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OutcomeEntry:
    """One row of the outcome grid (decision D9)."""

    draw_id: str
    player_id: str
    round_reached: RoundReached
    note: str | None


@dataclass(frozen=True, slots=True)
class QuestionOutcome:
    question_id: str
    correct_answer: QuestionOutcomePayload
    settled_at: datetime
    note: str | None


@dataclass(frozen=True, slots=True)
class ScoreEntry:
    """Derived data, rebuildable at any time (AGENTS.md hard rule 7)."""

    id: str
    participation_id: str
    question_id: str
    points: int
    reason: str
    calculated_at: datetime
