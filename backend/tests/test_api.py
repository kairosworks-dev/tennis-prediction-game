"""The API through its own HTTP surface.

Exercises the contract as the frontend will call it, including the rules that
must not be reachable from a component: authorisation, visibility and the
validation in spec 5.3.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import build_repository_scope, create_app
from app.seed import DEMO_PASSWORD
from tests.conftest import TOURNAMENT_ID


class TestAuthentication:
    def test_an_anonymous_visitor_gets_null_not_an_error(self, client: TestClient) -> None:
        response = client.get("/api/me")
        assert response.status_code == 200
        assert response.json() is None

    def test_a_protected_route_refuses_an_anonymous_caller(self, client: TestClient) -> None:
        response = client.get("/api/tournaments")
        assert response.status_code == 401
        assert response.json()["title"] == "Not signed in"

    def test_sign_in_sets_a_session(self, client: TestClient) -> None:
        client.post(
            "/api/auth/login", json={"email": "you@example.com", "password": DEMO_PASSWORD}
        )
        assert client.get("/api/me").json()["displayName"] == "You"

    def test_a_wrong_password_is_refused(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/login", json={"email": "you@example.com", "password": "wrong"}
        )
        assert response.status_code == 422

    def test_sign_out_clears_the_session(self, participant: TestClient) -> None:
        assert participant.post("/api/auth/logout").status_code == 204
        assert participant.get("/api/me").json() is None

    def test_registration_reports_field_errors(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "password": "short", "displayName": "New"},
        )
        assert response.status_code == 422
        assert "password" in response.json()["errors"]

    def test_a_duplicate_address_conflicts(self, client: TestClient) -> None:
        response = client.post(
            "/api/auth/register",
            json={
                "email": "you@example.com",
                "password": "a-long-enough-password",
                "displayName": "Impostor",
            },
        )
        assert response.status_code == 409


class TestLandingPage:
    def test_the_teaser_needs_no_session(self, client: TestClient) -> None:
        response = client.get("/api/public/next-game")
        assert response.status_code == 200
        assert response.json()["name"]


class TestGames:
    def test_the_game_list_carries_the_three_states(self, participant: TestClient) -> None:
        rows = participant.get("/api/tournaments").json()
        assert len(rows) >= 2
        assert {"RUNNING", "OPEN_FOR_SIGNUP"} <= {row["state"] for row in rows}

    def test_a_participant_never_sees_a_join_code(self, participant: TestClient) -> None:
        detail = participant.get(f"/api/tournaments/{TOURNAMENT_ID}").json()
        assert detail["tournament"]["joinCode"] is None

    def test_joining_a_closed_game_is_refused(self, participant: TestClient) -> None:
        response = participant.post(
            f"/api/tournaments/{TOURNAMENT_ID}/join", json={"tournamentId": TOURNAMENT_ID}
        )
        assert response.status_code == 403


class TestPlay:
    def test_a_draw_has_eight_sections_that_partition_the_field(
        self, participant: TestClient
    ) -> None:
        draws = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
        assert len(draws) == 2
        sections = participant.get(
            f"/api/tournaments/{TOURNAMENT_ID}/draws/{draws[0]['id']}/entries"
        ).json()
        assert [s["section"]["index"] for s in sections] == [1, 2, 3, 4, 5, 6, 7, 8]
        assert sum(len(s["entries"]) for s in sections) == draws[0]["drawSize"]

    def test_bet_groups_come_back_in_deadline_order(self, participant: TestClient) -> None:
        groups = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/bet-groups").json()
        deadlines = [g["deadline"] for g in groups]
        assert deadlines == sorted(deadlines)

    def _open_question(self, client: TestClient) -> dict:
        groups = client.get(f"/api/tournaments/{TOURNAMENT_ID}/bet-groups").json()
        open_group = next(g for g in groups if g["status"] == "OPEN")
        questions = client.get(
            f"/api/tournaments/{TOURNAMENT_ID}/bet-groups/{open_group['id']}/questions"
        ).json()
        return next(q for q in questions if q["answerType"] == "MATCH_RESULT")

    def test_a_prediction_can_be_submitted_and_replaced(self, participant: TestClient) -> None:
        question = self._open_question(participant)
        draws = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
        best_of = next(d["bestOf"] for d in draws if d["id"] == question["drawId"])
        score = "3-1" if best_of == 5 else "2-1"

        url = f"/api/tournaments/{TOURNAMENT_ID}/questions/{question['id']}/prediction"
        body = {
            "tournamentId": TOURNAMENT_ID,
            "questionId": question["id"],
            "payload": {
                "kind": "GENERIC_MATCH_RESULT",
                "winnerId": question["matchup"][0],
                "setScore": score,
            },
            "asDraft": False,
        }
        first = participant.put(url, json=body)
        assert first.status_code == 200, first.text
        assert first.json()["submittedAt"] is not None

        second = participant.put(url, json={**body, "asDraft": True})
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["submittedAt"] is None

        mine = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/predictions").json()
        assert len([p for p in mine if p["questionId"] == question["id"]]) == 1

    def test_an_illegal_set_score_is_rejected(self, participant: TestClient) -> None:
        question = self._open_question(participant)
        draws = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
        best_of = next(d["bestOf"] for d in draws if d["id"] == question["drawId"])
        illegal = "2-0" if best_of == 5 else "3-0"

        response = participant.put(
            f"/api/tournaments/{TOURNAMENT_ID}/questions/{question['id']}/prediction",
            json={
                "tournamentId": TOURNAMENT_ID,
                "questionId": question["id"],
                "payload": {
                    "kind": "GENERIC_MATCH_RESULT",
                    "winnerId": question["matchup"][0],
                    "setScore": illegal,
                },
                "asDraft": False,
            },
        )
        assert response.status_code == 422
        assert "not a legal result" in response.json()["detail"]

    def test_a_locked_group_refuses_a_prediction(self, participant: TestClient) -> None:
        groups = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/bet-groups").json()
        settled = next(g for g in groups if g["status"] == "SETTLED")
        questions = participant.get(
            f"/api/tournaments/{TOURNAMENT_ID}/bet-groups/{settled['id']}/questions"
        ).json()
        question = next(q for q in questions if q["kind"] == "UNDERPERFORMER")
        entries = participant.get(
            f"/api/tournaments/{TOURNAMENT_ID}/draws/{question['drawId']}/entries"
        ).json()
        seeded = next(
            row["player"]["id"]
            for section in entries
            for row in section["entries"]
            if row["entry"]["seed"] is not None and row["entry"]["seed"] <= 10
        )
        response = participant.put(
            f"/api/tournaments/{TOURNAMENT_ID}/questions/{question['id']}/prediction",
            json={
                "tournamentId": TOURNAMENT_ID,
                "questionId": question["id"],
                "payload": {"kind": "UNDERPERFORMER", "playerId": seeded},
                "asDraft": False,
            },
        )
        assert response.status_code == 403
        assert "closed" in response.json()["detail"]

    def test_a_mismatched_payload_shape_is_rejected(self, participant: TestClient) -> None:
        question = self._open_question(participant)
        response = participant.put(
            f"/api/tournaments/{TOURNAMENT_ID}/questions/{question['id']}/prediction",
            json={
                "tournamentId": TOURNAMENT_ID,
                "questionId": question["id"],
                "payload": {"kind": "GENERIC_INTEGER", "value": 3},
                "asDraft": False,
            },
        )
        assert response.status_code == 422


class TestResults:
    def test_a_participant_cannot_enter_results(self, participant: TestClient) -> None:
        response = participant.post(f"/api/admin/tournaments/{TOURNAMENT_ID}/recalculate")
        assert response.status_code == 403

    def test_an_organiser_can_recalculate_and_it_is_idempotent(
        self, organiser: TestClient
    ) -> None:
        first = organiser.post(f"/api/admin/tournaments/{TOURNAMENT_ID}/recalculate")
        assert first.status_code == 200, first.text
        second = organiser.post(f"/api/admin/tournaments/{TOURNAMENT_ID}/recalculate")
        assert second.json()["scoreEntriesWritten"] == first.json()["scoreEntriesWritten"]

    def test_the_outcome_grid_is_replaced_not_appended(self, organiser: TestClient) -> None:
        draws = organiser.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
        draw_id = draws[0]["id"]
        sections = organiser.get(
            f"/api/tournaments/{TOURNAMENT_ID}/draws/{draw_id}/entries"
        ).json()
        players = [row["player"]["id"] for row in sections[0]["entries"]][:3]

        response = organiser.put(
            f"/api/admin/draws/{draw_id}/outcomes",
            json={
                "drawId": draw_id,
                "entries": [
                    {"playerId": pid, "roundReached": "R64", "note": None} for pid in players
                ],
            },
        )
        assert response.status_code == 200, response.text
        recorded = [
            row
            for section in response.json()
            for row in section["entries"]
            if row["roundReached"] is not None
        ]
        assert len(recorded) == 3

    def test_a_player_outside_the_draw_is_rejected(self, organiser: TestClient) -> None:
        draws = organiser.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
        response = organiser.put(
            f"/api/admin/draws/{draws[0]['id']}/outcomes",
            json={
                "drawId": draws[0]["id"],
                "entries": [{"playerId": "ghost", "roundReached": "QF", "note": None}],
            },
        )
        assert response.status_code == 422


class TestRankingAndScores:
    def test_the_ranking_is_ordered_and_ties_share_a_position(
        self, organiser: TestClient
    ) -> None:
        organiser.post(f"/api/admin/tournaments/{TOURNAMENT_ID}/recalculate")
        rows = organiser.get(f"/api/tournaments/{TOURNAMENT_ID}/ranking").json()
        totals = [r["totalPoints"] for r in rows]
        assert totals == sorted(totals, reverse=True)
        for row in rows:
            above = sum(1 for other in rows if other["totalPoints"] > row["totalPoints"])
            assert row["position"] == above + 1

    def test_the_breakdown_agrees_with_the_ranking(self, participant: TestClient) -> None:
        breakdown = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/scores").json()
        ranking = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/ranking").json()
        mine = next(r for r in ranking if r["isCurrentUser"])
        assert breakdown["total"] == mine["totalPoints"]
        assert breakdown["position"] == mine["position"]

    def test_an_unsettled_question_has_no_points_rather_than_a_zero(
        self, participant: TestClient
    ) -> None:
        breakdown = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/scores").json()
        open_block = next(g for g in breakdown["groups"] if g["betGroup"]["status"] == "OPEN")
        assert all(row["points"] is None for row in open_block["rows"])
        assert open_block["comparisonAvailable"] is False


class TestRepositoryScoping:
    """A repository set is opened per request, not shared across them.

    A SQLAlchemy Session is not thread-safe and uvicorn runs sync endpoints in
    a threadpool, so one shared session corrupts results under concurrency. It
    surfaced in a browser as an IndexError inside SQLAlchemy's row handling,
    which names nothing useful. TestClient issues requests sequentially, so no
    amount of ordinary API testing would have found it.
    """

    def test_sqlite_opens_a_fresh_repository_set_each_time(self) -> None:
        scope = build_repository_scope("sqlite")
        with scope() as first, scope() as second:
            assert first is not second

    def test_memory_shares_one_set_because_the_store_is_the_truth(self) -> None:
        scope = build_repository_scope("memory")
        with scope() as first, scope() as second:
            assert first is second

    def test_concurrent_reads_all_succeed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The shape of the bug: many readers at once, against a real app.

        A file database rather than `sqlite://`, because the in-memory URL uses
        a StaticPool — one connection for everybody — which would reintroduce
        the same contention one layer down and prove nothing.
        """
        monkeypatch.setenv("REPOSITORY_BACKEND", "sqlite")
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'concurrency.db'}")

        client = TestClient(create_app())
        client.post(
            "/api/auth/login", json={"email": "you@example.com", "password": DEMO_PASSWORD}
        )

        paths = [
            f"/api/tournaments/{TOURNAMENT_ID}/draws",
            f"/api/tournaments/{TOURNAMENT_ID}/bet-groups",
            f"/api/tournaments/{TOURNAMENT_ID}/ranking",
            f"/api/tournaments/{TOURNAMENT_ID}/scores",
            "/api/me",
        ] * 6

        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = [r.status_code for r in pool.map(client.get, paths)]
        assert codes == [200] * len(paths)
