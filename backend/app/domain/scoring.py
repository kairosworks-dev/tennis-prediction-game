"""The scoring engine.

A pure function of (predictions, outcome grid, question outcomes, scoring
profile) to score entries (AGENTS.md hard rule 5). No I/O, no clock reads, no
randomness, no database access — everything it needs arrives as an argument,
which is what makes it testable with plain data structures and what lets a
score always be rebuilt from source data.

Spec section 5 is the reference for every rule here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import Question, ScoringProfile
from app.domain.enums import RoundReached, TypedQuestionKind, round_rank
from app.domain.predictions import (
    BreakoutPick,
    ChampionPick,
    FinalistPicks,
    GenericChoice,
    GenericInteger,
    GenericMatchResult,
    GenericPlayer,
    QuarterFinalPicks,
    SemiFinalPicks,
    UnderperformerPick,
)

RANK_R16 = round_rank(RoundReached.R16)
RANK_QF = round_rank(RoundReached.QF)
RANK_SF = round_rank(RoundReached.SF)
RANK_F = round_rank(RoundReached.F)
RANK_CHAMPION = round_rank(RoundReached.CHAMPION)

#: Points for a generic question the organiser did not price individually.
DEFAULT_GENERIC_POINTS = 2


@dataclass(frozen=True, slots=True)
class Award:
    """Points and the audit line that explains them (decision D9)."""

    points: int
    reason: str


@dataclass(frozen=True, slots=True)
class ScoringContext:
    """Everything the engine is allowed to know.

    `outcomes` maps a player id to the round they reached — the outcome grid,
    flattened. `names` is for the reason strings only and never affects points.
    """

    outcomes: dict[str, RoundReached]
    profile: ScoringProfile
    names: dict[str, str]

    def reached(self, player_id: str, floor: int) -> bool:
        return round_rank(self.outcomes.get(player_id)) >= floor

    def deepest_rank(self) -> int:
        """How far the tournament itself has got.

        A question cannot settle before the round it asks about has been
        played. Scoring a champion pick as wrong while the quarter-finals are
        still going is not a zero, it is a false statement.
        """
        return max((round_rank(r) for r in self.outcomes.values()), default=-1)

    def name(self, player_id: str) -> str:
        return self.names.get(player_id, player_id)


def score_prediction(
    payload: object,
    correct_answer: object | None,
    context: ScoringContext,
) -> Award | None:
    """Points for one answered question, or None while it has not settled."""
    match payload:
        case QuarterFinalPicks(picks=picks):
            if context.deepest_rank() < RANK_QF:
                return None
            hits = [p for p in picks if context.reached(p.player_id, RANK_QF)]
            names = ", ".join(context.name(p.player_id) for p in hits)
            return Award(
                points=len(hits) * context.profile.quarter_finalist_points,
                reason=(
                    "None of the eight reached the quarter-final."
                    if not hits
                    else f"{len(hits)} of {len(picks)} correct — {names}."
                ),
            )

        case SemiFinalPicks(player_ids=ids):
            if context.deepest_rank() < RANK_SF:
                return None
            hits = [pid for pid in ids if context.reached(pid, RANK_SF)]
            return Award(
                points=len(hits) * context.profile.semi_finalist_points,
                reason=f"{len(hits)} of {len(ids)} reached the semi-final.",
            )

        case FinalistPicks(player_ids=ids):
            if context.deepest_rank() < RANK_F:
                return None
            hits = [pid for pid in ids if context.reached(pid, RANK_F)]
            return Award(
                points=len(hits) * context.profile.finalist_points,
                reason=f"{len(hits)} of {len(ids)} reached the final.",
            )

        case ChampionPick(player_id=player_id):
            if context.deepest_rank() < RANK_CHAMPION:
                return None
            correct = context.reached(player_id, RANK_CHAMPION)
            return Award(
                points=context.profile.champion_points if correct else 0,
                reason=(
                    f"{context.name(player_id)} won the title."
                    if correct
                    else f"{context.name(player_id)} did not win the title."
                ),
            )

        case UnderperformerPick(player_id=player_id):
            reached = context.outcomes.get(player_id)
            exit_index = {
                RoundReached.R128: 0,
                RoundReached.R64: 1,
                RoundReached.R32: 2,
            }.get(reached) if reached is not None else None
            if exit_index is None:
                # Still in, or out later than round three — either way, nothing.
                if reached is None:
                    return None
                return Award(
                    points=0,
                    reason=f"{context.name(player_id)} survived the first three rounds.",
                )
            return Award(
                points=context.profile.underperformer_points[exit_index],
                reason=f"{context.name(player_id)} exited in round {exit_index + 1}.",
            )

        case BreakoutPick(player_id=player_id):
            if context.deepest_rank() < RANK_R16:
                return None
            rank = round_rank(context.outcomes.get(player_id))
            ladder = (
                (RANK_CHAMPION, 4),
                (RANK_F, 3),
                (RANK_SF, 2),
                (RANK_QF, 1),
                (RANK_R16, 0),
            )
            step = next((index for floor, index in ladder if rank >= floor), None)
            if step is None:
                return Award(
                    points=0,
                    reason=f"{context.name(player_id)} did not reach the fourth round.",
                )
            reached = context.outcomes.get(player_id)
            return Award(
                points=context.profile.breakout_points[step],
                reason=f"{context.name(player_id)} reached {reached}.",
            )

        case GenericMatchResult(winner_id=winner_id, set_score=set_score):
            if not isinstance(correct_answer, GenericMatchResult):
                return None
            winner_correct = winner_id == correct_answer.winner_id
            # The set-score point only counts when the winner is right (spec 5.2).
            score_correct = winner_correct and set_score == correct_answer.set_score
            points = (
                context.profile.featured_match_winner_points if winner_correct else 0
            ) + (context.profile.featured_match_set_score_points if score_correct else 0)
            if not winner_correct:
                reason = "Wrong winner. No points."
            elif score_correct:
                reason = "Winner correct, set score correct."
            else:
                reason = "Winner correct, set score wrong."
            return Award(points=points, reason=reason)

        case GenericInteger(value=value):
            if not isinstance(correct_answer, GenericInteger):
                return None
            correct = value == correct_answer.value
            return Award(
                points=DEFAULT_GENERIC_POINTS if correct else 0,
                reason=(
                    f"You said {value}. Correct."
                    if correct
                    else f"You said {value}, it was {correct_answer.value}."
                ),
            )

        case GenericChoice(option_id=option_id):
            if not isinstance(correct_answer, GenericChoice):
                return None
            correct = option_id == correct_answer.option_id
            return Award(
                points=DEFAULT_GENERIC_POINTS if correct else 0,
                reason="Correct." if correct else "Not this time.",
            )

        case GenericPlayer(player_id=player_id):
            if not isinstance(correct_answer, GenericPlayer):
                return None
            correct = player_id == correct_answer.player_id
            return Award(
                points=DEFAULT_GENERIC_POINTS if correct else 0,
                reason=(
                    f"{context.name(player_id)}. Correct."
                    if correct
                    else f"It was {context.name(correct_answer.player_id)}."
                ),
            )

    return None


@dataclass(frozen=True, slots=True)
class ScoreInput:
    """One participant's answer to one question, ready to be scored."""

    participation_id: str
    question: Question
    payload: object
    correct_answer: object | None


@dataclass(frozen=True, slots=True)
class ScoreResult:
    participation_id: str
    question_id: str
    points: int
    reason: str


def score_all(
    inputs: list[ScoreInput],
    context: ScoringContext,
) -> list[ScoreResult]:
    """Score every answered question. Unsettled questions produce no entry.

    This is the whole engine: given the same arguments it returns the same
    results, every time, with no reference to anything outside them.
    """
    results: list[ScoreResult] = []
    for item in inputs:
        award = score_prediction(item.payload, item.correct_answer, context)
        if award is None:
            continue
        results.append(
            ScoreResult(
                participation_id=item.participation_id,
                question_id=item.question.id,
                points=award.points,
                reason=award.reason,
            )
        )
    return results


__all__ = [
    "Award",
    "ScoreInput",
    "ScoreResult",
    "ScoringContext",
    "TypedQuestionKind",
    "score_all",
    "score_prediction",
]
