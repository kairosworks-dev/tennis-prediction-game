"""A bet group locks at its deadline (issue #36), through the HTTP API.

The clock is a `FixedClock` the test moves to either side of the deadline, so
no test waits for time to pass. Every test here runs against each repository
implementation.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain.entities import BetGroup
from app.domain.enums import BetGroupKind, BetGroupStatus
from app.providers.clock import FixedClock, SystemClock
from app.repositories.interfaces import Repositories
from app.repositories.memory import MemoryRepositories
from app.seed import DEMO_PASSWORD, seed_demo_game
from tests.conftest import TOURNAMENT_ID

OPEN_GROUP_ID = "rg-bg-qf"
SECOND = timedelta(seconds=1)


@pytest.fixture
def deadline(repositories: Repositories, client: TestClient):
    """The open group's deadline. Depends on `client` so the app has seeded."""
    del client
    group = repositories.bet_groups.get(OPEN_GROUP_ID)
    assert group is not None and group.status is BetGroupStatus.OPEN
    return group.deadline


def _sign_in(client: TestClient, email: str) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert response.status_code == 200, response.text


def _match_result_questions(client: TestClient) -> list[dict]:
    questions = client.get(
        f"/api/tournaments/{TOURNAMENT_ID}/bet-groups/{OPEN_GROUP_ID}/questions"
    ).json()
    return [q for q in questions if q["answerType"] == "MATCH_RESULT"]


def _answer(client: TestClient, question: dict, *, winner: int = 0) -> dict:
    draws = client.get(f"/api/tournaments/{TOURNAMENT_ID}/draws").json()
    best_of = next(d["bestOf"] for d in draws if d["id"] == question["drawId"])
    return {
        "kind": "GENERIC_MATCH_RESULT",
        "winnerId": question["matchup"][winner],
        "setScore": "3-0" if best_of == 5 else "2-0",
    }


def _put(client: TestClient, question: dict, payload: dict, *, as_draft: bool = False):
    return client.put(
        f"/api/tournaments/{TOURNAMENT_ID}/questions/{question['id']}/prediction",
        json={
            "tournamentId": TOURNAMENT_ID,
            "questionId": question["id"],
            "payload": payload,
            "asDraft": as_draft,
        },
    )


def _own_predictions(client: TestClient) -> list[dict]:
    return client.get(f"/api/tournaments/{TOURNAMENT_ID}/predictions").json()


def _groups(client: TestClient) -> dict[str, dict]:
    rows = client.get(f"/api/tournaments/{TOURNAMENT_ID}/bet-groups").json()
    return {g["id"]: g for g in rows}


class TestSavingAPrediction:
    def test_one_second_before_the_deadline_it_is_saved(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        question = _match_result_questions(participant)[0]
        clock.set(deadline - SECOND)

        assert _put(participant, question, _answer(participant, question)).status_code == 200

    def test_at_the_deadline_it_is_refused_like_a_closed_group(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        question = _match_result_questions(participant)[0]
        clock.set(deadline)

        response = _put(participant, question, _answer(participant, question))

        assert response.status_code == 403
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["status"] == 403
        assert body["title"] == "Not allowed"
        assert body["type"].endswith("/forbidden")
        assert body["detail"] == "That group has closed. Predictions are final."

    def test_after_the_deadline_the_stored_prediction_is_unchanged(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        question = _match_result_questions(participant)[0]
        clock.set(deadline - SECOND)
        assert _put(participant, question, _answer(participant, question)).status_code == 200
        before = _own_predictions(participant)

        clock.set(deadline + timedelta(hours=1))
        # A replacement is not an exception, and neither is a draft.
        other = _answer(participant, question, winner=1)
        assert _put(participant, question, other).status_code == 403
        assert _put(participant, question, other, as_draft=True).status_code == 403

        assert _own_predictions(participant) == before

    def test_a_first_save_after_the_deadline_stores_nothing(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        question = _match_result_questions(participant)[0]
        clock.set(deadline + SECOND)

        assert _put(participant, question, _answer(participant, question)).status_code == 403
        assert not [p for p in _own_predictions(participant) if p["questionId"] == question["id"]]


class TestReadingBetGroups:
    def test_an_open_group_reads_open_before_and_locked_from_its_deadline(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        clock.set(deadline - SECOND)
        assert _groups(participant)[OPEN_GROUP_ID]["status"] == "OPEN"

        clock.set(deadline)
        assert _groups(participant)[OPEN_GROUP_ID]["status"] == "LOCKED"

        clock.set(deadline + timedelta(days=30))
        assert _groups(participant)[OPEN_GROUP_ID]["status"] == "LOCKED"

    def test_a_settled_group_stays_settled(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        clock.set(deadline + timedelta(days=30))
        assert _groups(participant)["rg-bg-tournament"]["status"] == "SETTLED"

    def test_a_draft_group_is_hidden_from_participants_and_draft_for_organisers(
        self, client: TestClient, repositories: Repositories, clock: FixedClock, deadline
    ) -> None:
        repositories.bet_groups.add(
            BetGroup(
                id="bg-draft",
                tournament_id=TOURNAMENT_ID,
                kind=BetGroupKind.ROUND,
                round=6,
                title="Semi-finals",
                intro_markdown="",
                deadline=deadline - timedelta(days=1),
                status=BetGroupStatus.DRAFT,
            )
        )
        repositories.commit()
        clock.set(deadline + timedelta(days=30))

        _sign_in(client, "you@example.com")
        assert "bg-draft" not in _groups(client)
        _sign_in(client, "organiser@example.com")
        assert _groups(client)["bg-draft"]["status"] == "DRAFT"

    def test_a_group_stored_locked_stays_locked_before_its_deadline(
        self, client: TestClient, repositories: Repositories, deadline
    ) -> None:
        repositories.bet_groups.add(
            BetGroup(
                id="bg-locked",
                tournament_id=TOURNAMENT_ID,
                kind=BetGroupKind.ROUND,
                round=6,
                title="Semi-finals",
                intro_markdown="",
                deadline=deadline + timedelta(days=30),
                status=BetGroupStatus.LOCKED,
            )
        )
        repositories.commit()

        _sign_in(client, "you@example.com")
        assert _groups(client)["bg-locked"]["status"] == "LOCKED"


class TestTheScoreBreakdown:
    def _block(self, client: TestClient) -> dict:
        breakdown = client.get(f"/api/tournaments/{TOURNAMENT_ID}/scores").json()
        return next(g for g in breakdown["groups"] if g["betGroup"]["id"] == OPEN_GROUP_ID)

    def test_the_status_and_the_comparison_follow_the_deadline(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        clock.set(deadline - SECOND)
        before = self._block(participant)
        assert before["betGroup"]["status"] == "OPEN"
        assert before["comparisonAvailable"] is False

        clock.set(deadline)
        after = self._block(participant)
        assert after["betGroup"]["status"] == "LOCKED"
        assert after["comparisonAvailable"] is True

    def test_a_settled_group_keeps_its_comparison(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        clock.set(deadline + timedelta(days=30))
        breakdown = participant.get(f"/api/tournaments/{TOURNAMENT_ID}/scores").json()
        settled = next(g for g in breakdown["groups"] if g["betGroup"]["status"] == "SETTLED")
        assert settled["comparisonAvailable"] is True


class TestTheGamesList:
    def _running_game(self, client: TestClient) -> dict:
        rows = client.get("/api/tournaments").json()
        return next(r for r in rows if r["tournament"]["id"] == TOURNAMENT_ID)

    def test_the_next_deadline_and_round_go_when_the_only_open_group_locks(
        self, participant: TestClient, clock: FixedClock, deadline
    ) -> None:
        clock.set(deadline - SECOND)
        before = self._running_game(participant)
        assert before["nextDeadline"] is not None
        assert before["currentRound"] == 5

        clock.set(deadline)
        after = self._running_game(participant)
        assert after["nextDeadline"] is None
        assert after["currentRound"] is None


class TestTheRanking:
    def test_standings_are_identical_either_side_of_the_deadline(
        self, client: TestClient, clock: FixedClock, deadline
    ) -> None:
        # Give the open group points, so there is something to move or to keep.
        _sign_in(client, "you@example.com")
        question = _match_result_questions(client)[0]
        answer = _answer(client, question)
        clock.set(deadline - SECOND)
        assert _put(client, question, answer).status_code == 200
        _sign_in(client, "organiser@example.com")
        client.put(
            f"/api/admin/questions/{question['id']}/outcome",
            json={"questionId": question["id"], "correctAnswer": answer, "note": None},
        )
        client.post(f"/api/admin/tournaments/{TOURNAMENT_ID}/recalculate")
        _sign_in(client, "you@example.com")

        def standings() -> list[dict]:
            return client.get(f"/api/tournaments/{TOURNAMENT_ID}/ranking").json()

        before = standings()
        assert max(r["totalPoints"] for r in before) > 0

        clock.set(deadline)
        assert standings() == before


class TestNothingIsWrittenToStorage:
    def test_the_stored_status_is_still_open_after_post_deadline_requests(
        self, participant: TestClient, repositories: Repositories, clock: FixedClock, deadline
    ) -> None:
        question = _match_result_questions(participant)[0]
        clock.set(deadline + timedelta(days=1))

        assert _groups(participant)[OPEN_GROUP_ID]["status"] == "LOCKED"
        participant.get(f"/api/tournaments/{TOURNAMENT_ID}/scores")
        participant.get("/api/tournaments")
        assert _put(participant, question, _answer(participant, question)).status_code == 403

        stored = repositories.bet_groups.get(OPEN_GROUP_ID)
        assert stored is not None
        assert stored.status is BetGroupStatus.OPEN


class TestDraftsDoNotScore:
    def test_recalculation_skips_a_prediction_that_was_never_submitted(
        self, client: TestClient, repositories: Repositories
    ) -> None:
        _sign_in(client, "you@example.com")
        submitted, draft = _match_result_questions(client)[:2]
        answers = {q["id"]: _answer(client, q) for q in (submitted, draft)}
        assert _put(client, submitted, answers[submitted["id"]]).status_code == 200
        assert _put(client, draft, answers[draft["id"]], as_draft=True).status_code == 200

        # Both questions are answered correctly: only the submitted one may score.
        _sign_in(client, "organiser@example.com")
        for question in (submitted, draft):
            client.put(
                f"/api/admin/questions/{question['id']}/outcome",
                json={
                    "questionId": question["id"],
                    "correctAnswer": answers[question["id"]],
                    "note": None,
                },
            )
        assert client.post(f"/api/admin/tournaments/{TOURNAMENT_ID}/recalculate").status_code == 200

        user = repositories.users.get_by_email("you@example.com")
        assert user is not None
        participation = repositories.participations.find(TOURNAMENT_ID, user.id)
        assert participation is not None
        entries = repositories.scores.list_for_participation(participation.id)
        scored = {s.question_id: s for s in entries}

        assert submitted["id"] in scored
        assert scored[submitted["id"]].points > 0
        assert draft["id"] not in scored

        _sign_in(client, "you@example.com")
        ranking = client.get(f"/api/tournaments/{TOURNAMENT_ID}/ranking").json()
        own = next(r for r in ranking if r["isCurrentUser"])
        assert own["totalPoints"] == sum(s.points for s in scored.values())


class TestTheSeed:
    def test_the_open_group_stays_open_for_more_than_59_days(self) -> None:
        # The demo group must not lock within a working session, let alone within hours.
        repos = MemoryRepositories()
        seed_demo_game(repos)
        group = repos.bet_groups.get(OPEN_GROUP_ID)
        assert group is not None and group.status is BetGroupStatus.OPEN
        assert group.deadline - SystemClock().now() > timedelta(days=59)
