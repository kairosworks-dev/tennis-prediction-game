"""Conversion between SQLAlchemy rows and domain entities.

The domain does not know about rows and the rows do not know about the domain;
this module is the only place that knows both.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.domain import predictions as payloads
from app.domain.entities import (
    BetGroup,
    Draw,
    DrawEntry,
    DrawSection,
    OutcomeEntry,
    Participation,
    Player,
    Prediction,
    Question,
    QuestionChoiceOption,
    QuestionOutcome,
    ScoreEntry,
    ScoringProfile,
    Tournament,
    User,
)
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
from app.repositories import models

_PAYLOAD_TYPES: dict[str, type] = {
    "QF_PICKS": payloads.QuarterFinalPicks,
    "SF_PICKS": payloads.SemiFinalPicks,
    "FINALIST_PICKS": payloads.FinalistPicks,
    "CHAMPION": payloads.ChampionPick,
    "UNDERPERFORMER": payloads.UnderperformerPick,
    "BREAKOUT": payloads.BreakoutPick,
    "GENERIC_PLAYER": payloads.GenericPlayer,
    "GENERIC_MATCH_RESULT": payloads.GenericMatchResult,
    "GENERIC_INTEGER": payloads.GenericInteger,
    "GENERIC_CHOICE": payloads.GenericChoice,
}


def payload_to_json(payload: object) -> dict[str, Any]:
    data = asdict(payload)  # type: ignore[call-overload]
    if isinstance(payload, payloads.QuarterFinalPicks):
        data["picks"] = [asdict(p) for p in payload.picks]
    return data


def payload_from_json(data: dict[str, Any]) -> object:
    kind = data.get("kind")
    cls = _PAYLOAD_TYPES.get(str(kind))
    if cls is None:
        raise ValueError(f"unrecognised payload kind: {kind!r}")
    fields = {k: v for k, v in data.items() if k != "kind"}
    if cls is payloads.QuarterFinalPicks:
        return payloads.QuarterFinalPicks(
            picks=tuple(payloads.SectionPick(**p) for p in fields["picks"])
        )
    for key in ("player_ids",):
        if key in fields and isinstance(fields[key], list):
            fields[key] = tuple(fields[key])
    return cls(**fields)


def user_to_domain(row: models.UserRow) -> User:
    return User(
        id=row.id, email=row.email, password_hash=row.password_hash,
        display_name=row.display_name, full_name=row.full_name, is_admin=row.is_admin,
        is_active=row.is_active, email_verified_at=row.email_verified_at,
        created_at=row.created_at,
    )


def user_to_row(user: User) -> models.UserRow:
    return models.UserRow(**{f: getattr(user, f) for f in (
        "id", "email", "password_hash", "display_name", "full_name",
        "is_admin", "is_active", "email_verified_at", "created_at",
    )})


def player_to_domain(row: models.PlayerRow) -> Player:
    return Player(id=row.id, full_name=row.full_name, country_code=row.country_code,
                  tour=Tour(row.tour))


def player_to_row(player: Player) -> models.PlayerRow:
    return models.PlayerRow(id=player.id, full_name=player.full_name,
                            country_code=player.country_code, tour=str(player.tour))


def tournament_to_domain(row: models.TournamentRow) -> Tournament:
    return Tournament(
        id=row.id, name=row.name, category=TournamentCategory(row.category),
        surface=Surface(row.surface), location=row.location, start_date=row.start_date,
        end_date=row.end_date, signup_deadline=row.signup_deadline,
        visibility=TournamentVisibility(row.visibility), join_code=row.join_code,
        status=TournamentStatus(row.status), rules_markdown=row.rules_markdown,
        created_at=row.created_at,
        scoring_profile=ScoringProfile(
            **{
                **row.scoring_profile,
                "underperformer_points": tuple(row.scoring_profile["underperformer_points"]),
                "breakout_points": tuple(row.scoring_profile["breakout_points"]),
            }
        ),
    )


def tournament_to_row(t: Tournament) -> models.TournamentRow:
    return models.TournamentRow(
        id=t.id, name=t.name, category=str(t.category), surface=str(t.surface),
        location=t.location, start_date=t.start_date, end_date=t.end_date,
        signup_deadline=t.signup_deadline, visibility=str(t.visibility),
        join_code=t.join_code, status=str(t.status), rules_markdown=t.rules_markdown,
        scoring_profile=asdict(t.scoring_profile), created_at=t.created_at,
    )


def draw_to_domain(row: models.DrawRow) -> Draw:
    return Draw(id=row.id, tournament_id=row.tournament_id, tour=Tour(row.tour),
                draw_size=row.draw_size, best_of=row.best_of,
                official_draw_url=row.official_draw_url)


def draw_to_row(d: Draw) -> models.DrawRow:
    return models.DrawRow(id=d.id, tournament_id=d.tournament_id, tour=str(d.tour),
                          draw_size=d.draw_size, best_of=d.best_of,
                          official_draw_url=d.official_draw_url)


def section_to_domain(row: models.DrawSectionRow) -> DrawSection:
    return DrawSection(id=row.id, draw_id=row.draw_id, index=row.index)


def section_to_row(s: DrawSection) -> models.DrawSectionRow:
    return models.DrawSectionRow(id=s.id, draw_id=s.draw_id, index=s.index)


def entry_to_domain(row: models.DrawEntryRow) -> DrawEntry:
    return DrawEntry(id=row.id, draw_id=row.draw_id, section_id=row.section_id,
                     player_id=row.player_id, seed=row.seed)


def entry_to_row(e: DrawEntry) -> models.DrawEntryRow:
    return models.DrawEntryRow(id=e.id, draw_id=e.draw_id, section_id=e.section_id,
                               player_id=e.player_id, seed=e.seed)


def participation_to_domain(row: models.ParticipationRow) -> Participation:
    return Participation(id=row.id, user_id=row.user_id, tournament_id=row.tournament_id,
                         joined_at=row.joined_at, status=ParticipationStatus(row.status))


def participation_to_row(p: Participation) -> models.ParticipationRow:
    return models.ParticipationRow(id=p.id, user_id=p.user_id, tournament_id=p.tournament_id,
                                   joined_at=p.joined_at, status=str(p.status))


def bet_group_to_domain(row: models.BetGroupRow) -> BetGroup:
    return BetGroup(id=row.id, tournament_id=row.tournament_id, kind=BetGroupKind(row.kind),
                    round=row.round, title=row.title, intro_markdown=row.intro_markdown,
                    deadline=row.deadline, status=BetGroupStatus(row.status))


def bet_group_to_row(g: BetGroup) -> models.BetGroupRow:
    return models.BetGroupRow(id=g.id, tournament_id=g.tournament_id, kind=str(g.kind),
                              round=g.round, title=g.title, intro_markdown=g.intro_markdown,
                              deadline=g.deadline, status=str(g.status))


def question_to_domain(row: models.QuestionRow) -> Question:
    return Question(
        id=row.id, bet_group_id=row.bet_group_id, draw_id=row.draw_id,
        family=QuestionFamily(row.family),
        kind=TypedQuestionKind(row.kind) if row.kind else None,
        prompt=row.prompt, answer_type=AnswerType(row.answer_type),
        options=tuple(QuestionChoiceOption(**o) for o in row.options) if row.options else None,
        matchup=(row.matchup[0], row.matchup[1]) if row.matchup else None,
        points_hint=row.points_hint, deadline_override=row.deadline_override,
        position=row.position,
    )


def question_to_row(q: Question) -> models.QuestionRow:
    return models.QuestionRow(
        id=q.id, bet_group_id=q.bet_group_id, draw_id=q.draw_id, family=str(q.family),
        kind=str(q.kind) if q.kind else None, prompt=q.prompt,
        answer_type=str(q.answer_type),
        options=[asdict(o) for o in q.options] if q.options else None,
        matchup=list(q.matchup) if q.matchup else None, points_hint=q.points_hint,
        deadline_override=q.deadline_override, position=q.position,
    )


def prediction_to_domain(row: models.PredictionRow) -> Prediction:
    return Prediction(id=row.id, participation_id=row.participation_id,
                      question_id=row.question_id, payload=payload_from_json(row.payload),
                      submitted_at=row.submitted_at, updated_at=row.updated_at)


def prediction_to_row(p: Prediction) -> models.PredictionRow:
    return models.PredictionRow(id=p.id, participation_id=p.participation_id,
                                question_id=p.question_id, payload=payload_to_json(p.payload),
                                submitted_at=p.submitted_at, updated_at=p.updated_at)


def outcome_to_domain(row: models.OutcomeEntryRow) -> OutcomeEntry:
    return OutcomeEntry(draw_id=row.draw_id, player_id=row.player_id,
                        round_reached=RoundReached(row.round_reached), note=row.note)


def outcome_to_row(o: OutcomeEntry) -> models.OutcomeEntryRow:
    return models.OutcomeEntryRow(draw_id=o.draw_id, player_id=o.player_id,
                                  round_reached=str(o.round_reached), note=o.note)


def question_outcome_to_domain(row: models.QuestionOutcomeRow) -> QuestionOutcome:
    return QuestionOutcome(question_id=row.question_id,
                           correct_answer=payload_from_json(row.correct_answer),
                           settled_at=row.settled_at, note=row.note)


def question_outcome_to_row(o: QuestionOutcome) -> models.QuestionOutcomeRow:
    return models.QuestionOutcomeRow(question_id=o.question_id,
                                     correct_answer=payload_to_json(o.correct_answer),
                                     settled_at=o.settled_at, note=o.note)


def score_to_domain(row: models.ScoreEntryRow) -> ScoreEntry:
    return ScoreEntry(id=row.id, participation_id=row.participation_id,
                      question_id=row.question_id, points=row.points, reason=row.reason,
                      calculated_at=row.calculated_at)


def score_to_row(s: ScoreEntry) -> models.ScoreEntryRow:
    return models.ScoreEntryRow(id=s.id, participation_id=s.participation_id,
                                question_id=s.question_id, points=s.points, reason=s.reason,
                                calculated_at=s.calculated_at)
