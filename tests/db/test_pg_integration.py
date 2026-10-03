"""Live PostgreSQL integration tests. SKIPPED without TEST_DATABASE_URL.

When a server is available (docker-compose.yml, or TEST_DATABASE_URL set),
these exercise the real dialect: DDL, timestamptz, JSONB, FK enforcement,
and a fixture migration + parity round-trip.
"""
import os
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

URL = os.environ.get("TEST_DATABASE_URL", "").strip() or None
needs_pg = pytest.mark.skipif(URL is None, reason="TEST_DATABASE_URL not set")


@needs_pg
def test_pg_connect_and_revision():
    from sqlalchemy import create_engine, text
    eng = create_engine(URL)
    with eng.connect() as c:
        assert c.execute(text("SELECT 1")).scalar() == 1


@needs_pg
def test_pg_alembic_and_crud():
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, DATABASE_URL=URL, DATABASE_BACKEND="postgres")
    env.pop("CAPSTONE_DEMO", None)
    env.pop("CAPSTONE_DESIGN_DATABASE_URL", None)
    r = subprocess.run([sys.executable, "-m", "alembic", "-c", "alembic.ini",
                        "upgrade", "head"], cwd=root, env=env,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    from src.db.session import create_app_engine, session_factory
    from src.db.models import Event, NavDaily
    S = session_factory(create_app_engine(URL))
    from uuid import uuid4
    eid="E" + uuid4().hex[:14]
    with S() as s:
        ts = datetime(2026, 9, 12, 17, 18, 40, 780314, tzinfo=timezone.utc)
        s.add(Event(event_id=eid, event_type="X", participant_id=None,
                    account_id=None, timestamp=ts, payload_json={"b": 1},
                    model_version="CORE_V0.3"))
        s.commit()
        back = s.get(Event, eid)
        assert back.timestamp == ts and back.timestamp.tzinfo is not None
        assert back.payload_json == {"b": 1}
        s.add(NavDaily(account_id="MISSING", date=date(2026, 1, 1), nav=1,
                       nav_base100=100, daily_return=None, cumulative_return=0,
                       cash_balance=1, stale_price_flag=False, nav_status="OK",
                       benchmark_version="V", theme_universe_version="T",
                       risk_model_version="R", execution_rule_version="E"))
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            s.commit()
        s.rollback()
