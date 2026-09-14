"""Test fixtures.

The `repositories` fixture is parameterised over both implementations, so the
whole API suite runs twice: once against the in-memory repositories from step 3
and once against SQLAlchemy on SQLite. That is step 4's definition of done — a
service or domain change that only works for one of them fails here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.interfaces import Repositories
from app.repositories.memory import MemoryRepositories
from app.repositories.models import Base
from app.repositories.sqlalchemy_repos import (
    SqlAlchemyRepositories,
    create_session_factory,
    create_sqlite_engine,
)
from app.seed import DEMO_PASSWORD

TOURNAMENT_ID = "roland-garros-2026"


@pytest.fixture(params=["memory", "sqlite"])
def repositories(request: pytest.FixtureRequest) -> Iterator[Repositories]:
    if request.param == "memory":
        yield MemoryRepositories()
        return

    # A fresh in-memory database per test: no file, no leakage between tests.
    engine = create_sqlite_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = create_session_factory(engine)()
    try:
        yield SqlAlchemyRepositories(session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(repositories: Repositories) -> TestClient:
    return TestClient(create_app(repositories=repositories))


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
