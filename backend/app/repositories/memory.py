"""In-memory repository implementations (step 3).

Step 4 adds a SQLAlchemy set beside these and the test suite runs against both.
Nothing here is clever: lists and dictionaries, so the interface is exercised
honestly without a database in the way.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    QuestionOutcome,
    ScoreEntry,
    Tournament,
    User,
)
from app.repositories import interfaces


@dataclass
class MemoryStore:
    """The tables, as plain lists."""

    users: list[User] = field(default_factory=list)
    players: list[Player] = field(default_factory=list)
    tournaments: list[Tournament] = field(default_factory=list)
    draws: list[Draw] = field(default_factory=list)
    sections: list[DrawSection] = field(default_factory=list)
    entries: list[DrawEntry] = field(default_factory=list)
    participations: list[Participation] = field(default_factory=list)
    bet_groups: list[BetGroup] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    predictions: list[Prediction] = field(default_factory=list)
    outcomes: list[OutcomeEntry] = field(default_factory=list)
    question_outcomes: list[QuestionOutcome] = field(default_factory=list)
    scores: list[ScoreEntry] = field(default_factory=list)


class MemoryUserRepository(interfaces.UserRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, user_id: str) -> User | None:
        return next((u for u in self._store.users if u.id == user_id), None)

    def get_by_email(self, email: str) -> User | None:
        lowered = email.strip().lower()
        return next((u for u in self._store.users if u.email.lower() == lowered), None)

    def add(self, user: User) -> User:
        self._store.users.append(user)
        return user

    def list_all(self) -> list[User]:
        return list(self._store.users)


class MemoryPlayerRepository(interfaces.PlayerRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, player_id: str) -> Player | None:
        return next((p for p in self._store.players if p.id == player_id), None)

    def list_all(self) -> list[Player]:
        return list(self._store.players)

    def add(self, player: Player) -> Player:
        self._store.players.append(player)
        return player


class MemoryTournamentRepository(interfaces.TournamentRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, tournament_id: str) -> Tournament | None:
        return next((t for t in self._store.tournaments if t.id == tournament_id), None)

    def list_all(self) -> list[Tournament]:
        return list(self._store.tournaments)

    def add(self, tournament: Tournament) -> Tournament:
        self._store.tournaments.append(tournament)
        return tournament


class MemoryDrawRepository(interfaces.DrawRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, draw_id: str) -> Draw | None:
        return next((d for d in self._store.draws if d.id == draw_id), None)

    def list_for_tournament(self, tournament_id: str) -> list[Draw]:
        return [d for d in self._store.draws if d.tournament_id == tournament_id]

    def list_sections(self, draw_id: str) -> list[DrawSection]:
        return sorted(
            (s for s in self._store.sections if s.draw_id == draw_id), key=lambda s: s.index
        )

    def list_entries(self, draw_id: str) -> list[DrawEntry]:
        return [e for e in self._store.entries if e.draw_id == draw_id]

    def add(self, draw: Draw) -> Draw:
        self._store.draws.append(draw)
        return draw

    def add_section(self, section: DrawSection) -> DrawSection:
        self._store.sections.append(section)
        return section

    def add_entry(self, entry: DrawEntry) -> DrawEntry:
        self._store.entries.append(entry)
        return entry


class MemoryParticipationRepository(interfaces.ParticipationRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, participation_id: str) -> Participation | None:
        return next((p for p in self._store.participations if p.id == participation_id), None)

    def find(self, tournament_id: str, user_id: str) -> Participation | None:
        return next(
            (
                p
                for p in self._store.participations
                if p.tournament_id == tournament_id and p.user_id == user_id
            ),
            None,
        )

    def list_for_tournament(self, tournament_id: str) -> list[Participation]:
        return [p for p in self._store.participations if p.tournament_id == tournament_id]

    def add(self, participation: Participation) -> Participation:
        self._store.participations.append(participation)
        return participation


class MemoryBetGroupRepository(interfaces.BetGroupRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, bet_group_id: str) -> BetGroup | None:
        return next((g for g in self._store.bet_groups if g.id == bet_group_id), None)

    def list_for_tournament(self, tournament_id: str) -> list[BetGroup]:
        return sorted(
            (g for g in self._store.bet_groups if g.tournament_id == tournament_id),
            key=lambda g: g.deadline,
        )

    def add(self, bet_group: BetGroup) -> BetGroup:
        self._store.bet_groups.append(bet_group)
        return bet_group


class MemoryQuestionRepository(interfaces.QuestionRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get(self, question_id: str) -> Question | None:
        return next((q for q in self._store.questions if q.id == question_id), None)

    def list_for_group(self, bet_group_id: str) -> list[Question]:
        return sorted(
            (q for q in self._store.questions if q.bet_group_id == bet_group_id),
            key=lambda q: q.position,
        )

    def add(self, question: Question) -> Question:
        self._store.questions.append(question)
        return question


class MemoryPredictionRepository(interfaces.PredictionRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def find(self, participation_id: str, question_id: str) -> Prediction | None:
        return next(
            (
                p
                for p in self._store.predictions
                if p.participation_id == participation_id and p.question_id == question_id
            ),
            None,
        )

    def list_for_participation(self, participation_id: str) -> list[Prediction]:
        return [p for p in self._store.predictions if p.participation_id == participation_id]

    def list_for_question(self, question_id: str) -> list[Prediction]:
        return [p for p in self._store.predictions if p.question_id == question_id]

    def upsert(self, prediction: Prediction) -> Prediction:
        for index, existing in enumerate(self._store.predictions):
            if (
                existing.participation_id == prediction.participation_id
                and existing.question_id == prediction.question_id
            ):
                self._store.predictions[index] = prediction
                return prediction
        self._store.predictions.append(prediction)
        return prediction


class MemoryOutcomeRepository(interfaces.OutcomeRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def list_for_draw(self, draw_id: str) -> list[OutcomeEntry]:
        return [o for o in self._store.outcomes if o.draw_id == draw_id]

    def replace_for_draw(self, draw_id: str, entries: list[OutcomeEntry]) -> None:
        self._store.outcomes = [o for o in self._store.outcomes if o.draw_id != draw_id]
        self._store.outcomes.extend(entries)

    def add_many(self, entries: list[OutcomeEntry]) -> None:
        self._store.outcomes.extend(entries)

    def get_question_outcome(self, question_id: str) -> QuestionOutcome | None:
        return next(
            (o for o in self._store.question_outcomes if o.question_id == question_id), None
        )

    def put_question_outcome(self, outcome: QuestionOutcome) -> None:
        self._store.question_outcomes = [
            o for o in self._store.question_outcomes if o.question_id != outcome.question_id
        ]
        self._store.question_outcomes.append(outcome)


class MemoryScoreRepository(interfaces.ScoreRepository):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def list_for_participation(self, participation_id: str) -> list[ScoreEntry]:
        return [s for s in self._store.scores if s.participation_id == participation_id]

    def replace_for_questions(self, question_ids: list[str], entries: list[ScoreEntry]) -> None:
        targets = set(question_ids)
        self._store.scores = [s for s in self._store.scores if s.question_id not in targets]
        self._store.scores.extend(entries)


class MemoryRepositories(interfaces.Repositories):
    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        self.users = MemoryUserRepository(self.store)
        self.players = MemoryPlayerRepository(self.store)
        self.tournaments = MemoryTournamentRepository(self.store)
        self.draws = MemoryDrawRepository(self.store)
        self.participations = MemoryParticipationRepository(self.store)
        self.bet_groups = MemoryBetGroupRepository(self.store)
        self.questions = MemoryQuestionRepository(self.store)
        self.predictions = MemoryPredictionRepository(self.store)
        self.outcomes = MemoryOutcomeRepository(self.store)
        self.scores = MemoryScoreRepository(self.store)

    def commit(self) -> None:
        """Nothing to commit: the store is the truth while it lives in memory."""
