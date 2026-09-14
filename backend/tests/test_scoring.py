"""Scoring engine tests — every question kind, including zero-point and
partial-credit cases (AGENTS.md testing expectations, spec section 9 step 3).

The engine is a pure function, so every test here is plain data in, plain data
out: no database, no HTTP client, no FastAPI.
"""

from __future__ import annotations

import pytest

from app.domain.entities import ScoringProfile
from app.domain.enums import RoundReached
from app.domain.predictions import (
    BreakoutPick,
    ChampionPick,
    FinalistPicks,
    GenericChoice,
    GenericInteger,
    GenericMatchResult,
    GenericPlayer,
    QuarterFinalPicks,
    SectionPick,
    SemiFinalPicks,
    UnderperformerPick,
)
from app.domain.scoring import ScoringContext, score_prediction

PROFILE = ScoringProfile()


def context(outcomes: dict[str, RoundReached]) -> ScoringContext:
    return ScoringContext(
        outcomes=outcomes,
        profile=PROFILE,
        names={pid: pid.title() for pid in outcomes},
    )


def qf_picks(*player_ids: str) -> QuarterFinalPicks:
    return QuarterFinalPicks(
        picks=tuple(SectionPick(section_index=i + 1, player_id=p) for i, p in enumerate(player_ids))
    )


#: Eight players, all of whom reached the quarter-final.
ALL_EIGHT = {f"p{i}": RoundReached.QF for i in range(1, 9)}


class TestQuarterFinalPicks:
    def test_all_eight_correct(self) -> None:
        award = score_prediction(qf_picks(*ALL_EIGHT), None, context(ALL_EIGHT))
        assert award is not None
        assert award.points == 8 * PROFILE.quarter_finalist_points

    def test_partial_credit(self) -> None:
        outcomes = {**ALL_EIGHT, "p3": RoundReached.R32, "p7": RoundReached.R64}
        award = score_prediction(qf_picks(*ALL_EIGHT), None, context(outcomes))
        assert award is not None
        assert award.points == 6
        assert "6 of 8" in award.reason

    def test_zero_points_reads_as_a_sentence_not_a_list(self) -> None:
        # Somebody has to have reached the quarter-final for the question to
        # settle at all — it just was not any of these eight.
        outcomes = {pid: RoundReached.R128 for pid in ALL_EIGHT}
        outcomes["someone-else"] = RoundReached.QF
        award = score_prediction(qf_picks(*ALL_EIGHT), None, context(outcomes))
        assert award is not None
        assert award.points == 0
        assert award.reason == "None of the eight reached the quarter-final."

    def test_a_deeper_run_still_counts_as_reaching_the_quarter_final(self) -> None:
        outcomes = {**ALL_EIGHT, "p1": RoundReached.CHAMPION, "p2": RoundReached.SF}
        award = score_prediction(qf_picks(*ALL_EIGHT), None, context(outcomes))
        assert award is not None
        assert award.points == 8

    def test_does_not_settle_before_the_quarter_finals_are_played(self) -> None:
        outcomes = {pid: RoundReached.R16 for pid in ALL_EIGHT}
        assert score_prediction(qf_picks(*ALL_EIGHT), None, context(outcomes)) is None

    def test_a_withdrawal_never_advanced(self) -> None:
        outcomes = {**ALL_EIGHT, "p1": RoundReached.WITHDREW}
        award = score_prediction(qf_picks(*ALL_EIGHT), None, context(outcomes))
        assert award is not None
        assert award.points == 7


class TestSemiFinalPicks:
    def test_partial_credit_at_two_points_each(self) -> None:
        outcomes = {
            "a": RoundReached.SF, "b": RoundReached.F,
            "c": RoundReached.QF, "d": RoundReached.QF,
        }
        award = score_prediction(SemiFinalPicks(("a", "b", "c", "d")), None, context(outcomes))
        assert award is not None
        assert award.points == 2 * PROFILE.semi_finalist_points

    def test_zero_when_none_got_there(self) -> None:
        outcomes = {"a": RoundReached.SF, "b": RoundReached.QF}
        award = score_prediction(SemiFinalPicks(("b",)), None, context(outcomes))
        assert award is not None
        assert award.points == 0

    def test_does_not_settle_before_the_semi_finals(self) -> None:
        outcomes = {"a": RoundReached.QF}
        assert score_prediction(SemiFinalPicks(("a",)), None, context(outcomes)) is None


class TestFinalistPicks:
    def test_three_points_each(self) -> None:
        outcomes = {"a": RoundReached.F, "b": RoundReached.CHAMPION, "c": RoundReached.SF}
        award = score_prediction(FinalistPicks(("a", "b")), None, context(outcomes))
        assert award is not None
        assert award.points == 2 * PROFILE.finalist_points

    def test_partial_credit(self) -> None:
        outcomes = {"a": RoundReached.F, "c": RoundReached.SF}
        award = score_prediction(FinalistPicks(("a", "c")), None, context(outcomes))
        assert award is not None
        assert award.points == PROFILE.finalist_points


class TestChampion:
    def test_five_points_for_the_winner(self) -> None:
        outcomes = {"a": RoundReached.CHAMPION, "b": RoundReached.F}
        award = score_prediction(ChampionPick("a"), None, context(outcomes))
        assert award is not None
        assert award.points == PROFILE.champion_points

    def test_zero_for_the_runner_up(self) -> None:
        outcomes = {"a": RoundReached.CHAMPION, "b": RoundReached.F}
        award = score_prediction(ChampionPick("b"), None, context(outcomes))
        assert award is not None
        assert award.points == 0
        assert "did not win" in award.reason

    def test_does_not_settle_until_someone_has_won(self) -> None:
        outcomes = {"a": RoundReached.F, "b": RoundReached.F}
        assert score_prediction(ChampionPick("a"), None, context(outcomes)) is None


class TestUnderperformer:
    @pytest.mark.parametrize(
        ("exit_round", "expected"),
        [(RoundReached.R128, 3), (RoundReached.R64, 2), (RoundReached.R32, 1)],
    )
    def test_the_earlier_the_exit_the_better(self, exit_round: RoundReached, expected: int) -> None:
        award = score_prediction(UnderperformerPick("a"), None, context({"a": exit_round}))
        assert award is not None
        assert award.points == expected

    @pytest.mark.parametrize(
        "deep_round",
        [RoundReached.R16, RoundReached.QF, RoundReached.SF, RoundReached.F, RoundReached.CHAMPION],
    )
    def test_zero_when_they_survive_the_first_three_rounds(self, deep_round: RoundReached) -> None:
        award = score_prediction(UnderperformerPick("a"), None, context({"a": deep_round}))
        assert award is not None
        assert award.points == 0
        assert "survived" in award.reason

    def test_unsettled_while_they_are_still_in(self) -> None:
        assert score_prediction(UnderperformerPick("a"), None, context({})) is None


class TestBreakout:
    @pytest.mark.parametrize(
        ("reached", "expected"),
        [
            (RoundReached.R16, 2),
            (RoundReached.QF, 3),
            (RoundReached.SF, 4),
            (RoundReached.F, 5),
            (RoundReached.CHAMPION, 7),
        ],
    )
    def test_the_ladder_climbs(self, reached: RoundReached, expected: int) -> None:
        outcomes = {"a": reached, "other": RoundReached.R16}
        award = score_prediction(BreakoutPick("a"), None, context(outcomes))
        assert award is not None
        assert award.points == expected

    def test_zero_below_the_fourth_round(self) -> None:
        outcomes = {"a": RoundReached.R32, "other": RoundReached.R16}
        award = score_prediction(BreakoutPick("a"), None, context(outcomes))
        assert award is not None
        assert award.points == 0

    def test_does_not_settle_before_the_fourth_round(self) -> None:
        assert score_prediction(BreakoutPick("a"), None, context({"a": RoundReached.R32})) is None


class TestFeaturedMatch:
    """Spec 5.2 — the set-score point only counts with the right winner."""

    def test_winner_and_score_both_right(self) -> None:
        award = score_prediction(
            GenericMatchResult("a", "3-1"), GenericMatchResult("a", "3-1"), context({})
        )
        assert award is not None
        assert award.points == 2

    def test_winner_right_score_wrong(self) -> None:
        award = score_prediction(
            GenericMatchResult("a", "3-0"), GenericMatchResult("a", "3-1"), context({})
        )
        assert award is not None
        assert award.points == 1

    def test_wrong_winner_scores_nothing_even_with_the_right_score(self) -> None:
        award = score_prediction(
            GenericMatchResult("b", "3-1"), GenericMatchResult("a", "3-1"), context({})
        )
        assert award is not None
        assert award.points == 0
        assert award.reason == "Wrong winner. No points."

    def test_unsettled_until_the_organiser_enters_the_result(self) -> None:
        assert score_prediction(GenericMatchResult("a", "3-1"), None, context({})) is None


class TestGenericAnswers:
    def test_integer_correct_and_wrong(self) -> None:
        right = score_prediction(GenericInteger(3), GenericInteger(3), context({}))
        wrong = score_prediction(GenericInteger(2), GenericInteger(3), context({}))
        assert right is not None and right.points == 2
        assert wrong is not None and wrong.points == 0
        assert "it was 3" in wrong.reason

    def test_choice_correct_and_wrong(self) -> None:
        right = score_prediction(GenericChoice("x"), GenericChoice("x"), context({}))
        wrong = score_prediction(GenericChoice("y"), GenericChoice("x"), context({}))
        assert right is not None and right.points == 2
        assert wrong is not None and wrong.points == 0

    def test_player_correct_and_wrong(self) -> None:
        ctx = context({"a": RoundReached.QF, "b": RoundReached.QF})
        right = score_prediction(GenericPlayer("a"), GenericPlayer("a"), ctx)
        wrong = score_prediction(GenericPlayer("b"), GenericPlayer("a"), ctx)
        assert right is not None and right.points == 2
        assert wrong is not None and wrong.points == 0

    def test_a_mismatched_answer_shape_does_not_score(self) -> None:
        assert score_prediction(GenericInteger(3), GenericChoice("x"), context({})) is None


class TestProfileIsRespected:
    """Structure is fixed, values are not (decision D10)."""

    def test_custom_point_values_are_used(self) -> None:
        generous = ScoringProfile(quarter_finalist_points=10, champion_points=100)
        ctx = ScoringContext(outcomes=ALL_EIGHT, profile=generous, names={})
        award = score_prediction(qf_picks(*ALL_EIGHT), None, ctx)
        assert award is not None
        assert award.points == 80


class TestPurity:
    """AGENTS.md hard rule 5 — same arguments, same answer, no side effects."""

    def test_repeated_calls_agree(self) -> None:
        ctx = context(ALL_EIGHT)
        payload = qf_picks(*ALL_EIGHT)
        first = score_prediction(payload, None, ctx)
        second = score_prediction(payload, None, ctx)
        assert first == second

    def test_the_context_is_not_mutated(self) -> None:
        outcomes = dict(ALL_EIGHT)
        ctx = context(outcomes)
        score_prediction(qf_picks(*ALL_EIGHT), None, ctx)
        assert ctx.outcomes == outcomes
