"""Domain exceptions and the HTTP problem-detail representation.

Services raise these; routers never translate them by hand. The handlers
registered in `app.main` convert them into RFC 7807 `application/problem+json`
responses.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for every expected, user-facing failure."""

    status_code: int = 500
    error_code: str = "internal_error"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        error_code: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.title
        if error_code:
            self.error_code = error_code
        self.extra = extra or {}
        super().__init__(self.detail)

    def to_problem(self, instance: str | None = None) -> dict[str, Any]:
        problem: dict[str, Any] = {
            "type": f"about:blank#{self.error_code}",
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "code": self.error_code,
        }
        if instance:
            problem["instance"] = instance
        if self.extra:
            problem["extra"] = self.extra
        return problem


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"
    title = "Resource Not Found"

    def __init__(self, resource: str, identifier: Any = None, **kwargs: Any) -> None:
        detail = f"{resource} not found" if identifier is None else f"{resource} '{identifier}' not found"
        super().__init__(detail, **kwargs)


class ConflictError(AppError):
    status_code = 409
    error_code = "conflict"
    title = "Conflict"


class ValidationError(AppError):
    status_code = 422
    error_code = "validation_error"
    title = "Validation Failed"


class BadRequestError(AppError):
    status_code = 400
    error_code = "bad_request"
    title = "Bad Request"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "unauthorized"
    title = "Not Authenticated"


class ForbiddenError(AppError):
    status_code = 403
    error_code = "forbidden"
    title = "Forbidden"


class ServiceUnavailableError(AppError):
    status_code = 503
    error_code = "service_unavailable"
    title = "Service Unavailable"
