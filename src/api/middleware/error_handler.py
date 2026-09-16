"""Exception handlers: ApiError + validation errors -> common envelope."""
from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..errors import ApiError


def _rid(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status,
        content={"error": {"code": exc.code, "message": exc.message,
                           "details": exc.details},
                 "request_id": _rid(request)},
        headers={"X-Request-ID": _rid(request)},
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = {"errors": [{k: v for k, v in e.items() if k in ("loc", "msg", "type")}
                          for e in exc.errors()]}
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR",
                           "message": "Request validation failed.",
                           "details": details},
                 "request_id": _rid(request)},
        headers={"X-Request-ID": _rid(request)},
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"HTTP_{exc.status_code}",
                           "message": str(exc.detail), "details": {}},
                 "request_id": _rid(request)},
        headers={"X-Request-ID": _rid(request)},
    )


async def unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR",
                           "message": "Unexpected server error.", "details": {}},
                 "request_id": _rid(request)},
        headers={"X-Request-ID": _rid(request)},
    )
