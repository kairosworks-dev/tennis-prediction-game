"""Key user workflows, end to end over HTTP against the compose stack.

Each test passes alone and in any order. Ids are discovered by state, status
and answer type; nothing asserts on fixture names, player ids, point totals or
positions, only on before/after relationships.
"""

from __future__ import annotations

import httpx
import pytest
from conftest import (
    DEMO_PASSWORD,
    ORGANISER,
    PARTICIPANT,
    find_game,
    match_payload,
    match_questions,
    new_client,
    put_prediction,
    questions_in,
    random_email,
)


def _score_rows(client: httpx.Client, tournament_id: str) -> dict[str, dict]:
    breakdown = client.get(f"/tournaments/{tournament_id}/scores").json()
    return {row["question"]["id"]: row for g in breakdown["groups"] for row in g["rows"]}


def _own_ranking_total(client: httpx.Client, tournament_id: str) -> int:
    ranking = client.get(f"/tournaments/{tournament_id}/ranking").json()
    mine = [r for r in ranking if r["isCurrentUser"]]
    assert len(mine) == 1, "the signed-in participant should appear once in the ranking"
    return mine[0]["totalPoints"]


@pytest.mark.parametrize("email", [PARTICIPANT, ORGANISER])
def test_demo_accounts_sign_in_and_out(app_url: str, email: str) -> None:
    with new_client(app_url) as client:
        login = client.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert login.status_code == 200
        assert login.json()["user"]["email"] == email
        assert client.get("/me").json()["email"] == email

        assert client.post("/auth/logout").status_code == 204
        assert client.get("/me").json() is None


def test_wrong_password_is_refused(anonymous: httpx.Client) -> None:
    response = anonymous.post(
        "/auth/login", json={"email": PARTICIPANT, "password": "not-the-password"}
    )
    assert response.status_code == 422
    assert anonymous.get("/me").json() is None


def test_registration_requires_email_confirmation_before_joining(
    anonymous: httpx.Client, open_game: dict
) -> None:
    # Joining is exercised with the seeded account elsewhere because there is no
    # email-confirmation endpoint to verify a new address with (decision D14).
    registered = anonymous.post(
        "/auth/register",
        json={
            "email": random_email(),
            "password": "a-long-enough-password",
            "displayName": "Integration",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["requiresEmailVerification"] is True

    joined = anonymous.post(
        f"/tournaments/{open_game['tournament']['id']}/join",
        json={"tournamentId": open_game["tournament"]["id"]},
    )
    assert joined.status_code == 403


def test_join_open_game_once(participant: httpx.Client, open_game: dict) -> None:
    tournament_id = open_game["tournament"]["id"]
    body = {"tournamentId": tournament_id}

    # Idempotent across reruns against a long-lived stack: if the demo user has
    # already joined, only the duplicate-join rule is left to check.
    if open_game["participationId"] is None:
        first = participant.post(f"/tournaments/{tournament_id}/join", json=body)
        assert first.status_code == 201
        detail = participant.get(f"/tournaments/{tournament_id}").json()
        assert detail["participationId"] == first.json()["id"]

    assert participant.post(f"/tournaments/{tournament_id}/join", json=body).status_code == 409


def test_joining_a_running_game_is_refused(participant: httpx.Client) -> None:
    running = find_game(participant, "RUNNING")
    tournament_id = running["tournament"]["id"]
    response = participant.post(
        f"/tournaments/{tournament_id}/join", json={"tournamentId": tournament_id}
    )
    assert response.status_code == 403


def test_prediction_persists_and_second_put_replaces(
    participant: httpx.Client, running_game: dict
) -> None:
    tournament_id = running_game["tournament"]["id"]
    question = match_questions(participant, tournament_id)[0]
    first = match_payload(participant, tournament_id, question, 0)
    second = match_payload(participant, tournament_id, question, 1)

    stored = put_prediction(participant, tournament_id, question["id"], first)
    assert stored.status_code == 200, stored.text
    assert stored.json()["submittedAt"] is not None

    replaced = put_prediction(participant, tournament_id, question["id"], second)
    assert replaced.status_code == 200, replaced.text

    listed = participant.get(f"/tournaments/{tournament_id}/predictions").json()
    for_question = [p for p in listed if p["questionId"] == question["id"]]
    assert len(for_question) == 1
    assert for_question[0]["payload"] == second


def test_settled_group_refuses_predictions(participant: httpx.Client, running_game: dict) -> None:
    tournament_id = running_game["tournament"]["id"]
    locked = questions_in(participant, tournament_id, "SETTLED")[0]
    # The answer is well-formed for a match question; the group's status is
    # what must refuse it, so reuse any legal-looking payload shape.
    payload = {"kind": "CHAMPION", "playerId": "irrelevant"}
    if locked["answerType"] == "MATCH_RESULT" and locked["matchup"]:
        payload = match_payload(participant, tournament_id, locked, 0)
    response = put_prediction(participant, tournament_id, locked["id"], payload)
    assert response.status_code == 403


def test_participant_cannot_recalculate(participant: httpx.Client, running_game: dict) -> None:
    response = participant.post(
        f"/admin/tournaments/{running_game['tournament']['id']}/recalculate"
    )
    assert response.status_code == 403


def test_organiser_results_move_the_participants_score_and_ranking(
    participant: httpx.Client, organiser: httpx.Client, running_game: dict
) -> None:
    tournament_id = running_game["tournament"]["id"]

    # Use a match question not settled yet (the last one, so the persistence
    # test's question is left alone when there are two).
    rows = _score_rows(participant, tournament_id)
    candidates = [
        q
        for q in match_questions(participant, tournament_id)
        if rows.get(q["id"], {}).get("points") is None
    ]
    assert candidates, "expected an unsettled MATCH_RESULT question in the OPEN group"
    question = candidates[-1]
    answer = match_payload(participant, tournament_id, question, 0)

    assert put_prediction(participant, tournament_id, question["id"], answer).status_code == 200
    ranking_before = _own_ranking_total(participant, tournament_id)

    settled = organiser.put(
        f"/admin/questions/{question['id']}/outcome",
        json={"questionId": question["id"], "correctAnswer": answer, "note": None},
    )
    assert settled.status_code == 204
    recalculated = organiser.post(f"/admin/tournaments/{tournament_id}/recalculate")
    assert recalculated.status_code == 200

    row = _score_rows(participant, tournament_id)[question["id"]]
    assert isinstance(row["points"], int) and row["points"] > 0
    ranking_after = _own_ranking_total(participant, tournament_id)
    assert ranking_after - ranking_before == row["points"]

    breakdown = participant.get(f"/tournaments/{tournament_id}/scores").json()
    assert breakdown["total"] == ranking_after


def test_recalculating_twice_writes_the_same_number_of_entries(
    organiser: httpx.Client, running_game: dict
) -> None:
    path = f"/admin/tournaments/{running_game['tournament']['id']}/recalculate"
    first = organiser.post(path)
    second = organiser.post(path)
    assert first.status_code == second.status_code == 200
    assert first.json()["scoreEntriesWritten"] == second.json()["scoreEntriesWritten"]
