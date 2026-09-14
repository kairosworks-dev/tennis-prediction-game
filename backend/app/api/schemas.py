"""Request and response schemas.

These are the wire format, and they must agree with `openapi.yaml` — from this
step a CI check fails on drift. Field names are camelCase to match the
contract; the domain keeps snake_case and the conversion happens here, at the
boundary, so `domain/` never learns about JSON.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.domain.enums import (
    AnswerType,
    BetGroupKind,
    BetGroupStatus,
    GameListState,
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


class Schema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


class Problem(BaseModel):
    """RFC 7807 problem details."""

    type: str
    title: str
    status: int
    detail: str
    errors: dict[str, list[str]] | None = None


# --- prediction payloads, discriminated on `kind` (spec 6.2) ---


class SectionPickSchema(Schema):
    section_index: int = Field(ge=1, le=8)
    player_id: str


class QuarterFinalPicksSchema(Schema):
    kind: Literal["QF_PICKS"] = "QF_PICKS"
    picks: list[SectionPickSchema]


class SemiFinalPicksSchema(Schema):
    kind: Literal["SF_PICKS"] = "SF_PICKS"
    player_ids: list[str]


class FinalistPicksSchema(Schema):
    kind: Literal["FINALIST_PICKS"] = "FINALIST_PICKS"
    player_ids: list[str]


class ChampionSchema(Schema):
    kind: Literal["CHAMPION"] = "CHAMPION"
    player_id: str


class UnderperformerSchema(Schema):
    kind: Literal["UNDERPERFORMER"] = "UNDERPERFORMER"
    player_id: str


class BreakoutSchema(Schema):
    kind: Literal["BREAKOUT"] = "BREAKOUT"
    player_id: str


class GenericPlayerSchema(Schema):
    kind: Literal["GENERIC_PLAYER"] = "GENERIC_PLAYER"
    player_id: str


class GenericMatchResultSchema(Schema):
    kind: Literal["GENERIC_MATCH_RESULT"] = "GENERIC_MATCH_RESULT"
    winner_id: str
    set_score: Literal["2-0", "2-1", "3-0", "3-1", "3-2"]


class GenericIntegerSchema(Schema):
    kind: Literal["GENERIC_INTEGER"] = "GENERIC_INTEGER"
    value: int = Field(ge=0)


class GenericChoiceSchema(Schema):
    kind: Literal["GENERIC_CHOICE"] = "GENERIC_CHOICE"
    option_id: str


PredictionPayloadSchema = Annotated[
    QuarterFinalPicksSchema
    | SemiFinalPicksSchema
    | FinalistPicksSchema
    | ChampionSchema
    | UnderperformerSchema
    | BreakoutSchema
    | GenericPlayerSchema
    | GenericMatchResultSchema
    | GenericIntegerSchema
    | GenericChoiceSchema,
    Field(discriminator="kind"),
]


# --- entities ---


class UserSchema(Schema):
    id: str
    email: str
    display_name: str
    full_name: str | None
    is_admin: bool
    is_active: bool
    email_verified_at: datetime | None
    created_at: datetime


class PlayerSchema(Schema):
    id: str
    full_name: str
    country_code: str
    tour: Tour


class ScoringProfileSchema(Schema):
    quarter_finalist_points: int
    semi_finalist_points: int
    finalist_points: int
    champion_points: int
    underperformer_points: list[int]
    breakout_points: list[int]
    featured_match_winner_points: int
    featured_match_set_score_points: int


class TournamentSchema(Schema):
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
    scoring_profile: ScoringProfileSchema
    created_at: datetime


class DrawSchema(Schema):
    id: str
    tournament_id: str
    tour: Tour
    draw_size: int
    best_of: int
    official_draw_url: str | None


class DrawSectionSchema(Schema):
    id: str
    draw_id: str
    index: int


class DrawEntrySchema(Schema):
    id: str
    draw_id: str
    section_id: str
    player_id: str
    seed: int | None


class DrawEntryWithPlayerSchema(Schema):
    entry: DrawEntrySchema
    player: PlayerSchema
    round_reached: RoundReached | None


class DrawSectionWithEntriesSchema(Schema):
    section: DrawSectionSchema
    entries: list[DrawEntryWithPlayerSchema]


class ParticipationSchema(Schema):
    id: str
    user_id: str
    tournament_id: str
    joined_at: datetime
    status: ParticipationStatus


class BetGroupSchema(Schema):
    id: str
    tournament_id: str
    kind: BetGroupKind
    round: int | None
    title: str
    intro_markdown: str
    deadline: datetime
    status: BetGroupStatus


class QuestionChoiceOptionSchema(Schema):
    id: str
    label: str


class QuestionSchema(Schema):
    id: str
    bet_group_id: str
    draw_id: str | None
    family: QuestionFamily
    kind: TypedQuestionKind | None
    prompt: str
    answer_type: AnswerType
    options: list[QuestionChoiceOptionSchema] | None
    matchup: list[str] | None
    points_hint: str
    deadline_override: datetime | None
    position: int


class PredictionSchema(Schema):
    id: str
    participation_id: str
    question_id: str
    payload: PredictionPayloadSchema
    submitted_at: datetime | None
    updated_at: datetime


# --- requests and view models ---


class RegisterRequest(Schema):
    email: str
    password: str
    display_name: str


class LoginRequest(Schema):
    email: str
    password: str


class AuthenticatedUser(Schema):
    user: UserSchema
    requires_email_verification: bool


class NextGameTeaser(Schema):
    tournament_id: str
    name: str
    category: TournamentCategory
    surface: Surface
    location: str
    start_date: date
    end_date: date
    signup_deadline: datetime
    participant_count: int


class TournamentSummarySchema(Schema):
    tournament: TournamentSchema
    state: GameListState
    participant_count: int
    participation_id: str | None
    next_deadline: datetime | None
    user_position: int | None
    user_points: int | None
    current_round: int | None


class TournamentDetailSchema(Schema):
    tournament: TournamentSchema
    draws: list[DrawSchema]
    participant_count: int
    participation_id: str | None


class JoinTournamentRequest(Schema):
    tournament_id: str
    join_code: str | None = None


class PutPredictionRequest(Schema):
    tournament_id: str
    question_id: str
    payload: PredictionPayloadSchema
    as_draft: bool


class QuestionScoreRowSchema(Schema):
    question: QuestionSchema
    own_payload: PredictionPayloadSchema | None
    correct_answer: PredictionPayloadSchema | None
    points: int | None
    reason: str | None


class BetGroupScoreBlockSchema(Schema):
    bet_group: BetGroupSchema
    rows: list[QuestionScoreRowSchema]
    subtotal: int
    comparison_available: bool


class ScoreBreakdownSchema(Schema):
    tournament_id: str
    total: int
    position: int | None
    participant_count: int
    groups: list[BetGroupScoreBlockSchema]


class BetGroupPointsSchema(Schema):
    bet_group_id: str
    title: str
    points: int


class RankingEntrySchema(Schema):
    position: int
    participation_id: str
    display_name: str
    is_current_user: bool
    total_points: int
    last_group_points: int
    movement: int | None
    per_group_points: list[BetGroupPointsSchema]


class OutcomeEntryInput(Schema):
    player_id: str
    round_reached: RoundReached
    note: str | None = None


class PutDrawOutcomesRequest(Schema):
    draw_id: str
    entries: list[OutcomeEntryInput]


class PutQuestionOutcomeRequest(Schema):
    question_id: str
    correct_answer: PredictionPayloadSchema
    note: str | None = None


class RecalculateResultSchema(Schema):
    tournament_id: str
    score_entries_written: int
    calculated_at: datetime
