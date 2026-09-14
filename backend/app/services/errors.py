"""Service-level failures.

The API layer turns each of these into an RFC 7807 problem. Keeping them here
rather than raising `HTTPException` is what lets services stay testable without
FastAPI in the way.
"""

from __future__ import annotations


class ServiceError(Exception):
    status = 400

    def __init__(self, detail: str, errors: dict[str, list[str]] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or {}


class NotFound(ServiceError):
    status = 404


class Unauthorized(ServiceError):
    status = 401


class Forbidden(ServiceError):
    status = 403


class Conflict(ServiceError):
    status = 409


class ValidationFailed(ServiceError):
    status = 422
