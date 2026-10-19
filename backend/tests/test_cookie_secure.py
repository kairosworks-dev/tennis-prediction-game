"""The `Secure` attribute on the session cookie (issue #7).

Assertions are on the raw `Set-Cookie` response header, not on the client's
cookie jar: over `http://testserver` a `Secure` cookie is neither stored nor
sent back, so a second request under `true` would fail for the wrong reason.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import build_cookie_secure
from app.main import create_app
from app.repositories.interfaces import Repositories
from app.seed import DEMO_PASSWORD

MakeApp = Callable[[], TestClient]


@pytest.fixture
def make_client(repositories: Repositories) -> MakeApp:
    """Builds the app on demand, so a test sets the environment first."""
    return lambda: TestClient(create_app(repositories=repositories))


def _attributes(header: str) -> list[str]:
    return [part.strip().lower() for part in header.split(";")]


def _headers(client: TestClient) -> dict[str, str]:
    """The `Set-Cookie` header of register, login and logout."""
    register = client.post(
        "/api/auth/register",
        json={
            "email": f"cookie-{uuid.uuid4().hex}@example.test",
            "password": "a-long-enough-password",
            "displayName": "Cookie",
        },
    )
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/auth/login", json={"email": "you@example.com", "password": DEMO_PASSWORD}
    )
    assert login.status_code == 200, login.text
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204, logout.text
    return {
        "register": register.headers["set-cookie"],
        "login": login.headers["set-cookie"],
        "logout": logout.headers["set-cookie"],
    }


def _assert_common(headers: dict[str, str]) -> None:
    for name, header in headers.items():
        attributes = _attributes(header)
        assert header.startswith("session="), name
        assert "httponly" in attributes, name
        assert "samesite=lax" in attributes, name
        assert "path=/" in attributes, name
        assert not any(a.startswith("domain") for a in attributes), name
    assert "max-age=0" in _attributes(headers["logout"])


class TestSecureTrue:
    def test_every_session_cookie_is_secure(
        self, monkeypatch: pytest.MonkeyPatch, make_client: MakeApp
    ) -> None:
        monkeypatch.setenv("COOKIE_SECURE", "true")
        headers = _headers(make_client())
        _assert_common(headers)
        for name, header in headers.items():
            assert "secure" in _attributes(header), name


class TestNotSecure:
    @pytest.mark.parametrize("value", ["false", ""])
    def test_set_to_false_or_empty(
        self, value: str, monkeypatch: pytest.MonkeyPatch, make_client: MakeApp
    ) -> None:
        monkeypatch.setenv("COOKIE_SECURE", value)
        headers = _headers(make_client())
        _assert_common(headers)
        for name, header in headers.items():
            assert "secure" not in _attributes(header), name

    def test_unset(self, monkeypatch: pytest.MonkeyPatch, make_client: MakeApp) -> None:
        monkeypatch.delenv("COOKIE_SECURE", raising=False)
        headers = _headers(make_client())
        _assert_common(headers)
        for name, header in headers.items():
            assert "secure" not in _attributes(header), name


class TestSelection:
    @pytest.mark.parametrize(("value", "expected"), [("true", True), ("false", False), ("", False)])
    def test_accepted_values(self, value: str, expected: bool) -> None:
        assert build_cookie_secure(value) is expected

    def test_unset_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("COOKIE_SECURE", raising=False)
        assert build_cookie_secure() is False

    def test_the_environment_is_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("COOKIE_SECURE", "true")
        assert build_cookie_secure() is True

    @pytest.mark.parametrize(
        "value", ["True", "TRUE", "1", "0", "yes", "on", "treu", " true", "true ", "False"]
    )
    def test_any_other_value_stops_start_up(
        self, value: str, monkeypatch: pytest.MonkeyPatch, repositories: Repositories
    ) -> None:
        with pytest.raises(ValueError, match="COOKIE_SECURE") as raised:
            build_cookie_secure(value)
        assert "true" in str(raised.value) and "false" in str(raised.value)

        monkeypatch.setenv("COOKIE_SECURE", value)
        with pytest.raises(ValueError, match="COOKIE_SECURE"):
            create_app(repositories=repositories)

    def test_the_app_holds_the_value_it_read_once(
        self, monkeypatch: pytest.MonkeyPatch, make_client: MakeApp
    ) -> None:
        monkeypatch.setenv("COOKIE_SECURE", "true")
        client = make_client()
        assert client.app.state.cookie_secure is True  # type: ignore[attr-defined]
        # Changing the environment afterwards changes nothing: read at start-up.
        monkeypatch.setenv("COOKIE_SECURE", "false")
        assert "secure" in _attributes(_headers(client)["login"])
