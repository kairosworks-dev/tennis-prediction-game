"""Landing page teaser and game selection (spec 4.1, 4.3)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import schemas
from app.api.deps import CurrentUser, GameServiceDep, RepositoriesDep

router = APIRouter()


@router.get(
    "/public/next-game",
    operation_id="getNextGame",
    tags=["public"],
    response_model=schemas.NextGameTeaser | None,
    summary="The next game open for signup",
)
def next_game(games: GameServiceDep, repos: RepositoriesDep) -> schemas.NextGameTeaser | None:
    tournament = games.next_open_game()
    if tournament is None:
        return None
    return schemas.NextGameTeaser(
        tournament_id=tournament.id,
        name=tournament.name,
        category=tournament.category,
        surface=tournament.surface,
        location=tournament.location,
        start_date=tournament.start_date,
        end_date=tournament.end_date,
        signup_deadline=tournament.signup_deadline,
        participant_count=len(repos.participations.list_for_tournament(tournament.id)),
    )


@router.get(
    "/tournaments",
    operation_id="listTournaments",
    tags=["games"],
    response_model=list[schemas.TournamentSummarySchema],
    summary="Games visible to the signed-in user",
)
def list_tournaments(
    user: CurrentUser, games: GameServiceDep
) -> list[schemas.TournamentSummarySchema]:
    return [
        schemas.TournamentSummarySchema.model_validate(s) for s in games.list_for_user(user)
    ]


@router.get(
    "/tournaments/{tournament_id}",
    operation_id="getTournament",
    tags=["games"],
    response_model=schemas.TournamentDetailSchema,
    summary="One game with its draws",
)
def get_tournament(
    tournament_id: str, user: CurrentUser, games: GameServiceDep
) -> schemas.TournamentDetailSchema:
    return schemas.TournamentDetailSchema.model_validate(games.detail(tournament_id, user))


@router.post(
    "/tournaments/{tournament_id}/join",
    operation_id="joinTournament",
    tags=["games"],
    status_code=201,
    response_model=schemas.ParticipationSchema,
    summary="Join a game",
)
def join_tournament(
    tournament_id: str,
    body: schemas.JoinTournamentRequest,
    user: CurrentUser,
    games: GameServiceDep,
) -> schemas.ParticipationSchema:
    participation = games.join(tournament_id, user, body.join_code)
    return schemas.ParticipationSchema.model_validate(participation)
