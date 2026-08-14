import logging
from enum import Enum

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    UNAUTHORIZED = "unauthorized"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    INVALID_JSON = "invalid_json"
    INVALID_DIFF = "invalid_diff"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    INTERNAL = "internal"


# Every status code raised via HTTPException in this service maps to exactly
# one contract error code, so the status code alone is enough to recover it.
_STATUS_TO_CODE = {
    400: ErrorCode.INVALID_JSON,
    401: ErrorCode.UNAUTHORIZED,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.IDEMPOTENCY_CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    422: ErrorCode.INVALID_DIFF,
    429: ErrorCode.RATE_LIMITED,
}


def _envelope(
    status_code: int,
    code: ErrorCode,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code.value, "message": message}},
        headers=headers,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL)
    return _envelope(
        exc.status_code, code, str(exc.detail), getattr(exc, "headers", None)
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _envelope(400, ErrorCode.INVALID_JSON, "Malformed request body")


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _envelope(500, ErrorCode.INTERNAL, "Internal server error")
