"""Inside a game (spec 4.4)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import schemas
from app.api.deps import CurrentUser, PlayServiceDep, RankingServiceDep
from app.api.payloads import to_domain_payload

router = APIRouter(tags=["play"])


@router.get(
    "/tournaments/{tournament_id}/draws",
    operation_id="listDraws",
    response_model=list[schemas.DrawSchema],
    summary="The one or two draws of a game",
)
def list_draws(
    tournament_id: str, user: CurrentUser, play: PlayServiceDep
) -> list[schemas.DrawSchema]:
    del user
    return [schemas.DrawSchema.model_validate(d) for d in play.list_draws(tournament_id)]


@router.get(
    "/tournaments/{tournament_id}/draws/{draw_id}/entries",
    operation_id="listDrawEntries",
    response_model=list[schemas.DrawSectionWithEntriesSchema],
    summary="A draw's eight sections with their entrants",
)
def list_draw_entries(
    tournament_id: str, draw_id: str, user: CurrentUser, play: PlayServiceDep
) -> list[schemas.DrawSectionWithEntriesSchema]:
    del user
    play.list_draws(tournament_id)
    return [
        schemas.DrawSectionWithEntriesSchema.model_validate(s)
        for s in play.sections_with_entries(draw_id)
    ]


@router.get(
    "/tournaments/{tournament_id}/bet-groups",
    operation_id="listBetGroups",
    response_model=list[schemas.BetGroupSchema],
    summary="Bet groups, ordered by deadline",
)
def list_bet_groups(
    tournament_id: str, user: CurrentUser, play: PlayServiceDep
) -> list[schemas.BetGroupSchema]:
    return [
        schemas.BetGroupSchema.model_validate(g) for g in play.list_bet_groups(tournament_id, user)
    ]


@router.get(
    "/tournaments/{tournament_id}/bet-groups/{bet_group_id}/questions",
    operation_id="listQuestions",
    response_model=list[schemas.QuestionSchema],
    summary="The questions in one bet group",
)
def list_questions(
    tournament_id: str, bet_group_id: str, user: CurrentUser, play: PlayServiceDep
) -> list[schemas.QuestionSchema]:
    del user
    return [
        schemas.QuestionSchema.model_validate(q)
        for q in play.list_questions(tournament_id, bet_group_id)
    ]


@router.get(
    "/tournaments/{tournament_id}/predictions",
    operation_id="listOwnPredictions",
    response_model=list[schemas.PredictionSchema],
    summary="The signed-in participant's own predictions",
)
def list_own_predictions(
    tournament_id: str, user: CurrentUser, play: PlayServiceDep
) -> list[schemas.PredictionSchema]:
    return [
        schemas.PredictionSchema.model_validate(p)
        for p in play.list_own_predictions(tournament_id, user)
    ]


@router.put(
    "/tournaments/{tournament_id}/questions/{question_id}/prediction",
    operation_id="putPrediction",
    response_model=schemas.PredictionSchema,
    summary="Submit or update one prediction",
)
def put_prediction(
    tournament_id: str,
    question_id: str,
    body: schemas.PutPredictionRequest,
    user: CurrentUser,
    play: PlayServiceDep,
) -> schemas.PredictionSchema:
    prediction = play.put_prediction(
        tournament_id=tournament_id,
        question_id=question_id,
        payload=to_domain_payload(body.payload),
        as_draft=body.as_draft,
        user=user,
    )
    return schemas.PredictionSchema.model_validate(prediction)


@router.get(
    "/tournaments/{tournament_id}/scores",
    operation_id="getScoreBreakdown",
    response_model=schemas.ScoreBreakdownSchema,
    summary="The participant's own scores, by bet group",
)
def get_scores(
    tournament_id: str, user: CurrentUser, play: PlayServiceDep
) -> schemas.ScoreBreakdownSchema:
    return schemas.ScoreBreakdownSchema.model_validate(play.score_breakdown(tournament_id, user))


@router.get(
    "/tournaments/{tournament_id}/ranking",
    operation_id="getRanking",
    response_model=list[schemas.RankingEntrySchema],
    summary="The leaderboard, both draws combined",
)
def get_ranking(
    tournament_id: str,
    user: CurrentUser,
    play: PlayServiceDep,
    ranking: RankingServiceDep,
) -> list[schemas.RankingEntrySchema]:
    play.list_draws(tournament_id)
    return [
        schemas.RankingEntrySchema.model_validate(r)
        for r in ranking.ranking_for(tournament_id, user.id)
    ]
