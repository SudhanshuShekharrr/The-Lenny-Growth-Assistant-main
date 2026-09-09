"""
Structured error responses.

Ensures every error the client sees has the same shape, which is the
"structured errors" bar set in the assignment's API-quality requirement.
Registered on the app in main.py via app.add_exception_handler(...).
"""

import logging
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger("lenny.errors")


def _error_body(message: str, code: str, request: Request) -> dict:
    return {
        "error": {
            "message": message,
            "code": code,
            "requestId": getattr(request.state, "request_id", None),
        }
    }


async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(str(exc.detail), "HTTP_ERROR", request),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("Request validation failed.", "VALIDATION_ERROR", request)
        | {"details": exc.errors()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log full detail server-side; never leak stack traces to the client.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("Internal server error", "INTERNAL_ERROR", request),
    )
