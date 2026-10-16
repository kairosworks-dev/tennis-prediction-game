"""Seed a demo game into the configured database.

    uv run python scripts_seed.py

Step 4's definition of done asks for a seed script that produces a realistic
demo game. It runs through the repository interfaces, so it works against
either implementation.

It imports the repository builders from `app.bootstrap` and never the app
module: importing that runs `create_app()`, which seeds, and the message below
would then always say the game was already there (issue #32). This script is the
one place that reports whether it seeded.
"""

from __future__ import annotations

import os

from app.bootstrap import build_repositories
from app.seed import DEMO_PASSWORD, seed_demo_game


def main() -> None:
    os.environ.setdefault("REPOSITORY_BACKEND", "sqlalchemy")
    repos = build_repositories()
    if repos.tournaments.get("roland-garros-2026") is not None:
        print("Demo game roland-garros-2026 already present; nothing to do.")
        return
    tournament_id = seed_demo_game(repos)
    print(f"Seeded {tournament_id}.")
    print(f"  participant: you@example.com / {DEMO_PASSWORD}")
    print(f"  organiser:   organiser@example.com / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
