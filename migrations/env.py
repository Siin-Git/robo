"""Alembic environment: URL from DATABASE_URL (or sqlite fallback for offline use)."""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from src.db.base import Base  # noqa: E402
import src.db.models  # noqa: E402,F401

target_metadata = Base.metadata


def get_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    backend = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower()
    if backend == "sqlite":
        path = os.environ.get("SQLITE_PATH", str(Path.cwd() / "data" / "forward_test.db"))
        return f"sqlite:///{path}"
    raise ValueError("DATABASE_URL is not set for postgres backend")


def run_migrations_offline() -> None:
    context.configure(url=get_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
