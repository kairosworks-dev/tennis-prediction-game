"""SQLAlchemy tables.

These exist only inside `repositories/`. The domain keeps its own dataclasses
and never learns that a database exists (AGENTS.md hard rule 4); the mapping
between the two lives in `sqlalchemy_repos.py`.

JSON columns carry the shapes the spec already models as JSON: prediction
payloads, the scoring profile, question options and a matchup.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, TypeDecorator
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UtcDateTime(TypeDecorator[datetime]):
    """A timestamp that survives a round trip through SQLite.

    SQLite has no timezone-aware type, so a plain `DateTime` column stores an
    aware datetime and returns a naive one — and the next comparison against
    `datetime.now(UTC)` raises. Everything is normalised to UTC on the way in
    and marked as UTC on the way out, which is also what spec 7.5 asks for.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)


class PlayerRow(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    country_code: Mapped[str] = mapped_column(String(3))
    tour: Mapped[str] = mapped_column(String)


class TournamentRow(Base):
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    surface: Mapped[str] = mapped_column(String)
    location: Mapped[str] = mapped_column(String)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    signup_deadline: Mapped[datetime] = mapped_column(UtcDateTime)
    visibility: Mapped[str] = mapped_column(String)
    join_code: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    rules_markdown: Mapped[str] = mapped_column(String, default="")
    scoring_profile: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime)


class DrawRow(Base):
    __tablename__ = "draws"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    tour: Mapped[str] = mapped_column(String)
    draw_size: Mapped[int] = mapped_column(Integer)
    best_of: Mapped[int] = mapped_column(Integer)
    official_draw_url: Mapped[str | None] = mapped_column(String, nullable=True)


class DrawSectionRow(Base):
    __tablename__ = "draw_sections"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    draw_id: Mapped[str] = mapped_column(ForeignKey("draws.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)


class DrawEntryRow(Base):
    __tablename__ = "draw_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    draw_id: Mapped[str] = mapped_column(ForeignKey("draws.id"), index=True)
    section_id: Mapped[str] = mapped_column(ForeignKey("draw_sections.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ParticipationRow(Base):
    __tablename__ = "participations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    joined_at: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String)


class BetGroupRow(Base):
    __tablename__ = "bet_groups"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tournament_id: Mapped[str] = mapped_column(ForeignKey("tournaments.id"), index=True)
    kind: Mapped[str] = mapped_column(String)
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String)
    intro_markdown: Mapped[str] = mapped_column(String, default="")
    deadline: Mapped[datetime] = mapped_column(UtcDateTime)
    status: Mapped[str] = mapped_column(String)


class QuestionRow(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bet_group_id: Mapped[str] = mapped_column(ForeignKey("bet_groups.id"), index=True)
    draw_id: Mapped[str | None] = mapped_column(ForeignKey("draws.id"), nullable=True)
    family: Mapped[str] = mapped_column(String)
    kind: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt: Mapped[str] = mapped_column(String)
    answer_type: Mapped[str] = mapped_column(String)
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    matchup: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    points_hint: Mapped[str] = mapped_column(String, default="")
    deadline_override: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class PredictionRow(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    participation_id: Mapped[str] = mapped_column(ForeignKey("participations.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime)


class OutcomeEntryRow(Base):
    __tablename__ = "outcome_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draw_id: Mapped[str] = mapped_column(ForeignKey("draws.id"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    round_reached: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class QuestionOutcomeRow(Base):
    __tablename__ = "question_outcomes"

    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    correct_answer: Mapped[dict[str, Any]] = mapped_column(JSON)
    settled_at: Mapped[datetime] = mapped_column(UtcDateTime)
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class ScoreEntryRow(Base):
    __tablename__ = "score_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    participation_id: Mapped[str] = mapped_column(ForeignKey("participations.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    points: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String)
    calculated_at: Mapped[datetime] = mapped_column(UtcDateTime)
