"""Consistent error envelope (spec §5.2).

    { "error": { "code", "message", "details", "request_id" } }

Every failure — validation, auth, not-found, conflict, unexpected — leaves the API
in this shape, and every response carries ``X-Request-Id``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.core.request_context import get_request_id

log = get_logger("errors")


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(
        self, message: str, *, details: Any | None = None, code: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class PreconditionFailedError(AppError):
    """Optimistic-concurrency failure: the resource changed under the caller."""

    status_code = status.HTTP_412_PRECONDITION_FAILED
    code = "precondition_failed"


class PreconditionRequiredError(AppError):
    status_code = status.HTTP_428_PRECONDITION_REQUIRED
    code = "precondition_required"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class AuthorizationError(AppError):
    """Deny-by-default authorization failure (spec §2.3, §7.2)."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


def _envelope(code: str, message: str, details: Any | None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def _json_error(status_code: int, code: str, message: str, details: Any | None) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content=_envelope(code, message, details))
    request_id = get_request_id()
    if request_id:
        response.headers["X-Request-Id"] = request_id
    return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("app_error", code=exc.code, status=exc.status_code)
        else:
            log.info("app_error", code=exc.code, status=exc.status_code)
        return _json_error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _json_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "Request validation failed.",
            jsonable_encoder(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "unauthenticated",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
        return _json_error(exc.status_code, code, str(exc.detail), None)

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_exception", error_type=type(exc).__name__)
        return _json_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
            None,
        )
