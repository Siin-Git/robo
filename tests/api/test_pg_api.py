"""API-on-PostgreSQL integration. SKIPPED without TEST_DATABASE_URL."""
import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

URL = os.environ.get("TEST_DATABASE_URL", "").strip() or None
needs_pg = pytest.mark.skipif(URL is None, reason="TEST_DATABASE_URL not set")


@needs_pg
def test_api_flow_on_postgres():
    from src.api.dependencies import get_db
    from src.api.main import app
    from src.db.base import Base
    from src.db.models.theme import Theme

    engine = create_engine(URL)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)

    def override():
        s = factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    try:
        with factory() as s:
            s.query(Theme).delete()
            s.add(Theme(theme_id="ai", display_name="AI", theme_type="theme",
                        ticker="AIQ", market="US", currency="USD", active=True,
                        valid_from=date(2026, 1, 1), valid_to=None,
                        universe_version="THEME_UNIVERSE_V0.1", inactive_reason=None))
            s.commit()
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
            pid = c.post("/api/v1/participants",
                         json={"display_name": "PG User"}).json()["participant_id"]
            r = c.post(f"/api/v1/participants/{pid}/views",
                       json={"theme_ids": ["ai"], "reason": "pg"})
            assert r.status_code == 201, r.text
            assert r.json()["views"][0]["status"] == "new"
            assert c.get(f"/api/v1/portfolio/core").status_code == 200
    finally:
        app.dependency_overrides.clear()
        with factory() as s:
            for t in ("views", "events", "portfolio_targets", "accounts",
                      "participants", "counters"):
                s.execute(__import__("sqlalchemy").text(f'DELETE FROM "{t}"'))
            s.commit()
