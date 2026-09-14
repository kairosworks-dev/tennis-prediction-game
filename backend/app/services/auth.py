"""Sign-up and sign-in (spec 4.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.domain.entities import User
from app.providers.email import EmailProvider
from app.repositories.interfaces import Repositories
from app.services.errors import Conflict, Forbidden, ValidationFailed

MIN_PASSWORD_LENGTH = 10
MIN_DISPLAY_NAME_LENGTH = 2

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        # A wrong password and a malformed stored hash are both failed sign-ins.
        return False


class AuthService:
    def __init__(self, repos: Repositories, email: EmailProvider) -> None:
        self._repos = repos
        self._email = email

    def register(self, email: str, password: str, display_name: str) -> User:
        address = email.strip().lower()
        if "@" not in address:
            raise ValidationFailed(
                "That does not look like an email address.",
                {"email": ["Enter a valid address."]},
            )
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationFailed(
                "Passwords need at least ten characters.", {"password": ["Too short."]}
            )
        if len(display_name.strip()) < MIN_DISPLAY_NAME_LENGTH:
            raise ValidationFailed(
                "Display names need at least two characters.", {"displayName": ["Too short."]}
            )
        if self._repos.users.get_by_email(address) is not None:
            raise Conflict("An account already exists for that address.")

        user = User(
            id=f"user-{uuid4().hex[:12]}",
            email=address,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            full_name=None,
            is_admin=False,
            is_active=True,
            email_verified_at=None,
            created_at=datetime.now(UTC),
        )
        self._repos.users.add(user)
        self._repos.commit()
        # Transactional email only in the MVP (decision D11); the mock prints it.
        self._email.send_verification(user.email, token=f"verify-{user.id}")
        return user

    def login(self, email: str, password: str) -> User:
        user = self._repos.users.get_by_email(email)
        if user is None or not verify_password(user.password_hash, password):
            raise ValidationFailed("That email and password do not match an account.")
        if not user.is_active:
            raise Forbidden("That account has been deactivated.")
        return user
