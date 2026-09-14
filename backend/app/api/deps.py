"""FastAPI dependencies: the session, the repositories, the services.

The session is an HTTP-only signed cookie (spec 7.5). Everything below resolves
interfaces, never implementations, so step 4 swaps the repository set here and
nowhere else.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Cookie, Depends, Request
from itsdangerous import BadSignature, URLSafeSerializer

from app.domain.entities import User
from app.providers.email import ConsoleEmailProvider, EmailProvider
from app.repositories.interfaces import Repositories
from app.services.auth import AuthService
from app.services.errors import Forbidden, Unauthorized
from app.services.games import GameService
from app.services.play import PlayService
from app.services.ranking import RankingService
from app.services.results import ResultsService

SESSION_COOKIE = "session"
_SECRET = os.environ.get("SESSION_SECRET", "development-only-not-a-secret")
_serializer = URLSafeSerializer(_SECRET, salt="session")


def sign_session(user_id: str) -> str:
    return _serializer.dumps({"userId": user_id})


def read_session(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        payload = _serializer.loads(raw)
    except BadSignature:
        return None
    user_id = payload.get("userId") if isinstance(payload, dict) else None
    return user_id if isinstance(user_id, str) else None


def get_repositories(request: Request) -> Repositories:
    """The one place an implementation is chosen (step 4 swaps it here)."""
    return request.app.state.repositories


def get_email_provider() -> EmailProvider:
    return ConsoleEmailProvider()


RepositoriesDep = Annotated[Repositories, Depends(get_repositories)]


def get_optional_user(
    repos: RepositoriesDep,
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User | None:
    """Who is looking, or nobody. Never raises — the landing page may ask."""
    user_id = read_session(session)
    return repos.users.get(user_id) if user_id else None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(user: OptionalUser) -> User:
    if user is None:
        raise Unauthorized("You must be signed in to do that.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise Forbidden("That is an organiser action.")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


def get_auth_service(
    repos: RepositoriesDep,
    email: Annotated[EmailProvider, Depends(get_email_provider)],
) -> AuthService:
    return AuthService(repos, email)


def get_game_service(repos: RepositoriesDep) -> GameService:
    return GameService(repos)


def get_play_service(repos: RepositoriesDep) -> PlayService:
    return PlayService(repos)


def get_ranking_service(repos: RepositoriesDep) -> RankingService:
    return RankingService(repos)


def get_results_service(repos: RepositoriesDep) -> ResultsService:
    return ResultsService(repos)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
GameServiceDep = Annotated[GameService, Depends(get_game_service)]
PlayServiceDep = Annotated[PlayService, Depends(get_play_service)]
RankingServiceDep = Annotated[RankingService, Depends(get_ranking_service)]
ResultsServiceDep = Annotated[ResultsService, Depends(get_results_service)]
