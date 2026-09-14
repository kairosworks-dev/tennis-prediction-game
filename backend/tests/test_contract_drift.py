"""AGENTS.md hard rule 3: the committed contract and the generated schema
must not drift.

This is the check that fails in CI. When it fails, fix the cause — the code or
the contract — never the check.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.main import create_app

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"


def committed_operations() -> dict[str, str]:
    """operationId -> "METHOD /path", as the contract declares it."""
    document = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                found[operation["operationId"]] = f"{method.upper()} {path}"
    return found


def generated_operations() -> dict[str, str]:
    spec = create_app(seed=False).openapi()
    found: dict[str, str] = {}
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post", "put", "patch", "delete"}:
                # The app is mounted under /api; the contract says so in `servers`.
                found[operation["operationId"]] = f"{method.upper()} {path.removeprefix('/api')}"
    return found


def test_the_contract_and_the_backend_expose_the_same_operations() -> None:
    committed = committed_operations()
    generated = generated_operations()

    missing = sorted(set(committed) - set(generated))
    extra = sorted(set(generated) - set(committed))
    assert not missing, f"in openapi.yaml but not implemented: {missing}"
    assert not extra, f"implemented but not in openapi.yaml: {extra}"


def test_every_operation_is_mounted_at_the_path_the_contract_declares() -> None:
    committed = committed_operations()
    generated = generated_operations()

    # Path parameters are named differently by convention on each side
    # (tournamentId in the contract, tournament_id in Python), so compare shape.
    def normalise(route: str) -> str:
        parts = []
        for segment in route.split("/"):
            parts.append("{param}" if segment.startswith("{") else segment)
        return "/".join(parts)

    mismatches = {
        operation_id: (route, generated[operation_id])
        for operation_id, route in committed.items()
        if operation_id in generated and normalise(route) != normalise(generated[operation_id])
    }
    assert not mismatches, f"path mismatches: {mismatches}"


def test_the_contract_covers_every_first_pass_operation() -> None:
    """Nineteen operations, per decision D14."""
    assert len(committed_operations()) == 19
