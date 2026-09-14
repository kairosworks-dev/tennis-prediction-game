"""Finding, viewing and joining a game (spec 4.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities import Draw, Participation, Tournament, User
from app.domain.enums import (
    BetGroupStatus,
    GameListState,
    ParticipationStatus,
    TournamentStatus,
    TournamentVisibility,
)
from app.repositories.interfaces import Repositories
from app.services.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.services.ranking import RankingService


@dataclass(frozen=True, slots=True)
class TournamentSummary:
    tournament: Tournament
    state: GameListState
    participant_count: int
    participation_id: str | None
    next_deadline: datetime | None
    user_position: int | None
    user_points: int | None
    current_round: int | None


@dataclass(frozen=True, slots=True)
class TournamentDetail:
    tournament: Tournament
    draws: list[Draw]
    participant_count: int
    participation_id: str | None


class GameService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos
        self._ranking = RankingService(repos)

    def next_open_game(self) -> Tournament | None:
        """The landing page teaser (decision D13). No session required."""
        now = datetime.now(UTC)
        open_games = [
            t
            for t in self._repos.tournaments.list_all()
            if t.status is TournamentStatus.PUBLISHED
            and t.visibility is TournamentVisibility.PUBLIC
            and t.signup_deadline > now
        ]
        return min(open_games, key=lambda t: t.signup_deadline, default=None)

    def list_for_user(self, user: User) -> list[TournamentSummary]:
        now = datetime.now(UTC)
        summaries: list[TournamentSummary] = []

        for tournament in self._repos.tournaments.list_all():
            participation = self._repos.participations.find(tournament.id, user.id)
            if tournament.status is TournamentStatus.DRAFT and not user.is_admin:
                continue
            if tournament.visibility is TournamentVisibility.PRIVATE and participation is None:
                continue

            participants = self._repos.participations.list_for_tournament(tournament.id)
            groups = self._repos.bet_groups.list_for_tournament(tournament.id)
            open_group = next((g for g in groups if g.status is BetGroupStatus.OPEN), None)

            if tournament.status is TournamentStatus.FINISHED:
                state = GameListState.FINISHED
            elif participation is not None and tournament.status is TournamentStatus.RUNNING:
                state = GameListState.RUNNING
            elif tournament.signup_deadline > now:
                state = GameListState.OPEN_FOR_SIGNUP
            else:
                state = GameListState.RUNNING

            position: int | None = None
            points: int | None = None
            if participation is not None:
                for row in self._ranking.ranking_for(tournament.id, user.id):
                    if row.participation_id == participation.id:
                        position, points = row.position, row.total_points
                        break

            summaries.append(
                TournamentSummary(
                    tournament=tournament,
                    state=state,
                    participant_count=len(participants),
                    participation_id=participation.id if participation else None,
                    next_deadline=open_group.deadline if open_group else None,
                    user_position=position,
                    user_points=points,
                    current_round=open_group.round if open_group else None,
                )
            )
        return summaries

    def detail(self, tournament_id: str, user: User) -> TournamentDetail:
        tournament = self._repos.tournaments.get(tournament_id)
        if tournament is None:
            raise NotFound("That game does not exist.")
        participation = self._repos.participations.find(tournament_id, user.id)
        if (
            tournament.visibility is TournamentVisibility.PRIVATE
            and participation is None
            and not user.is_admin
        ):
            raise NotFound("That game does not exist.")

        # A join code is an organiser's to hand out, not a participant's to read.
        visible = tournament
        if not user.is_admin and tournament.join_code is not None:
            visible = Tournament(**{**tournament.__dict__, "join_code": None})

        return TournamentDetail(
            tournament=visible,
            draws=self._repos.draws.list_for_tournament(tournament_id),
            participant_count=len(self._repos.participations.list_for_tournament(tournament_id)),
            participation_id=participation.id if participation else None,
        )

    def join(self, tournament_id: str, user: User, join_code: str | None) -> Participation:
        tournament = self._repos.tournaments.get(tournament_id)
        if tournament is None:
            raise NotFound("That game does not exist.")
        if user.email_verified_at is None:
            raise Forbidden("Confirm your email address before joining a game.")
        if tournament.signup_deadline <= datetime.now(UTC):
            raise Forbidden("Signup for that game has closed.")
        private = tournament.visibility is TournamentVisibility.PRIVATE
        if private and join_code != tournament.join_code:
            raise ValidationFailed(
                "That join code is not right.", {"joinCode": ["Check it with the organiser."]}
            )
        if self._repos.participations.find(tournament_id, user.id) is not None:
            raise Conflict("You have already joined this game.")

        participation = Participation(
            id=f"part-{uuid4().hex[:12]}",
            user_id=user.id,
            tournament_id=tournament_id,
            joined_at=datetime.now(UTC),
            status=ParticipationStatus.ACTIVE,
        )
        self._repos.participations.add(participation)
        self._repos.commit()
        return participation
