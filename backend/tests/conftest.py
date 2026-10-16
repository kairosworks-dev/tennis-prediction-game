"""Test fixtures.

The `repositories` fixture is parameterised over the implementations, so the
whole API suite runs once per implementation: in-memory (step 3), SQLAlchemy on
SQLite (step 4) and, when `TEST_DATABASE_URL` names a Postgres database,
SQLAlchemy on Postgres. Without that variable the Postgres parameter is skipped.
A service or domain change that only works for one of them fails here.

`TEST_DATABASE_URL` must be a throwaway database: every Postgres test drops and
recreates the whole schema. It is refused if it equals `DATABASE_URL`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app
from app.providers.clock import FixedClock
from app.repositories.interfaces import Repositories
from app.repositories.memory import MemoryRepositories
from app.repositories.models import Base
from app.repositories.sqlalchemy_repos import (
    SqlAlchemyRepositories,
    create_db_engine,
    create_session_factory,
    normalise_database_url,
)
from app.seed import DEMO_PASSWORD

TOURNAMENT_ID = "roland-garros-2026"


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

POSTGRES_PARAM = pytest.param(
    "postgres",
    marks=pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is not set"),
)


def _postgres_test_url() -> str:
    assert TEST_DATABASE_URL
    url = normalise_database_url(TEST_DATABASE_URL)
    live = os.environ.get("DATABASE_URL")
    if live and normalise_database_url(live) == url:
        raise pytest.UsageError(
            "TEST_DATABASE_URL must not be the database DATABASE_URL points at: "
            "the suite drops every table in it."
        )
    return url


@pytest.fixture(params=["memory", "sqlite", POSTGRES_PARAM])
def repositories(request: pytest.FixtureRequest) -> Iterator[Repositories]:
    if request.param == "memory":
        yield MemoryRepositories()
        return

    if request.param == "postgres":
        # Every test starts from an empty schema, so none sees another's rows.
        engine = create_db_engine(_postgres_test_url())
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    else:
        # A fresh in-memory database per test: no file, no leakage between tests.
        engine = create_db_engine("sqlite://")
        Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        yield SqlAlchemyRepositories(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def clock() -> FixedClock:
    """The app's clock, frozen at the moment the test starts.

    Tests move it with `set` / `advance` to stand on either side of a deadline.
    """
    return FixedClock(datetime.now(UTC))


@pytest.fixture
def client(repositories: Repositories, clock: FixedClock) -> TestClient:
    app = create_app(repositories=repositories)
    app.dependency_overrides[get_clock] = lambda: clock
    return TestClient(app)


@pytest.fixture
def participant(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login", json={"email": "you@example.com", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def organiser(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login", json={"email": "organiser@example.com", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client
