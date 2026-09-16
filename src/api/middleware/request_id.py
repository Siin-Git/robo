"""Request ID + access logging middleware (no sensitive payload logging)."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = logging.getLogger("robo.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"request_id": request_id})
            raise
        duration_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-ID"] = request_id
        log.info("%s %s -> %s (%.1fms)", request.method, request.url.path,
                 response.status_code, duration_ms,
                 extra={"request_id": request_id})
        return response
