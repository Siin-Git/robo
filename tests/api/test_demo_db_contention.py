"""Slow hosted requests must not break the demo's atomic slot reservation."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api import dependencies


def test_demo_request_waits_for_busy_database(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("APP_PROFILE", "local")
    engine = create_engine(f"sqlite:///{tmp_path / 'busy.db'}",
                           connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(dependencies, "get_session_factory", lambda: factory)
    started = Event()

    def request():
        generator = dependencies.get_db()
        started.set()
        session = next(generator)
        value = session.connection().exec_driver_sql("SELECT 1").scalar()
        with pytest.raises(StopIteration):
            next(generator)
        return value

    with engine.connect() as holder, ThreadPoolExecutor(max_workers=1) as pool:
        holder.exec_driver_sql("BEGIN IMMEDIATE")
        future = pool.submit(request)
        assert started.wait(2)
        try:
            # Exceed the old five-second timeout while holding a separate
            # connection's write lock, then prove the waiting request recovers.
            with pytest.raises(TimeoutError):
                future.result(timeout=5.3)
        finally:
            holder.rollback()
        assert future.result(timeout=3) == 1
    engine.dispose()
