"""The leaderboard (spec 4.4.4).

Reads persisted score entries; it never recomputes them (spec 5.4), so the
query stays cheap as participants and questions grow.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import BetGroupStatus
from app.repositories.interfaces import Repositories


@dataclass(frozen=True, slots=True)
class BetGroupPoints:
    bet_group_id: str
    title: str
    points: int


@dataclass(frozen=True, slots=True)
class RankingEntry:
    position: int
    participation_id: str
    display_name: str
    is_current_user: bool
    total_points: int
    last_group_points: int
    movement: int | None
    per_group_points: list[BetGroupPoints]


class RankingService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    def ranking_for(self, tournament_id: str, current_user_id: str | None) -> list[RankingEntry]:
        participations = self._repos.participations.list_for_tournament(tournament_id)
        settled = [
            g
            for g in self._repos.bet_groups.list_for_tournament(tournament_id)
            if g.status is BetGroupStatus.SETTLED
        ]
        question_ids_by_group = {
            group.id: {q.id for q in self._repos.questions.list_for_group(group.id)}
            for group in settled
        }
        last_group = settled[-1] if settled else None

        rows = []
        for participation in participations:
            own = self._repos.scores.list_for_participation(participation.id)
            per_group = [
                BetGroupPoints(
                    bet_group_id=group.id,
                    title=group.title,
                    points=sum(
                        s.points for s in own if s.question_id in question_ids_by_group[group.id]
                    ),
                )
                for group in settled
            ]
            user = self._repos.users.get(participation.user_id)
            rows.append(
                {
                    "participation_id": participation.id,
                    "display_name": user.display_name if user else "Former participant",
                    "is_current_user": participation.user_id == current_user_id,
                    "total_points": sum(g.points for g in per_group),
                    "last_group_points": next(
                        (
                            g.points
                            for g in per_group
                            if last_group is not None and g.bet_group_id == last_group.id
                        ),
                        0,
                    ),
                    "per_group_points": per_group,
                }
            )

        rows.sort(key=lambda r: (-r["total_points"], r["display_name"]))

        previous_order = [
            r["participation_id"]
            for r in sorted(
                rows,
                key=lambda r: (-(r["total_points"] - r["last_group_points"]), r["display_name"]),
            )
        ]

        entries: list[RankingEntry] = []
        position = 0
        previous_points: int | None = None
        for index, row in enumerate(rows):
            # Ties share a position and the next position skips (decision D13).
            if previous_points is None or row["total_points"] != previous_points:
                position = index + 1
                previous_points = row["total_points"]
            was_at = previous_order.index(row["participation_id"])
            entries.append(
                RankingEntry(
                    position=position,
                    participation_id=row["participation_id"],
                    display_name=row["display_name"],
                    is_current_user=row["is_current_user"],
                    total_points=row["total_points"],
                    last_group_points=row["last_group_points"],
                    movement=None if len(settled) < 2 else was_at - index,
                    per_group_points=row["per_group_points"],
                )
            )
        return entries
