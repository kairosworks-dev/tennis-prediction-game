"""The validation rules from spec section 5.3.

The backend is the authority on every rule here (AGENTS.md hard rule 2). The
frontend mirrors them for user experience; when the two disagree, this side
wins. Like the rest of `domain/`, this imports no framework — it raises a plain
exception and the API layer turns it into an RFC 7807 problem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.entities import Draw, DrawEntry, Question
from app.domain.enums import AnswerType, QuestionFamily, TypedQuestionKind, legal_set_scores
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

SECTION_COUNT = 8
UNDERPERFORMER_MAX_SEED = 10


class ValidationError(Exception):
    """A prediction that breaks a rule in spec 5.3."""

    def __init__(self, detail: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or {}


@dataclass(frozen=True, slots=True)
class ValidationContext:
    question: Question
    draw: Draw | None
    entries: tuple[DrawEntry, ...]
    #: The participant's other typed answers for the same draw and bet group.
    siblings: dict[TypedQuestionKind, object] = field(default_factory=dict)

    def seed_of(self, player_id: str) -> int | None:
        for entry in self.entries:
            if entry.player_id == player_id:
                return entry.seed
        return None

    def section_of(self, player_id: str) -> str | None:
        for entry in self.entries:
            if entry.player_id == player_id:
                return entry.section_id
        return None

    def is_entrant(self, player_id: str) -> bool:
        return any(entry.player_id == player_id for entry in self.entries)


def _pool(payload: object | None) -> tuple[str, ...]:
    """The player ids an earlier answer makes available to a later one."""
    match payload:
        case QuarterFinalPicks() as p:
            return p.player_ids
        case SemiFinalPicks(player_ids=ids) | FinalistPicks(player_ids=ids):
            return ids
        case ChampionPick(player_id=pid):
            return (pid,)
    return ()


def _require_subset(
    chosen: tuple[str, ...],
    pool: tuple[str, ...],
    size: int,
    label: str,
    pool_label: str,
) -> None:
    if len(chosen) != size:
        raise ValidationError(
            f"Choose exactly {size} {label}.",
            {"payload": [f"Expected {size}, got {len(chosen)}."]},
        )
    if len(set(chosen)) != len(chosen):
        raise ValidationError(
            f"The same player appears twice in your {label}.",
            {"payload": ["Each pick must be a different player."]},
        )
    if not pool:
        raise ValidationError(
            f"Answer the {pool_label} question first.",
            {"payload": [f"Your {label} are drawn from your {pool_label}."]},
        )
    stray = [pid for pid in chosen if pid not in pool]
    if stray:
        raise ValidationError(
            f"Your {label} must come from your {pool_label}.",
            {"payload": [f"{len(stray)} pick(s) are not among your {pool_label}."]},
        )


def validate_prediction(payload: object, context: ValidationContext) -> None:
    """Raise `ValidationError` when the answer breaks a rule."""

    def require_entrant(player_id: str) -> None:
        if not context.is_entrant(player_id):
            raise ValidationError(
                "That player is not in this draw.",
                {"payload": ["Pick an entrant of the draw this question belongs to."]},
            )

    match payload:
        case QuarterFinalPicks(picks=picks):
            if len(picks) != SECTION_COUNT:
                raise ValidationError(
                    f"Choose one player from each of the {SECTION_COUNT} sections.",
                    {"payload": [f"{len(picks)} of {SECTION_COUNT} sections answered."]},
                )
            seen: set[int] = set()
            for pick in picks:
                if not 1 <= pick.section_index <= SECTION_COUNT:
                    raise ValidationError(f"Section {pick.section_index} does not exist.")
                if pick.section_index in seen:
                    raise ValidationError(
                        f"Section {pick.section_index} has two picks.",
                        {"payload": ["Exactly one player per section."]},
                    )
                seen.add(pick.section_index)
                require_entrant(pick.player_id)
            if len({p.player_id for p in picks}) != len(picks):
                raise ValidationError("The same player cannot fill two sections.")

        case SemiFinalPicks(player_ids=ids):
            _require_subset(
                ids,
                _pool(context.siblings.get(TypedQuestionKind.QF_PICKS)),
                4,
                "semi-finalists",
                "quarter-finalists",
            )

        case FinalistPicks(player_ids=ids):
            _require_subset(
                ids,
                _pool(context.siblings.get(TypedQuestionKind.SF_PICKS)),
                2,
                "finalists",
                "semi-finalists",
            )

        case ChampionPick(player_id=player_id):
            _require_subset(
                (player_id,),
                _pool(context.siblings.get(TypedQuestionKind.FINALIST_PICKS)),
                1,
                "champion",
                "finalists",
            )

        case UnderperformerPick(player_id=player_id):
            require_entrant(player_id)
            seed = context.seed_of(player_id)
            if seed is None or seed > UNDERPERFORMER_MAX_SEED:
                raise ValidationError(
                    f"The underperformer must be seeded {UNDERPERFORMER_MAX_SEED} or better.",
                    {
                        "payload": [
                            "That player is unseeded."
                            if seed is None
                            else f"That player is seeded {seed}."
                        ]
                    },
                )

        case BreakoutPick(player_id=player_id):
            require_entrant(player_id)
            seed = context.seed_of(player_id)
            if seed is not None:
                raise ValidationError(
                    "The breakout pick must be an unseeded entrant.",
                    {"payload": [f"That player is seeded {seed}."]},
                )

        case GenericMatchResult(winner_id=winner_id, set_score=set_score):
            if context.question.matchup is None:
                raise ValidationError("This question has no match attached to it.")
            if winner_id not in context.question.matchup:
                raise ValidationError("The winner must be one of the two players in the tie.")
            best_of = context.draw.best_of if context.draw is not None else 3
            legal = legal_set_scores(best_of)
            if set_score not in legal:
                spelled = "three" if best_of == 3 else "five"
                raise ValidationError(
                    f"{set_score} is not a legal result in a best-of-{spelled} match.",
                    {"payload": [f"Legal scores: {', '.join(legal)}."]},
                )

        case GenericInteger(value=value):
            if value < 0:
                raise ValidationError("Answer with a whole number of zero or more.")

        case GenericChoice(option_id=option_id):
            options = context.question.options or ()
            if not any(option.id == option_id for option in options):
                raise ValidationError("That is not one of the offered answers.")

        case GenericPlayer(player_id=player_id):
            require_entrant(player_id)


def expected_payload_kind(question: Question) -> str:
    """The payload kind a question expects, so a mismatched shape fails early."""
    if question.family is QuestionFamily.TYPED and question.kind is not None:
        return str(question.kind)
    return {
        AnswerType.PLAYER: "GENERIC_PLAYER",
        AnswerType.MATCH_RESULT: "GENERIC_MATCH_RESULT",
        AnswerType.INTEGER: "GENERIC_INTEGER",
        AnswerType.CHOICE: "GENERIC_CHOICE",
    }[question.answer_type]
