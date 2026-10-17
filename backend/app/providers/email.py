"""Email behind an interface, with two mock implementations (decision D8).

No vendor is needed for development, and adding one later is a third
implementation rather than a change at the call sites. `EMAIL_PROVIDER` picks
one at start-up (see `app.bootstrap.build_email_provider`):

- `DiscardEmailProvider` (the default) does nothing observable, so a deployed
  environment never writes a participant's address or a token anywhere.
- `ConsoleEmailProvider` prints to stderr, for a machine you control.
"""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod


class EmailProvider(ABC):
    @abstractmethod
    def send_verification(self, address: str, token: str) -> None: ...

    @abstractmethod
    def send_password_reset(self, address: str, token: str) -> None: ...


class DiscardEmailProvider(EmailProvider):
    """Sends nothing and records nothing: no output, no logger, no file, no network.

    The default, because the safe behaviour must not depend on anyone setting a
    variable on a deployed environment.
    """

    def send_verification(self, address: str, token: str) -> None:
        return None

    def send_password_reset(self, address: str, token: str) -> None:
        return None


class ConsoleEmailProvider(EmailProvider):
    """Prints the message to stderr instead of sending it. Local use only.

    A plain `print`, not `logging`: it appears under a bare `uvicorn` without any
    logging configuration, and no handler added to the root logger later can
    ship it somewhere else.
    """

    def send_verification(self, address: str, token: str) -> None:
        print(f"[email] verification for {address}: token={token}", file=sys.stderr, flush=True)

    def send_password_reset(self, address: str, token: str) -> None:
        print(f"[email] password reset for {address}: token={token}", file=sys.stderr, flush=True)
