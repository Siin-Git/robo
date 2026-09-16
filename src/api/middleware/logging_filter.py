"""Logging redaction: sensitive keys are never written to logs.

Install once at process start (import side effect is opt-in via install()).
Request bodies are never logged by the API middleware by design; this filter
is defense-in-depth for any dict-shaped log records.
"""
from __future__ import annotations

import logging

REDACTED_KEYS = {"password", "current_password", "new_password", "session", "token",
                 "csrf", "cookie", "authorization", "set-cookie"}
REDACTED = "***REDACTED***"


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = {k: (REDACTED if str(k).lower() in REDACTED_KEYS else v)
                           for k, v in record.args.items()}
        msg = str(record.getMessage())
        lowered = msg.lower()
        if any(k in lowered for k in ("password=", "token=", "csrf=")):
            record.msg = REDACTED
            record.args = ()
        return True


def install() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    root = logging.getLogger("robo")
    if not any(isinstance(h, logging.StreamHandler) and
               any(isinstance(f, RedactingFilter) for f in h.filters)
               for h in root.handlers):
        root.addHandler(handler)
