"""Error codes and the handlers that turn every failure into {"error": {"code", "params"}}.

The server never sends prose. Each code needs an `errors.<CODE>` key in both
frontend/src/locales/ar.json and en.json; tests/test_error_codes.py enforces it.
"""

import logging
from enum import StrEnum
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    # Auth and users (B2). The first five are the names the F1 shell codes against.
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    RATE_LIMITED = "RATE_LIMITED"
    GUEST_DISABLED = "GUEST_DISABLED"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    CSRF_REJECTED = "CSRF_REJECTED"
    EMAIL_TAKEN = "EMAIL_TAKEN"
    PASSWORD_TOO_SHORT = "PASSWORD_TOO_SHORT"  # noqa: S105 - an error code, not a password
    CANNOT_CHANGE_OWN_ACCESS = "CANNOT_CHANGE_OWN_ACCESS"
    GUEST_ROLE_FIXED = "GUEST_ROLE_FIXED"
    # Documents and ingestion (B3). Ingestion failures are stored as documents.error_code.
    DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    FILE_CORRUPT = "FILE_CORRUPT"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    NO_TEXT_LAYER = "NO_TEXT_LAYER"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    CONVERSION_FAILED = "CONVERSION_FAILED"
    TXT_ENCODING_UNKNOWN = "TXT_ENCODING_UNKNOWN"
    WORKER_TIMEOUT = "WORKER_TIMEOUT"
    ML_UNAVAILABLE = "ML_UNAVAILABLE"
    DOCUMENT_NOT_READY = "DOCUMENT_NOT_READY"
    DOCUMENT_NOT_RETRYABLE = "DOCUMENT_NOT_RETRYABLE"
    # Ask (R1). A refusal is an outcome, not an error: these are for when no answer could run.
    SEARCH_UNAVAILABLE = "SEARCH_UNAVAILABLE"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    HOSTED_LLM_NON_SEED_DATA = "HOSTED_LLM_NON_SEED_DATA"


_STATUS_TO_CODE = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    429: ErrorCode.RATE_LIMITED,
}


class ApiError(Exception):
    """Raise from route code to return a coded error with a given HTTP status."""

    def __init__(self, status_code: int, code: ErrorCode, **params: Any) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.params = params


def error_body(code: ErrorCode, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code.value, "params": params or {}}}


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    err = cast(ApiError, exc)
    return JSONResponse(error_body(err.code, err.params), status_code=err.status_code)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    err = cast(StarletteHTTPException, exc)
    code = _STATUS_TO_CODE.get(err.status_code, ErrorCode.BAD_REQUEST)
    if err.status_code >= 500:
        code = ErrorCode.INTERNAL_ERROR
    return JSONResponse(error_body(code), status_code=err.status_code, headers=err.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    errors = cast(RequestValidationError, exc).errors()
    fields = sorted({".".join(str(p) for p in e["loc"]) for e in errors})
    return JSONResponse(error_body(ErrorCode.VALIDATION_ERROR, {"fields": fields}), status_code=422)


async def _unhandled_error(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled error", exc_info=exc)
    return JSONResponse(error_body(ErrorCode.INTERNAL_ERROR), status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
