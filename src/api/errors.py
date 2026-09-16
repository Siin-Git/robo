"""Unified API error contract: {error: {code, message, details}, request_id}."""
from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400,
                 details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


def not_found(code: str, message: str) -> ApiError:
    return ApiError(code, message, 404)


def conflict(code: str, message: str) -> ApiError:
    return ApiError(code, message, 409)


def unprocessable(code: str, message: str, details=None) -> ApiError:
    return ApiError(code, message, 422, details)


def unavailable(code: str, message: str) -> ApiError:
    return ApiError(code, message, 503)
