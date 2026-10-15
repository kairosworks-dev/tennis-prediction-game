"""Postgres support (issue #1): URL handling, schema ownership and round trips.

Most of this runs on any database; the tests that need a real Postgres use the
`repositories` fixture's postgres parameter or skip without `TEST_DATABASE_URL`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect

from app.domain.entities import ScoringProfile
from app.main import build_repository_scope
from app.repositories.interfaces import Repositories
from app.repositories.models import Base
from app.repositories.sqlalchemy_repos import create_db_engine, normalise_database_url
from app.seed import seed_demo_game
from tests.conftest import TEST_DATABASE_URL, TOURNAMENT_ID, _postgres_test_url


class TestUrlNormalisation:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("postgresql://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
            ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
            ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
            ("sqlite:///./tennis.db", "sqlite:///./tennis.db"),
        ],
    )
    def test_normalise(self, given: str, expected: str) -> None:
        assert normalise_database_url(given) == expected

    def test_bare_postgres_url_builds_an_engine_without_psycopg2(self) -> None:
        # create_engine imports the driver but connects lazily: no server needed.
        engine = create_db_engine("postgresql://u:p@localhost:1/db")
        assert engine.url.drivername == "postgresql+psycopg"
        engine.dispose()


needs_postgres = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set")


@needs_postgres
class TestSchemaOwnership:
    def test_start_up_does_not_create_tables_on_postgres(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        url = _postgres_test_url()
        engine = create_db_engine(url)
        Base.metadata.drop_all(engine)
        monkeypatch.setenv("DATABASE_URL", url)
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            build_repository_scope("sqlalchemy")
        assert set(inspect(engine).get_table_names()) == set()
        engine.dispose()


class TestRoundTrips:
    def test_datetimes_come_back_as_aware_utc(self, repositories: Repositories) -> None:
        seed_demo_game(repositories)
        tournament = repositories.tournaments.get(TOURNAMENT_ID)
        assert tournament is not None
        for value in (tournament.signup_deadline, tournament.created_at):
            assert value.tzinfo is not None
            assert value.utcoffset() == timedelta(0)

    def test_a_non_utc_datetime_is_stored_as_the_same_instant(
        self, repositories: Repositories
    ) -> None:
        seed_demo_game(repositories)
        user = repositories.users.get_by_email("you@example.com")
        assert user is not None
        plus_two = datetime(2026, 5, 1, 12, 0, tzinfo=timezone(timedelta(hours=2)))
        participation = repositories.participations.list_for_tournament(TOURNAMENT_ID)[0]
        prediction = repositories.predictions.list_for_participation(participation.id)[0]
        repositories.predictions.upsert(replace(prediction, updated_at=plus_two))
        _drop_identity_map(repositories)
        reloaded = repositories.predictions.find(participation.id, prediction.question_id)
        assert reloaded is not None
        assert reloaded.updated_at == plus_two
        assert reloaded.updated_at.tzinfo is not None
        assert reloaded.updated_at == datetime(2026, 5, 1, 10, 0, tzinfo=UTC)

    def test_prediction_payloads_round_trip_equal(self, repositories: Repositories) -> None:
        seed_demo_game(repositories)
        participation = repositories.participations.list_for_tournament(TOURNAMENT_ID)[0]
        before = repositories.predictions.list_for_participation(participation.id)
        assert before
        _drop_identity_map(repositories)
        assert repositories.predictions.list_for_participation(participation.id) == before

    def test_scoring_profile_round_trips_equal(self, repositories: Repositories) -> None:
        seed_demo_game(repositories)
        tournament = repositories.tournaments.get(TOURNAMENT_ID)
        assert tournament is not None
        custom = replace(
            tournament,
            id="custom-profile",
            scoring_profile=ScoringProfile(champion_points=11, underperformer_points=(9, 8, 7)),
        )
        repositories.tournaments.add(custom)
        _drop_identity_map(repositories)
        assert repositories.tournaments.get("custom-profile") == custom


def _drop_identity_map(repositories: Repositories) -> None:
    """Force the next read to hit the database rather than the session's cache."""
    session = getattr(repositories, "_session", None)
    if session is not None:
        session.expire_all()
