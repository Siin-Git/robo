"""Database configuration: env-driven, no hardcoded paths or secrets."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        pass


_load_dotenv()

BACKENDS = ("sqlite", "postgres")


def get_backend() -> str:
    backend = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower()
    if backend not in BACKENDS:
        raise ValueError(f"unknown DATABASE_BACKEND={backend!r}")
    return backend


def get_database_url(backend: str | None = None) -> str:
    backend = backend or get_backend()
    if backend == "postgres":
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL is not set (required for postgres backend)")
        return url
    # Local profile has its own file; APP_PROFILE=local takes precedence over SQLITE_PATH.
    if os.environ.get("APP_PROFILE", "").strip().lower() == "local":
        return f"sqlite:///{ROOT / 'data' / 'forward_local.db'}"
    path = os.environ.get("SQLITE_PATH", str(ROOT / "data" / "forward_test.db"))
    return f"sqlite:///{path}"


def get_test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL", "").strip() or None
