"""The email provider choice and what it writes (issue #59).

The default must write nothing, so a deployed environment that sets no variable
never puts a participant's address or a token in its output. The positive
control in the same file proves the capture would see it: without it the
"nothing appears" test could pass for the wrong reason, which is how the latent
leak went unseen.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import build_email_provider
from app.main import create_app
from app.providers.email import ConsoleEmailProvider, DiscardEmailProvider, EmailProvider
from app.repositories.interfaces import Repositories

MakeApp = Callable[[], TestClient]

RESET_TOKEN = "reset-probe-value"
VERIFY_TOKEN = "verify-probe-value"


@pytest.fixture
def make_client(repositories: Repositories) -> MakeApp:
    """Builds the app on demand, so a test sets the environment first."""
    return lambda: TestClient(create_app(repositories=repositories))


def _register(client: TestClient, address: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": address, "password": "a-long-enough-password", "displayName": "Probe"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["requiresEmailVerification"] is True
    return body["user"]["id"]


def _sentinel() -> tuple[str, str]:
    local = f"leak-probe-{uuid.uuid4().hex}"
    return f"{local}@example.test", local


class TestSelection:
    def test_console(self) -> None:
        assert isinstance(build_email_provider("console"), ConsoleEmailProvider)

    @pytest.mark.parametrize("value", ["discard", ""])
    def test_discard_and_empty(self, value: str) -> None:
        assert isinstance(build_email_provider(value), DiscardEmailProvider)

    def test_unset_is_discard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)
        assert isinstance(build_email_provider(), DiscardEmailProvider)

    def test_the_environment_is_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_PROVIDER", "console")
        assert isinstance(build_email_provider(), ConsoleEmailProvider)
        monkeypatch.setenv("EMAIL_PROVIDER", "")
        assert isinstance(build_email_provider(), DiscardEmailProvider)

    @pytest.mark.parametrize("value", ["consol", "Console", "smtp", " console"])
    def test_an_unknown_value_stops_start_up(
        self, value: str, monkeypatch: pytest.MonkeyPatch, repositories: Repositories
    ) -> None:
        with pytest.raises(ValueError, match="EMAIL_PROVIDER") as raised:
            build_email_provider(value)
        assert "console" in str(raised.value) and "discard" in str(raised.value)

        monkeypatch.setenv("EMAIL_PROVIDER", value)
        with pytest.raises(ValueError, match="EMAIL_PROVIDER"):
            create_app(repositories=repositories)

    def test_the_app_holds_the_provider_it_built_once(
        self, monkeypatch: pytest.MonkeyPatch, make_client: MakeApp
    ) -> None:
        monkeypatch.setenv("EMAIL_PROVIDER", "console")
        client = make_client()
        provider = client.app.state.email_provider  # type: ignore[attr-defined]
        assert isinstance(provider, ConsoleEmailProvider)
        # Changing the environment afterwards changes nothing: read at start-up.
        monkeypatch.setenv("EMAIL_PROVIDER", "discard")
        _register(client, _sentinel()[0])
        assert client.app.state.email_provider is provider  # type: ignore[attr-defined]


def _everything_written(capfd: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> str:
    out, err = capfd.readouterr()
    records = "\n".join(
        f"{record.getMessage()} {record.args!r} {record.__dict__!r}" for record in caplog.records
    )
    return f"{out}\n{err}\n{records}"


class TestDeployedConfiguration:
    """`EMAIL_PROVIDER` is not set, as on a platform nobody configured."""

    @pytest.fixture(autouse=True)
    def _unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EMAIL_PROVIDER", raising=False)

    def test_registration_writes_nothing_about_the_user(
        self,
        make_client: MakeApp,
        capfd: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        address, local = _sentinel()
        client = make_client()
        caplog.set_level(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        capfd.readouterr()

        user_id = _register(client, address)

        written = _everything_written(capfd, caplog)
        for needle in (address, local, "verify-", user_id):
            assert needle not in written

    def test_password_reset_writes_nothing(
        self,
        make_client: MakeApp,
        capfd: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        address, _ = _sentinel()
        provider: EmailProvider = make_client().app.state.email_provider  # type: ignore[attr-defined]
        caplog.set_level(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        capfd.readouterr()

        provider.send_password_reset(address, RESET_TOKEN)
        provider.send_verification(address, VERIFY_TOKEN)

        written = _everything_written(capfd, caplog)
        assert written.strip() == ""
        assert address not in written

    def test_discard_set_explicitly_behaves_the_same(
        self,
        monkeypatch: pytest.MonkeyPatch,
        make_client: MakeApp,
        capfd: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("EMAIL_PROVIDER", "discard")
        address, local = _sentinel()
        client = make_client()
        assert isinstance(client.app.state.email_provider, DiscardEmailProvider)  # type: ignore[attr-defined]
        caplog.set_level(logging.DEBUG)
        capfd.readouterr()

        user_id = _register(client, address)

        written = _everything_written(capfd, caplog)
        for needle in (address, local, "verify-", user_id):
            assert needle not in written


class TestConsoleConfiguration:
    """The positive control: the same capture does see the line under `console`."""

    @pytest.fixture(autouse=True)
    def _console(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMAIL_PROVIDER", "console")

    def test_registration_prints_the_line_to_stderr(
        self,
        make_client: MakeApp,
        capfd: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        address, _ = _sentinel()
        client = make_client()
        caplog.set_level(logging.DEBUG)
        capfd.readouterr()

        user_id = _register(client, address)

        out, err = capfd.readouterr()
        assert f"[email] verification for {address}: token=verify-{user_id}" in err
        assert address not in out
        # Printed, not logged: no logging configuration is involved, and a root
        # handler added later has nothing to ship.
        assert address not in _everything_written(capfd, caplog)

    def test_password_reset_prints_the_line_to_stderr(
        self, make_client: MakeApp, capfd: pytest.CaptureFixture[str]
    ) -> None:
        address, _ = _sentinel()
        provider: EmailProvider = make_client().app.state.email_provider  # type: ignore[attr-defined]
        capfd.readouterr()

        provider.send_password_reset(address, RESET_TOKEN)

        assert f"[email] password reset for {address}: token={RESET_TOKEN}" in (
            capfd.readouterr().err
        )
