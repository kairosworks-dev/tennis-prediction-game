"""Organiser results entry (spec 4.5.4).

Authorisation is checked here on every route, not assumed from the frontend.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import schemas
from app.api.deps import AdminUser, PlayServiceDep, ResultsServiceDep
from app.api.payloads import to_domain_payload

router = APIRouter(tags=["results"])


@router.put(
    "/admin/draws/{draw_id}/outcomes",
    operation_id="putDrawOutcomes",
    response_model=list[schemas.DrawSectionWithEntriesSchema],
    summary="Replace a draw's outcome grid",
)
def put_draw_outcomes(
    draw_id: str,
    body: schemas.PutDrawOutcomesRequest,
    user: AdminUser,
    results: ResultsServiceDep,
    play: PlayServiceDep,
) -> list[schemas.DrawSectionWithEntriesSchema]:
    results.put_draw_outcomes(
        draw_id, [(e.player_id, e.round_reached, e.note) for e in body.entries], user
    )
    # The grid is returned in the shape the organiser's screen already renders.
    return [
        schemas.DrawSectionWithEntriesSchema.model_validate(s)
        for s in play.sections_with_entries(draw_id)
    ]


@router.put(
    "/admin/questions/{question_id}/outcome",
    operation_id="putQuestionOutcome",
    status_code=204,
    summary="Settle one generic question",
)
def put_question_outcome(
    question_id: str,
    body: schemas.PutQuestionOutcomeRequest,
    user: AdminUser,
    results: ResultsServiceDep,
) -> None:
    results.put_question_outcome(
        question_id, to_domain_payload(body.correct_answer), body.note, user
    )


@router.post(
    "/admin/tournaments/{tournament_id}/recalculate",
    operation_id="recalculateScores",
    response_model=schemas.RecalculateResultSchema,
    summary="Rebuild every score entry for a game",
)
def recalculate(
    tournament_id: str, user: AdminUser, results: ResultsServiceDep
) -> schemas.RecalculateResultSchema:
    return schemas.RecalculateResultSchema.model_validate(
        results.recalculate(tournament_id, user)
    )
