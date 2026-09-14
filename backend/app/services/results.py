"""Organiser results entry and recalculation (spec 4.5.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities import OutcomeEntry, QuestionOutcome, ScoreEntry, User
from app.domain.enums import RoundReached
from app.domain.scoring import ScoreInput, ScoringContext, score_all
from app.domain.validation import expected_payload_kind
from app.repositories.interfaces import Repositories
from app.services.errors import Forbidden, NotFound, ValidationFailed


@dataclass(frozen=True, slots=True)
class RecalculateResult:
    tournament_id: str
    score_entries_written: int
    calculated_at: datetime


class ResultsService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    @staticmethod
    def _require_admin(user: User) -> None:
        # Authorisation is checked server-side on every organiser route; the
        # frontend hiding a button is never the control (AGENTS.md).
        if not user.is_admin:
            raise Forbidden("That is an organiser action.")

    def put_draw_outcomes(
        self, draw_id: str, entries: list[tuple[str, RoundReached, str | None]], user: User
    ) -> None:
        self._require_admin(user)
        draw = self._repos.draws.get(draw_id)
        if draw is None:
            raise NotFound("That draw does not exist.")
        entrants = {e.player_id for e in self._repos.draws.list_entries(draw_id)}
        for player_id, _, _ in entries:
            if player_id not in entrants:
                raise ValidationFailed("That player is not in this draw.")

        # Replaces the whole grid rather than merging, so a removed row means
        # the outcome is gone (decision D9).
        self._repos.outcomes.replace_for_draw(
            draw_id,
            [
                OutcomeEntry(draw_id=draw_id, player_id=pid, round_reached=round_, note=note)
                for pid, round_, note in entries
            ],
        )
        self._repos.commit()

    def put_question_outcome(
        self, question_id: str, correct_answer: object, note: str | None, user: User
    ) -> None:
        self._require_admin(user)
        question = self._repos.questions.get(question_id)
        if question is None:
            raise NotFound("That question does not exist.")
        expected = expected_payload_kind(question)
        if getattr(correct_answer, "kind", None) != expected:
            raise ValidationFailed(f"This question settles with a {expected} answer.")
        self._repos.outcomes.put_question_outcome(
            QuestionOutcome(
                question_id=question_id,
                correct_answer=correct_answer,
                settled_at=datetime.now(UTC),
                note=note,
            )
        )
        self._repos.commit()

    def recalculate(self, tournament_id: str, user: User) -> RecalculateResult:
        """Rebuild every score entry for a game from source data.

        Idempotent: the old entries are thrown away and recomputed, which is
        the whole point of scores being derived data (AGENTS.md hard rule 7).
        """
        self._require_admin(user)
        tournament = self._repos.tournaments.get(tournament_id)
        if tournament is None:
            raise NotFound("That game does not exist.")

        outcomes: dict[str, RoundReached] = {}
        for draw in self._repos.draws.list_for_tournament(tournament_id):
            for entry in self._repos.outcomes.list_for_draw(draw.id):
                outcomes[entry.player_id] = entry.round_reached

        names = {p.id: p.full_name for p in self._repos.players.list_all()}
        context = ScoringContext(
            outcomes=outcomes, profile=tournament.scoring_profile, names=names
        )

        inputs: list[ScoreInput] = []
        question_ids: list[str] = []
        participations = self._repos.participations.list_for_tournament(tournament_id)

        for group in self._repos.bet_groups.list_for_tournament(tournament_id):
            for question in self._repos.questions.list_for_group(group.id):
                question_ids.append(question.id)
                outcome = self._repos.outcomes.get_question_outcome(question.id)
                for participation in participations:
                    prediction = self._repos.predictions.find(participation.id, question.id)
                    if prediction is None:
                        continue
                    inputs.append(
                        ScoreInput(
                            participation_id=participation.id,
                            question=question,
                            payload=prediction.payload,
                            correct_answer=outcome.correct_answer if outcome else None,
                        )
                    )

        calculated_at = datetime.now(UTC)
        results = score_all(inputs, context)
        self._repos.scores.replace_for_questions(
            question_ids,
            [
                ScoreEntry(
                    id=f"score-{uuid4().hex[:12]}",
                    participation_id=r.participation_id,
                    question_id=r.question_id,
                    points=r.points,
                    reason=r.reason,
                    calculated_at=calculated_at,
                )
                for r in results
            ],
        )
        self._repos.commit()
        return RecalculateResult(
            tournament_id=tournament_id,
            score_entries_written=len(results),
            calculated_at=calculated_at,
        )
