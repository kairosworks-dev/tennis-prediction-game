"""SQLAlchemy repository implementations (step 4).

The second implementation of the interfaces defined in `interfaces.py`. No
service or domain code changes to swap these in — `create_app` picks one, and
the same test suite runs against both.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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
from app.repositories import interfaces, mapping, models


class _Base:
    def __init__(self, session: Session) -> None:
        self._session = session


class SqlUserRepository(_Base, interfaces.UserRepository):
    def get(self, user_id: str) -> User | None:
        row = self._session.get(models.UserRow, user_id)
        return mapping.user_to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        stmt = select(models.UserRow).where(models.UserRow.email == email.strip().lower())
        row = self._session.scalars(stmt).first()
        return mapping.user_to_domain(row) if row else None

    def add(self, user: User) -> User:
        self._session.add(mapping.user_to_row(user))
        self._session.flush()
        return user

    def list_all(self) -> list[User]:
        return [mapping.user_to_domain(r) for r in self._session.scalars(select(models.UserRow))]


class SqlPlayerRepository(_Base, interfaces.PlayerRepository):
    def get(self, player_id: str) -> Player | None:
        row = self._session.get(models.PlayerRow, player_id)
        return mapping.player_to_domain(row) if row else None

    def list_all(self) -> list[Player]:
        return [
            mapping.player_to_domain(r) for r in self._session.scalars(select(models.PlayerRow))
        ]

    def add(self, player: Player) -> Player:
        self._session.add(mapping.player_to_row(player))
        self._session.flush()
        return player


class SqlTournamentRepository(_Base, interfaces.TournamentRepository):
    def get(self, tournament_id: str) -> Tournament | None:
        row = self._session.get(models.TournamentRow, tournament_id)
        return mapping.tournament_to_domain(row) if row else None

    def list_all(self) -> list[Tournament]:
        return [
            mapping.tournament_to_domain(r)
            for r in self._session.scalars(select(models.TournamentRow))
        ]

    def add(self, tournament: Tournament) -> Tournament:
        self._session.add(mapping.tournament_to_row(tournament))
        self._session.flush()
        return tournament


class SqlDrawRepository(_Base, interfaces.DrawRepository):
    def get(self, draw_id: str) -> Draw | None:
        row = self._session.get(models.DrawRow, draw_id)
        return mapping.draw_to_domain(row) if row else None

    def list_for_tournament(self, tournament_id: str) -> list[Draw]:
        stmt = select(models.DrawRow).where(models.DrawRow.tournament_id == tournament_id)
        return [mapping.draw_to_domain(r) for r in self._session.scalars(stmt)]

    def list_sections(self, draw_id: str) -> list[DrawSection]:
        stmt = (
            select(models.DrawSectionRow)
            .where(models.DrawSectionRow.draw_id == draw_id)
            .order_by(models.DrawSectionRow.index)
        )
        return [mapping.section_to_domain(r) for r in self._session.scalars(stmt)]

    def list_entries(self, draw_id: str) -> list[DrawEntry]:
        stmt = select(models.DrawEntryRow).where(models.DrawEntryRow.draw_id == draw_id)
        return [mapping.entry_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, draw: Draw) -> Draw:
        self._session.add(mapping.draw_to_row(draw))
        self._session.flush()
        return draw

    def add_section(self, section: DrawSection) -> DrawSection:
        self._session.add(mapping.section_to_row(section))
        self._session.flush()
        return section

    def add_entry(self, entry: DrawEntry) -> DrawEntry:
        self._session.add(mapping.entry_to_row(entry))
        self._session.flush()
        return entry


class SqlParticipationRepository(_Base, interfaces.ParticipationRepository):
    def get(self, participation_id: str) -> Participation | None:
        row = self._session.get(models.ParticipationRow, participation_id)
        return mapping.participation_to_domain(row) if row else None

    def find(self, tournament_id: str, user_id: str) -> Participation | None:
        stmt = select(models.ParticipationRow).where(
            models.ParticipationRow.tournament_id == tournament_id,
            models.ParticipationRow.user_id == user_id,
        )
        row = self._session.scalars(stmt).first()
        return mapping.participation_to_domain(row) if row else None

    def list_for_tournament(self, tournament_id: str) -> list[Participation]:
        stmt = select(models.ParticipationRow).where(
            models.ParticipationRow.tournament_id == tournament_id
        )
        return [mapping.participation_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, participation: Participation) -> Participation:
        self._session.add(mapping.participation_to_row(participation))
        self._session.flush()
        return participation


class SqlBetGroupRepository(_Base, interfaces.BetGroupRepository):
    def get(self, bet_group_id: str) -> BetGroup | None:
        row = self._session.get(models.BetGroupRow, bet_group_id)
        return mapping.bet_group_to_domain(row) if row else None

    def list_for_tournament(self, tournament_id: str) -> list[BetGroup]:
        stmt = (
            select(models.BetGroupRow)
            .where(models.BetGroupRow.tournament_id == tournament_id)
            .order_by(models.BetGroupRow.deadline)
        )
        return [mapping.bet_group_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, bet_group: BetGroup) -> BetGroup:
        self._session.add(mapping.bet_group_to_row(bet_group))
        self._session.flush()
        return bet_group


class SqlQuestionRepository(_Base, interfaces.QuestionRepository):
    def get(self, question_id: str) -> Question | None:
        row = self._session.get(models.QuestionRow, question_id)
        return mapping.question_to_domain(row) if row else None

    def list_for_group(self, bet_group_id: str) -> list[Question]:
        stmt = (
            select(models.QuestionRow)
            .where(models.QuestionRow.bet_group_id == bet_group_id)
            .order_by(models.QuestionRow.position)
        )
        return [mapping.question_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, question: Question) -> Question:
        self._session.add(mapping.question_to_row(question))
        self._session.flush()
        return question


class SqlPredictionRepository(_Base, interfaces.PredictionRepository):
    def find(self, participation_id: str, question_id: str) -> Prediction | None:
        stmt = select(models.PredictionRow).where(
            models.PredictionRow.participation_id == participation_id,
            models.PredictionRow.question_id == question_id,
        )
        row = self._session.scalars(stmt).first()
        return mapping.prediction_to_domain(row) if row else None

    def list_for_participation(self, participation_id: str) -> list[Prediction]:
        stmt = select(models.PredictionRow).where(
            models.PredictionRow.participation_id == participation_id
        )
        return [mapping.prediction_to_domain(r) for r in self._session.scalars(stmt)]

    def list_for_question(self, question_id: str) -> list[Prediction]:
        stmt = select(models.PredictionRow).where(
            models.PredictionRow.question_id == question_id
        )
        return [mapping.prediction_to_domain(r) for r in self._session.scalars(stmt)]

    def upsert(self, prediction: Prediction) -> Prediction:
        stmt = select(models.PredictionRow).where(
            models.PredictionRow.participation_id == prediction.participation_id,
            models.PredictionRow.question_id == prediction.question_id,
        )
        existing = self._session.scalars(stmt).first()
        if existing is not None:
            existing.payload = mapping.payload_to_json(prediction.payload)
            existing.submitted_at = prediction.submitted_at
            existing.updated_at = prediction.updated_at
        else:
            self._session.add(mapping.prediction_to_row(prediction))
        self._session.flush()
        return prediction


class SqlOutcomeRepository(_Base, interfaces.OutcomeRepository):
    def list_for_draw(self, draw_id: str) -> list[OutcomeEntry]:
        stmt = select(models.OutcomeEntryRow).where(models.OutcomeEntryRow.draw_id == draw_id)
        return [mapping.outcome_to_domain(r) for r in self._session.scalars(stmt)]

    def replace_for_draw(self, draw_id: str, entries: list[OutcomeEntry]) -> None:
        self._session.execute(
            delete(models.OutcomeEntryRow).where(models.OutcomeEntryRow.draw_id == draw_id)
        )
        self.add_many(entries)

    def add_many(self, entries: list[OutcomeEntry]) -> None:
        for entry in entries:
            self._session.add(mapping.outcome_to_row(entry))
        self._session.flush()

    def get_question_outcome(self, question_id: str) -> QuestionOutcome | None:
        row = self._session.get(models.QuestionOutcomeRow, question_id)
        return mapping.question_outcome_to_domain(row) if row else None

    def put_question_outcome(self, outcome: QuestionOutcome) -> None:
        self._session.execute(
            delete(models.QuestionOutcomeRow).where(
                models.QuestionOutcomeRow.question_id == outcome.question_id
            )
        )
        self._session.add(mapping.question_outcome_to_row(outcome))
        self._session.flush()


class SqlScoreRepository(_Base, interfaces.ScoreRepository):
    def list_for_participation(self, participation_id: str) -> list[ScoreEntry]:
        stmt = select(models.ScoreEntryRow).where(
            models.ScoreEntryRow.participation_id == participation_id
        )
        return [mapping.score_to_domain(r) for r in self._session.scalars(stmt)]

    def replace_for_questions(self, question_ids: list[str], entries: list[ScoreEntry]) -> None:
        if question_ids:
            self._session.execute(
                delete(models.ScoreEntryRow).where(
                    models.ScoreEntryRow.question_id.in_(question_ids)
                )
            )
        for entry in entries:
            self._session.add(mapping.score_to_row(entry))
        self._session.flush()


class SqlAlchemyRepositories(interfaces.Repositories):
    def __init__(self, session: Session) -> None:
        self._session = session
        self.users = SqlUserRepository(session)
        self.players = SqlPlayerRepository(session)
        self.tournaments = SqlTournamentRepository(session)
        self.draws = SqlDrawRepository(session)
        self.participations = SqlParticipationRepository(session)
        self.bet_groups = SqlBetGroupRepository(session)
        self.questions = SqlQuestionRepository(session)
        self.predictions = SqlPredictionRepository(session)
        self.outcomes = SqlOutcomeRepository(session)
        self.scores = SqlScoreRepository(session)

    def commit(self) -> None:
        self._session.commit()


def create_sqlite_engine(url: str = "sqlite:///./tennis.db") -> Engine:
    """Two SQLite quirks, neither of them an application decision.

    `check_same_thread` because TestClient and uvicorn both touch the
    connection from a worker thread. `StaticPool` because an in-memory
    database lives inside its connection — without it, `create_all` builds the
    schema on one connection and the session opens a second, empty one.
    """
    connect_args = {"check_same_thread": False}
    if url in {"sqlite://", "sqlite:///:memory:"}:
        return create_engine(url, connect_args=connect_args, poolclass=StaticPool)
    return create_engine(url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
