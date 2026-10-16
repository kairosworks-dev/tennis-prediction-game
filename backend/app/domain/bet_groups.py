"""When a bet group is open (spec 4.4.2, 5.3; decision D7).

The deadline is the lock. Nothing moves a group to LOCKED in storage, so the
status a reader or writer acts on is derived here from the group and "now".
`now` is an argument: the domain never reads a clock (AGENTS.md hard rule 5).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.entities import BetGroup
from app.domain.enums import BetGroupStatus


def effective_status(group: BetGroup, now: datetime) -> BetGroupStatus:
    """The stored status, except that an OPEN group is LOCKED from its deadline on.

    The boundary is inclusive: at `now == deadline` the group is locked. DRAFT,
    LOCKED and SETTLED keep their meaning whatever the deadline says.
    """
    if group.status is BetGroupStatus.OPEN and now >= group.deadline:
        return BetGroupStatus.LOCKED
    return group.status


def with_effective_status(group: BetGroup, now: datetime) -> BetGroup:
    """A copy of the group carrying its effective status. The stored one is untouched."""
    status = effective_status(group, now)
    return group if status is group.status else replace(group, status=status)
