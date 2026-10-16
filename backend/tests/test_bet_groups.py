"""The effective status of a bet group (issue #36), on plain datetimes.

No clock, no repository, no app: the rule is a pure function of the group and
"now" (AGENTS.md hard rule 5).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.bet_groups import effective_status, with_effective_status
from app.domain.entities import BetGroup
from app.domain.enums import BetGroupKind, BetGroupStatus

DEADLINE = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)


def group(status: BetGroupStatus, deadline: datetime = DEADLINE) -> BetGroup:
    return BetGroup(
        id="bg",
        tournament_id="t",
        kind=BetGroupKind.ROUND,
        round=5,
        title="Quarter-finals",
        intro_markdown="",
        deadline=deadline,
        status=status,
    )


class TestAnOpenGroup:
    def test_is_open_one_second_before_the_deadline(self) -> None:
        assert effective_status(group(BetGroupStatus.OPEN), DEADLINE - SECOND) is (
            BetGroupStatus.OPEN
        )

    def test_is_locked_exactly_at_the_deadline(self) -> None:
        assert effective_status(group(BetGroupStatus.OPEN), DEADLINE) is BetGroupStatus.LOCKED

    def test_is_locked_after_the_deadline(self) -> None:
        assert effective_status(group(BetGroupStatus.OPEN), DEADLINE + SECOND) is (
            BetGroupStatus.LOCKED
        )
        assert effective_status(group(BetGroupStatus.OPEN), DEADLINE + timedelta(days=90)) is (
            BetGroupStatus.LOCKED
        )


class TestAnyOtherStoredStatus:
    @pytest.mark.parametrize(
        "stored", [BetGroupStatus.DRAFT, BetGroupStatus.LOCKED, BetGroupStatus.SETTLED]
    )
    @pytest.mark.parametrize(
        "offset", [-timedelta(days=3), -SECOND, timedelta(0), SECOND, timedelta(days=3)]
    )
    def test_is_unchanged_whatever_the_deadline_says(
        self, stored: BetGroupStatus, offset: timedelta
    ) -> None:
        assert effective_status(group(stored), DEADLINE + offset) is stored


class TestWithEffectiveStatus:
    def test_returns_a_copy_and_leaves_the_stored_group_alone(self) -> None:
        stored = group(BetGroupStatus.OPEN)
        shown = with_effective_status(stored, DEADLINE)

        assert shown.status is BetGroupStatus.LOCKED
        assert stored.status is BetGroupStatus.OPEN
        assert (shown.id, shown.deadline, shown.title) == (stored.id, stored.deadline, stored.title)

    def test_returns_the_same_group_when_nothing_changes(self) -> None:
        stored = group(BetGroupStatus.OPEN)
        assert with_effective_status(stored, DEADLINE - SECOND) is stored
