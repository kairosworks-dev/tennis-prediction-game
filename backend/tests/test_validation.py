"""Validation rules from spec 5.3, tested one at a time.

These build their own draw rather than reading a fixture, so changing seed data
never rewrites a rule test.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from app.domain.entities import Draw, DrawEntry, Question
from app.domain.enums import AnswerType, QuestionFamily, Tour, TypedQuestionKind
from app.domain.predictions import (
    BreakoutPick,
    ChampionPick,
    FinalistPicks,
    GenericMatchResult,
    QuarterFinalPicks,
    SectionPick,
    SemiFinalPicks,
    UnderperformerPick,
)
from app.domain.validation import ValidationContext, ValidationError, validate_prediction

DRAW = Draw(
    id="draw-1", tournament_id="t-1", tour=Tour.ATP, draw_size=128, best_of=5,
    official_draw_url=None,
)


def build_entries() -> tuple[DrawEntry, ...]:
    """Eight sections of four: seeds 1-8, seeds 9-16, and two unseeded each."""
    entries: list[DrawEntry] = []
    for section in range(1, 9):
        section_id = f"s-{section}"
        entries += [
            DrawEntry(f"e-a{section}", DRAW.id, section_id, f"seedA-{section}", section),
            DrawEntry(f"e-b{section}", DRAW.id, section_id, f"seedB-{section}", section + 8),
            DrawEntry(f"e-c{section}", DRAW.id, section_id, f"free-{section}", None),
            DrawEntry(f"e-d{section}", DRAW.id, section_id, f"free2-{section}", None),
        ]
    return tuple(entries)


ENTRIES = build_entries()
ALL_SECTIONS = tuple(f"seedA-{i}" for i in range(1, 9))


def question(kind: TypedQuestionKind | None, **overrides: object) -> Question:
    base = {
        "id": "q-1", "bet_group_id": "bg-1", "draw_id": DRAW.id,
        "family": QuestionFamily.GENERIC if kind is None else QuestionFamily.TYPED,
        "kind": kind, "prompt": "test", "answer_type": AnswerType.PLAYER,
        "options": None, "matchup": None, "points_hint": "",
        "deadline_override": None, "position": 0,
    }
    return Question(**{**base, **overrides})  # type: ignore[arg-type]


def context(q: Question, **siblings: object) -> ValidationContext:
    return ValidationContext(
        question=q,
        draw=DRAW,
        entries=ENTRIES,
        siblings={TypedQuestionKind[k]: v for k, v in siblings.items()},
    )


def qf(*player_ids: str) -> QuarterFinalPicks:
    return QuarterFinalPicks(
        picks=tuple(SectionPick(i + 1, p) for i, p in enumerate(player_ids))
    )


def rejection(payload: object, ctx: ValidationContext) -> str:
    with pytest.raises(ValidationError) as caught:
        validate_prediction(payload, ctx)
    return caught.value.detail


class TestQuarterFinalPicks:
    def test_accepts_one_player_per_section(self) -> None:
        validate_prediction(qf(*ALL_SECTIONS), context(question(TypedQuestionKind.QF_PICKS)))

    def test_rejects_fewer_than_eight(self) -> None:
        detail = rejection(qf(*ALL_SECTIONS[:7]), context(question(TypedQuestionKind.QF_PICKS)))
        assert "one player from each" in detail

    def test_rejects_two_picks_for_one_section(self) -> None:
        picks = [SectionPick(i + 1, p) for i, p in enumerate(ALL_SECTIONS[:7])]
        picks.append(SectionPick(1, "seedB-1"))
        payload = QuarterFinalPicks(picks=tuple(picks))
        assert "two picks" in rejection(payload, context(question(TypedQuestionKind.QF_PICKS)))

    def test_rejects_someone_outside_the_draw(self) -> None:
        payload = qf("ghost", *ALL_SECTIONS[1:])
        ctx = context(question(TypedQuestionKind.QF_PICKS))
        assert "not in this draw" in rejection(payload, ctx)


class TestCascade:
    def test_semi_finalists_must_come_from_the_quarter_finalists(self) -> None:
        ctx = context(question(TypedQuestionKind.SF_PICKS), QF_PICKS=qf(*ALL_SECTIONS))
        validate_prediction(SemiFinalPicks(ALL_SECTIONS[:4]), ctx)
        detail = rejection(SemiFinalPicks((*ALL_SECTIONS[:3], "seedB-5")), ctx)
        assert "must come from your quarter-finalists" in detail

    def test_semi_finalists_need_exactly_four(self) -> None:
        ctx = context(question(TypedQuestionKind.SF_PICKS), QF_PICKS=qf(*ALL_SECTIONS))
        assert "exactly 4" in rejection(SemiFinalPicks(ALL_SECTIONS[:3]), ctx)

    def test_semi_finalists_ask_for_the_quarter_finals_first(self) -> None:
        ctx = context(question(TypedQuestionKind.SF_PICKS))
        detail = rejection(SemiFinalPicks(ALL_SECTIONS[:4]), ctx)
        assert "quarter-finalists question first" in detail

    def test_finalists_must_come_from_the_semi_finalists(self) -> None:
        ctx = context(
            question(TypedQuestionKind.FINALIST_PICKS),
            SF_PICKS=SemiFinalPicks(ALL_SECTIONS[:4]),
        )
        validate_prediction(FinalistPicks(ALL_SECTIONS[:2]), ctx)
        detail = rejection(FinalistPicks((ALL_SECTIONS[0], "seedA-8")), ctx)
        assert "must come from your semi-finalists" in detail

    def test_the_champion_must_be_a_finalist(self) -> None:
        ctx = context(
            question(TypedQuestionKind.CHAMPION),
            FINALIST_PICKS=FinalistPicks(ALL_SECTIONS[:2]),
        )
        validate_prediction(ChampionPick(ALL_SECTIONS[1]), ctx)
        assert "must come from your finalists" in rejection(ChampionPick("seedA-7"), ctx)


class TestUnderperformer:
    def test_accepts_a_seed_of_ten_or_better(self) -> None:
        ctx = context(question(TypedQuestionKind.UNDERPERFORMER))
        validate_prediction(UnderperformerPick("seedB-2"), ctx)  # seed 10

    def test_rejects_a_worse_seed(self) -> None:
        ctx = context(question(TypedQuestionKind.UNDERPERFORMER))
        assert "seeded 10 or better" in rejection(UnderperformerPick("seedB-3"), ctx)  # seed 11

    def test_rejects_an_unseeded_entrant(self) -> None:
        ctx = context(question(TypedQuestionKind.UNDERPERFORMER))
        assert "seeded 10 or better" in rejection(UnderperformerPick("free-1"), ctx)


class TestBreakout:
    def test_accepts_an_unseeded_entrant(self) -> None:
        validate_prediction(BreakoutPick("free-4"), context(question(TypedQuestionKind.BREAKOUT)))

    def test_rejects_a_seeded_entrant(self) -> None:
        ctx = context(question(TypedQuestionKind.BREAKOUT))
        assert "unseeded entrant" in rejection(BreakoutPick("seedA-1"), ctx)


class TestSetScores:
    MATCH: ClassVar[dict[str, object]] = {
        "answer_type": AnswerType.MATCH_RESULT,
        "matchup": ("seedA-1", "seedA-2"),
    }

    @pytest.mark.parametrize("score", ["3-0", "3-1", "3-2"])
    def test_best_of_five_accepts(self, score: str) -> None:
        validate_prediction(
            GenericMatchResult("seedA-1", score), context(question(None, **self.MATCH))
        )

    @pytest.mark.parametrize("score", ["2-0", "2-1"])
    def test_best_of_five_rejects(self, score: str) -> None:
        ctx = context(question(None, **self.MATCH))
        assert "not a legal result" in rejection(GenericMatchResult("seedA-1", score), ctx)

    @pytest.mark.parametrize("score", ["2-0", "2-1"])
    def test_best_of_three_accepts(self, score: str) -> None:
        ctx = ValidationContext(
            question=question(None, **self.MATCH),
            draw=Draw("d", "t", Tour.WTA, 128, 3, None),
            entries=ENTRIES,
            siblings={},
        )
        validate_prediction(GenericMatchResult("seedA-1", score), ctx)

    @pytest.mark.parametrize("score", ["3-0", "3-1", "3-2"])
    def test_best_of_three_rejects(self, score: str) -> None:
        ctx = ValidationContext(
            question=question(None, **self.MATCH),
            draw=Draw("d", "t", Tour.WTA, 128, 3, None),
            entries=ENTRIES,
            siblings={},
        )
        assert "not a legal result" in rejection(GenericMatchResult("seedA-1", score), ctx)

    def test_the_winner_must_be_in_the_tie(self) -> None:
        ctx = context(question(None, **self.MATCH))
        assert "one of the two players" in rejection(GenericMatchResult("seedA-5", "3-0"), ctx)
