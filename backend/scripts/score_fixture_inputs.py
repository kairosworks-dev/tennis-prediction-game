"""Score the frontend's fixture inputs with this backend's engine.

    uv run python scripts/score_fixture_inputs.py <inputs.json> <entries.json>

The frontend mock serves pre-computed score entries rather than computing them,
because scoring belongs to the backend (AGENTS.md rule 2). This is what
produces them: the same pure function the API uses, over the frontend's fixture
data. `--check` additionally diffs the result against whatever the input file
records as the current entries, which is how the old TypeScript scorer was
retired without taking anyone's word for it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.entities import ScoringProfile  # noqa: E402
from app.domain.enums import RoundReached  # noqa: E402
from app.domain.scoring import ScoringContext, score_prediction  # noqa: E402
from app.repositories.mapping import payload_from_json  # noqa: E402


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def to_domain(payload: dict[str, Any] | None) -> object | None:
    """The wire uses camelCase; the domain dataclasses use snake_case."""
    if payload is None:
        return None
    converted: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "picks":
            converted["picks"] = [{snake(k): v for k, v in pick.items()} for pick in value]
        else:
            converted[snake(key)] = value
    return payload_from_json(converted)


def profile_from(raw: dict[str, Any]) -> ScoringProfile:
    return ScoringProfile(
        **{
            snake(key): (tuple(value) if isinstance(value, list) else value)
            for key, value in raw.items()
        }
    )


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    inputs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    names = inputs["playerNames"]
    entries: list[dict[str, Any]] = []

    for game in inputs["games"]:
        context = ScoringContext(
            outcomes={pid: RoundReached(r) for pid, r in game["outcomes"].items()},
            profile=profile_from(game["scoringProfile"]),
            names=names,
        )
        for answer in game["answers"]:
            award = score_prediction(
                to_domain(answer["payload"]), to_domain(answer["correctAnswer"]), context
            )
            if award is None:
                continue
            entries.append(
                {
                    "participationId": answer["participationId"],
                    "questionId": answer["questionId"],
                    "points": award.points,
                    "reason": award.reason,
                }
            )

    Path(sys.argv[2]).write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {sys.argv[2]}: {len(entries)} score entries")

    if "--check" in sys.argv and "currentScores" in inputs:
        current = {(e["participationId"], e["questionId"]): e for e in inputs["currentScores"]}
        produced = {(e["participationId"], e["questionId"]): e for e in entries}

        only_current = sorted(set(current) - set(produced))
        only_produced = sorted(set(produced) - set(current))
        differing = [
            (key, current[key], produced[key])
            for key in sorted(set(current) & set(produced))
            if current[key]["points"] != produced[key]["points"]
            or current[key]["reason"] != produced[key]["reason"]
        ]

        print(f"  only in the existing entries: {len(only_current)}")
        print(f"  only in this engine's output: {len(only_produced)}")
        print(f"  present in both but different: {len(differing)}")
        for key, was, now in differing[:5]:
            print(f"    {key[1]}")
            print(f"      was: {was['points']} — {was['reason']}")
            print(f"      now: {now['points']} — {now['reason']}")
        for key in only_current[:3]:
            print(f"    only existing: {key[1]} — {current[key]['reason']}")
        for key in only_produced[:3]:
            print(f"    only produced: {key[1]} — {produced[key]['reason']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
