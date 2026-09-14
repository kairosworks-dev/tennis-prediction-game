"""Seed a demo game into the configured database.

    uv run python scripts_seed.py

Step 4's definition of done asks for a seed script that produces a realistic
demo game. It runs through the repository interfaces, so it works against
either implementation.
"""

from __future__ import annotations

import os

from app.main import build_repositories
from app.seed import DEMO_PASSWORD, seed_demo_game


def main() -> None:
    os.environ.setdefault("REPOSITORY_BACKEND", "sqlite")
    repos = build_repositories()
    if repos.tournaments.get("roland-garros-2026") is not None:
        print("Already seeded; nothing to do.")
        return
    tournament_id = seed_demo_game(repos)
    print(f"Seeded {tournament_id}.")
    print(f"  participant: you@example.com / {DEMO_PASSWORD}")
    print(f"  organiser:   organiser@example.com / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
