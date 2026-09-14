"""Email behind an interface, with a console mock (decision D8).

No vendor is needed for local development, and adding one later is a second
implementation rather than a change at the call sites.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    @abstractmethod
    def send_verification(self, address: str, token: str) -> None: ...

    @abstractmethod
    def send_password_reset(self, address: str, token: str) -> None: ...


class ConsoleEmailProvider(EmailProvider):
    """Prints instead of sending. The only implementation the MVP needs."""

    def send_verification(self, address: str, token: str) -> None:
        logger.info("[email] verification for %s: token=%s", address, token)

    def send_password_reset(self, address: str, token: str) -> None:
        logger.info("[email] password reset for %s: token=%s", address, token)
