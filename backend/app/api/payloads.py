"""Conversion between wire payloads and domain payloads.

The boundary lives here so `domain/` never imports Pydantic (AGENTS.md hard
rule 4) and the API never reaches into a dataclass by hand.
"""

from __future__ import annotations

from app.api import schemas
from app.domain import predictions as domain


def to_domain_payload(payload: object) -> object:
    match payload:
        case schemas.QuarterFinalPicksSchema(picks=picks):
            return domain.QuarterFinalPicks(
                picks=tuple(
                    domain.SectionPick(section_index=p.section_index, player_id=p.player_id)
                    for p in picks
                )
            )
        case schemas.SemiFinalPicksSchema(player_ids=ids):
            return domain.SemiFinalPicks(player_ids=tuple(ids))
        case schemas.FinalistPicksSchema(player_ids=ids):
            return domain.FinalistPicks(player_ids=tuple(ids))
        case schemas.ChampionSchema(player_id=pid):
            return domain.ChampionPick(player_id=pid)
        case schemas.UnderperformerSchema(player_id=pid):
            return domain.UnderperformerPick(player_id=pid)
        case schemas.BreakoutSchema(player_id=pid):
            return domain.BreakoutPick(player_id=pid)
        case schemas.GenericPlayerSchema(player_id=pid):
            return domain.GenericPlayer(player_id=pid)
        case schemas.GenericMatchResultSchema(winner_id=wid, set_score=score):
            return domain.GenericMatchResult(winner_id=wid, set_score=score)
        case schemas.GenericIntegerSchema(value=value):
            return domain.GenericInteger(value=value)
        case schemas.GenericChoiceSchema(option_id=option_id):
            return domain.GenericChoice(option_id=option_id)
    raise ValueError(f"unrecognised prediction payload: {payload!r}")
