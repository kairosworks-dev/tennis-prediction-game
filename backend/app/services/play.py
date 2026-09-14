"""Inside a game: draws, bet groups, questions, predictions and scores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities import (
    BetGroup,
    Draw,
    DrawEntry,
    DrawSection,
    Player,
    Prediction,
    Question,
    User,
)
from app.domain.enums import BetGroupStatus, RoundReached, TypedQuestionKind
from app.domain.validation import (
    ValidationContext,
    ValidationError,
    expected_payload_kind,
    validate_prediction,
)
from app.repositories.interfaces import Repositories
from app.services.errors import Forbidden, NotFound, ValidationFailed
from app.services.ranking import RankingService


@dataclass(frozen=True, slots=True)
class EntryWithPlayer:
    entry: DrawEntry
    player: Player
    round_reached: RoundReached | None


@dataclass(frozen=True, slots=True)
class SectionWithEntries:
    section: DrawSection
    entries: list[EntryWithPlayer]


@dataclass(frozen=True, slots=True)
class QuestionScoreRow:
    question: Question
    own_payload: object | None
    correct_answer: object | None
    points: int | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class BetGroupScoreBlock:
    bet_group: BetGroup
    rows: list[QuestionScoreRow]
    subtotal: int
    comparison_available: bool


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    tournament_id: str
    total: int
    position: int | None
    participant_count: int
    groups: list[BetGroupScoreBlock]


class PlayService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos
        self._ranking = RankingService(repos)

    def _require_tournament(self, tournament_id: str) -> None:
        if self._repos.tournaments.get(tournament_id) is None:
            raise NotFound("That game does not exist.")

    def _require_participation(self, tournament_id: str, user: User) -> str:
        participation = self._repos.participations.find(tournament_id, user.id)
        if participation is None:
            raise Forbidden("You have not joined this game.")
        return participation.id

    def list_draws(self, tournament_id: str) -> list[Draw]:
        self._require_tournament(tournament_id)
        return self._repos.draws.list_for_tournament(tournament_id)

    def sections_with_entries(self, draw_id: str) -> list[SectionWithEntries]:
        if self._repos.draws.get(draw_id) is None:
            raise NotFound("That draw does not exist.")
        outcomes = {
            o.player_id: o.round_reached for o in self._repos.outcomes.list_for_draw(draw_id)
        }
        entries = self._repos.draws.list_entries(draw_id)

        sections: list[SectionWithEntries] = []
        for section in self._repos.draws.list_sections(draw_id):
            rows: list[EntryWithPlayer] = []
            for entry in entries:
                if entry.section_id != section.id:
                    continue
                player = self._repos.players.get(entry.player_id)
                if player is None:
                    continue
                rows.append(EntryWithPlayer(entry, player, outcomes.get(entry.player_id)))
            rows.sort(key=lambda r: r.entry.seed if r.entry.seed is not None else 999)
            sections.append(SectionWithEntries(section, rows))
        return sections

    def list_bet_groups(self, tournament_id: str, user: User) -> list[BetGroup]:
        self._require_tournament(tournament_id)
        groups = self._repos.bet_groups.list_for_tournament(tournament_id)
        # A draft group is the organiser's work in progress.
        return [g for g in groups if g.status is not BetGroupStatus.DRAFT or user.is_admin]

    def list_questions(self, tournament_id: str, bet_group_id: str) -> list[Question]:
        self._require_tournament(tournament_id)
        group = self._repos.bet_groups.get(bet_group_id)
        if group is None or group.tournament_id != tournament_id:
            raise NotFound("That bet group does not exist.")
        return self._repos.questions.list_for_group(bet_group_id)

    def list_own_predictions(self, tournament_id: str, user: User) -> list[Prediction]:
        participation_id = self._require_participation(tournament_id, user)
        question_ids = self._question_ids_for(tournament_id)
        return [
            p
            for p in self._repos.predictions.list_for_participation(participation_id)
            if p.question_id in question_ids
        ]

    def _question_ids_for(self, tournament_id: str) -> set[str]:
        ids: set[str] = set()
        for group in self._repos.bet_groups.list_for_tournament(tournament_id):
            ids.update(q.id for q in self._repos.questions.list_for_group(group.id))
        return ids

    def put_prediction(
        self,
        tournament_id: str,
        question_id: str,
        payload: object,
        as_draft: bool,
        user: User,
    ) -> Prediction:
        participation_id = self._require_participation(tournament_id, user)
        question = self._repos.questions.get(question_id)
        if question is None:
            raise NotFound("That question does not exist.")
        group = self._repos.bet_groups.get(question.bet_group_id)
        if group is None or group.tournament_id != tournament_id:
            raise NotFound("That question does not exist.")

        # Spec 5.3: the question's bet group must be open.
        if group.status is not BetGroupStatus.OPEN:
            raise Forbidden(
                "That group is not open yet."
                if group.status is BetGroupStatus.DRAFT
                else "That group has closed. Predictions are final."
            )

        expected = expected_payload_kind(question)
        if getattr(payload, "kind", None) != expected:
            raise ValidationFailed(f"This question expects a {expected} answer.")

        # A draft saves the shape without holding it to the cross-question rules.
        if not as_draft:
            try:
                validate_prediction(payload, self._validation_context(question, participation_id))
            except ValidationError as error:
                raise ValidationFailed(error.detail, error.errors) from error

        now = datetime.now(UTC)
        existing = self._repos.predictions.find(participation_id, question_id)
        prediction = Prediction(
            id=existing.id if existing else f"pred-{uuid4().hex[:12]}",
            participation_id=participation_id,
            question_id=question_id,
            payload=payload,
            submitted_at=None if as_draft else now,
            updated_at=now,
        )
        self._repos.predictions.upsert(prediction)
        self._repos.commit()
        return prediction

    def _validation_context(self, question: Question, participation_id: str) -> ValidationContext:
        siblings: dict[TypedQuestionKind, object] = {}
        for other in self._repos.questions.list_for_group(question.bet_group_id):
            # Cross-question rules only compare answers within the same draw.
            if other.kind is None or other.draw_id != question.draw_id:
                continue
            found = self._repos.predictions.find(participation_id, other.id)
            if found is not None:
                siblings[other.kind] = found.payload

        draw = self._repos.draws.get(question.draw_id) if question.draw_id else None
        entries = self._repos.draws.list_entries(question.draw_id) if question.draw_id else []
        return ValidationContext(
            question=question, draw=draw, entries=tuple(entries), siblings=siblings
        )

    def score_breakdown(self, tournament_id: str, user: User) -> ScoreBreakdown:
        participation_id = self._require_participation(tournament_id, user)
        own_scores = {
            s.question_id: s for s in self._repos.scores.list_for_participation(participation_id)
        }
        blocks: list[BetGroupScoreBlock] = []

        for group in self._repos.bet_groups.list_for_tournament(tournament_id):
            if group.status is BetGroupStatus.DRAFT:
                continue
            rows: list[QuestionScoreRow] = []
            for question in self._repos.questions.list_for_group(group.id):
                prediction = self._repos.predictions.find(participation_id, question.id)
                outcome = self._repos.outcomes.get_question_outcome(question.id)
                score = own_scores.get(question.id)
                rows.append(
                    QuestionScoreRow(
                        question=question,
                        own_payload=prediction.payload if prediction else None,
                        correct_answer=outcome.correct_answer if outcome else None,
                        points=score.points if score else None,
                        reason=score.reason if score else None,
                    )
                )
            blocks.append(
                BetGroupScoreBlock(
                    bet_group=group,
                    rows=rows,
                    subtotal=sum(r.points or 0 for r in rows),
                    comparison_available=group.status
                    in (BetGroupStatus.LOCKED, BetGroupStatus.SETTLED),
                )
            )

        ranking = self._ranking.ranking_for(tournament_id, user.id)
        own = next((r for r in ranking if r.participation_id == participation_id), None)
        return ScoreBreakdown(
            tournament_id=tournament_id,
            total=sum(b.subtotal for b in blocks),
            position=own.position if own else None,
            participant_count=len(self._repos.participations.list_for_tournament(tournament_id)),
            groups=blocks,
        )
