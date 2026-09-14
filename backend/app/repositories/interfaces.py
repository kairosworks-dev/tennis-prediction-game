"""Persistence interfaces.

Defined once, implemented twice: `memory` in step 3 and `sqlalchemy` in step 4.
Step 4 swaps the implementation without touching `services/` or `domain/`, so
nothing here may leak a storage detail — no sessions, no queries, no ORM types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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


class UserRepository(ABC):
    @abstractmethod
    def get(self, user_id: str) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def list_all(self) -> list[User]: ...


class PlayerRepository(ABC):
    @abstractmethod
    def get(self, player_id: str) -> Player | None: ...

    @abstractmethod
    def list_all(self) -> list[Player]: ...

    @abstractmethod
    def add(self, player: Player) -> Player: ...


class TournamentRepository(ABC):
    @abstractmethod
    def get(self, tournament_id: str) -> Tournament | None: ...

    @abstractmethod
    def list_all(self) -> list[Tournament]: ...

    @abstractmethod
    def add(self, tournament: Tournament) -> Tournament: ...


class DrawRepository(ABC):
    @abstractmethod
    def get(self, draw_id: str) -> Draw | None: ...

    @abstractmethod
    def list_for_tournament(self, tournament_id: str) -> list[Draw]: ...

    @abstractmethod
    def list_sections(self, draw_id: str) -> list[DrawSection]: ...

    @abstractmethod
    def list_entries(self, draw_id: str) -> list[DrawEntry]: ...

    @abstractmethod
    def add(self, draw: Draw) -> Draw: ...

    @abstractmethod
    def add_section(self, section: DrawSection) -> DrawSection: ...

    @abstractmethod
    def add_entry(self, entry: DrawEntry) -> DrawEntry: ...


class ParticipationRepository(ABC):
    @abstractmethod
    def get(self, participation_id: str) -> Participation | None: ...

    @abstractmethod
    def find(self, tournament_id: str, user_id: str) -> Participation | None: ...

    @abstractmethod
    def list_for_tournament(self, tournament_id: str) -> list[Participation]: ...

    @abstractmethod
    def add(self, participation: Participation) -> Participation: ...


class BetGroupRepository(ABC):
    @abstractmethod
    def get(self, bet_group_id: str) -> BetGroup | None: ...

    @abstractmethod
    def list_for_tournament(self, tournament_id: str) -> list[BetGroup]: ...

    @abstractmethod
    def add(self, bet_group: BetGroup) -> BetGroup: ...


class QuestionRepository(ABC):
    @abstractmethod
    def get(self, question_id: str) -> Question | None: ...

    @abstractmethod
    def list_for_group(self, bet_group_id: str) -> list[Question]: ...

    @abstractmethod
    def add(self, question: Question) -> Question: ...


class PredictionRepository(ABC):
    @abstractmethod
    def find(self, participation_id: str, question_id: str) -> Prediction | None: ...

    @abstractmethod
    def list_for_participation(self, participation_id: str) -> list[Prediction]: ...

    @abstractmethod
    def list_for_question(self, question_id: str) -> list[Prediction]: ...

    @abstractmethod
    def upsert(self, prediction: Prediction) -> Prediction: ...


class OutcomeRepository(ABC):
    @abstractmethod
    def list_for_draw(self, draw_id: str) -> list[OutcomeEntry]: ...

    @abstractmethod
    def replace_for_draw(self, draw_id: str, entries: list[OutcomeEntry]) -> None: ...

    @abstractmethod
    def add_many(self, entries: list[OutcomeEntry]) -> None: ...

    @abstractmethod
    def get_question_outcome(self, question_id: str) -> QuestionOutcome | None: ...

    @abstractmethod
    def put_question_outcome(self, outcome: QuestionOutcome) -> None: ...


class ScoreRepository(ABC):
    @abstractmethod
    def list_for_participation(self, participation_id: str) -> list[ScoreEntry]: ...

    @abstractmethod
    def replace_for_questions(self, question_ids: list[str], entries: list[ScoreEntry]) -> None: ...


class Repositories(ABC):
    """Everything the service layer needs, in one place.

    Passing one object rather than ten keeps service signatures readable and
    gives step 4 a single seam to swap.
    """

    users: UserRepository
    players: PlayerRepository
    tournaments: TournamentRepository
    draws: DrawRepository
    participations: ParticipationRepository
    bet_groups: BetGroupRepository
    questions: QuestionRepository
    predictions: PredictionRepository
    outcomes: OutcomeRepository
    scores: ScoreRepository

    @abstractmethod
    def commit(self) -> None:
        """No-op in memory; a transaction boundary once there is a database."""
