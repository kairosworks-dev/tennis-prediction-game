"""Fixtures for the integration suite.

These tests talk HTTP to a running stack (the compose app plus Postgres) and
import nothing from the application. The only things they know about the seed
are its documented contract: two demo accounts, one game open for signup, and
one running game with an OPEN group holding a match-result question and a
SETTLED group. Ids are discovered by state, never hard-coded.
"""

from __future__ import annotations

import os
import time
import uuid
from urllib.parse import urlparse

import httpx
import pytest

DEMO_PASSWORD = "deuce-demo-password"
PARTICIPANT = "you@example.com"
ORGANISER = "organiser@example.com"
LOCAL_HOSTS = {"localhost", "127.0.0.1"}


def _app_url() -> str:
    default = f"http://localhost:{os.environ.get('APP_PORT', '8000')}"
    return os.environ.get("APP_URL", default).rstrip("/")


def pytest_configure(config: pytest.Config) -> None:
    """Refuse a non-local target before anything can send a request."""
    host = urlparse(_app_url()).hostname
    if host not in LOCAL_HOSTS and os.environ.get("INTEGRATION_ALLOW_REMOTE") != "1":
        raise pytest.UsageError(
            f"APP_URL host {host!r} is not localhost/127.0.0.1; these tests create "
            "accounts and change scores. Set INTEGRATION_ALLOW_REMOTE=1 to run anyway."
        )


@pytest.fixture(scope="session")
def app_url() -> str:
    return _app_url()


@pytest.fixture(scope="session", autouse=True)
def stack_ready(app_url: str) -> None:
    """Wait for GET /ready (root, not /api) to answer 200, bounded."""
    timeout = float(os.environ.get("READY_TIMEOUT", "90"))
    deadline = time.monotonic() + timeout
    last = "no response"
    while True:
        try:
            response = httpx.get(f"{app_url}/ready", timeout=5)
            if response.status_code == 200:
                return
            last = f"HTTP {response.status_code}"
        except httpx.HTTPError as error:
            last = f"no response ({type(error).__name__})"
        if time.monotonic() >= deadline:
            pytest.exit(
                f"Stack not ready: GET {app_url}/ready did not return 200 within "
                f"{timeout:g}s (last status seen: {last})",
                returncode=1,
            )
        time.sleep(1)


def new_client(app_url: str) -> httpx.Client:
    return httpx.Client(base_url=f"{app_url}/api", timeout=30)


def signed_in(app_url: str, email: str) -> httpx.Client:
    client = new_client(app_url)
    response = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, f"demo account {email} cannot sign in: {response.text}"
    return client


@pytest.fixture
def anonymous(app_url: str):
    with new_client(app_url) as client:
        yield client


@pytest.fixture
def participant(app_url: str):
    client = signed_in(app_url, PARTICIPANT)
    yield client
    client.close()


@pytest.fixture
def organiser(app_url: str):
    client = signed_in(app_url, ORGANISER)
    yield client
    client.close()


def find_game(client: httpx.Client, state: str) -> dict:
    games = client.get("/tournaments").json()
    found = [g for g in games if g["state"] == state]
    assert found, (
        f"seed precondition: expected a game in state {state}, "
        f"saw states {sorted({g['state'] for g in games})}"
    )
    return found[0]


@pytest.fixture
def open_game(participant: httpx.Client) -> dict:
    return find_game(participant, "OPEN_FOR_SIGNUP")


@pytest.fixture
def running_game(participant: httpx.Client) -> dict:
    return find_game(participant, "RUNNING")


def questions_in(client: httpx.Client, tournament_id: str, group_status: str) -> list[dict]:
    groups = client.get(f"/tournaments/{tournament_id}/bet-groups").json()
    matching = [g for g in groups if g["status"] == group_status]
    assert matching, (
        f"seed precondition: expected a {group_status} bet group in the running game, "
        f"saw {sorted(g['status'] for g in groups)}"
    )
    out: list[dict] = []
    for group in matching:
        out += client.get(f"/tournaments/{tournament_id}/bet-groups/{group['id']}/questions").json()
    return out


def match_questions(client: httpx.Client, tournament_id: str) -> list[dict]:
    found = [
        q
        for q in questions_in(client, tournament_id, "OPEN")
        if q["answerType"] == "MATCH_RESULT" and q["matchup"]
    ]
    assert found, "seed precondition: expected a MATCH_RESULT question in the OPEN group"
    return found


def match_payload(client: httpx.Client, tournament_id: str, question: dict, variant: int) -> dict:
    """A legal GENERIC_MATCH_RESULT answer; variant 0 and 1 differ in the set score."""
    draws = client.get(f"/tournaments/{tournament_id}/draws").json()
    draw = next(d for d in draws if d["id"] == question["drawId"])
    best_of_five = draw["bestOf"] == 5
    set_score = [("3-0", "3-1"), ("2-0", "2-1")][0 if best_of_five else 1][variant]
    return {
        "kind": "GENERIC_MATCH_RESULT",
        "winnerId": question["matchup"][0],
        "setScore": set_score,
    }


def put_prediction(
    client: httpx.Client, tournament_id: str, question_id: str, payload: dict
) -> httpx.Response:
    return client.put(
        f"/tournaments/{tournament_id}/questions/{question_id}/prediction",
        json={
            "tournamentId": tournament_id,
            "questionId": question_id,
            "payload": payload,
            "asDraft": False,
        },
    )


def random_email() -> str:
    return f"it-{uuid.uuid4().hex[:12]}@example.com"
