"""Authentication routes (spec 4.2)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.api import schemas
from app.api.deps import SESSION_COOKIE, AuthServiceDep, OptionalUser, sign_session

router = APIRouter(tags=["auth"])


def _set_session(request: Request, response: Response, user_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        sign_session(user_id),
        httponly=True,
        samesite="lax",
        path="/",
        secure=request.app.state.cookie_secure,
    )


@router.post(
    "/auth/register",
    operation_id="register",
    status_code=201,
    response_model=schemas.AuthenticatedUser,
    summary="Create an account",
)
def register(
    body: schemas.RegisterRequest, request: Request, response: Response, auth: AuthServiceDep
) -> schemas.AuthenticatedUser:
    user = auth.register(body.email, body.password, body.display_name)
    _set_session(request, response, user.id)
    return schemas.AuthenticatedUser(
        user=schemas.UserSchema.model_validate(user), requires_email_verification=True
    )


@router.post(
    "/auth/login",
    operation_id="login",
    response_model=schemas.AuthenticatedUser,
    summary="Sign in",
)
def login(
    body: schemas.LoginRequest, request: Request, response: Response, auth: AuthServiceDep
) -> schemas.AuthenticatedUser:
    user = auth.login(body.email, body.password)
    _set_session(request, response, user.id)
    return schemas.AuthenticatedUser(
        user=schemas.UserSchema.model_validate(user),
        requires_email_verification=user.email_verified_at is None,
    )


@router.post("/auth/logout", operation_id="logout", status_code=204, summary="Sign out")
def logout(request: Request, response: Response) -> None:
    # The deletion carries the attributes of the cookie it deletes.
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.app.state.cookie_secure,
    )


@router.get(
    "/me",
    operation_id="getCurrentUser",
    response_model=schemas.UserSchema | None,
    summary="The signed-in user, or null",
)
def get_me(user: OptionalUser) -> schemas.UserSchema | None:
    # Null rather than 401, so an anonymous visitor is not treated as an error.
    return schemas.UserSchema.model_validate(user) if user else None
