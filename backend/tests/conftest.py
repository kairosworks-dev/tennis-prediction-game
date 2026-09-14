from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import DEMO_PASSWORD

TOURNAMENT_ID = "roland-garros-2026"


@pytest.fixture
def client() -> TestClient:
    """A fresh app, and therefore a fresh store, per test."""
    return TestClient(create_app())


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
