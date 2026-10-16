"""The seed script reports what it did (issue #32).

Run as a subprocess on purpose: the defect was an import side effect (importing
`app.main` seeded before the script looked), so only a fresh interpreter shows
it. In-process, `app.main` is already imported by the rest of the suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _run_seed_script(database_url: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "TEST_DATABASE_URL"}
    env["DATABASE_URL"] = database_url
    env["REPOSITORY_BACKEND"] = "sqlalchemy"
    return subprocess.run(
        [sys.executable, "scripts_seed.py"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_first_run_says_seeded_and_second_run_says_already_present(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'seed.db'}"

    first = _run_seed_script(url)
    assert first.returncode == 0, first.stderr
    first_lines = first.stdout.splitlines()
    assert first_lines[0] == "Seeded roland-garros-2026."
    assert len(first_lines) == 3  # the message, then the two account lines
    assert "you@example.com" in first_lines[1]
    assert "organiser@example.com" in first_lines[2]
    assert "already present" not in first.stdout

    second = _run_seed_script(url)
    assert second.returncode == 0, second.stderr
    assert second.stdout == "Demo game roland-garros-2026 already present; nothing to do.\n"
    assert "Seeded" not in second.stdout


def test_main_module_still_exports_the_repository_builders() -> None:
    from app import bootstrap, main

    assert main.build_repository_scope is bootstrap.build_repository_scope
    assert main.build_repositories is bootstrap.build_repositories
