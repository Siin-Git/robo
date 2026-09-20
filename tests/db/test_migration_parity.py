"""Migration + parity logic tests (SQLite destination stands in for PostgreSQL).

Same code paths, same type conversions, same comparisons — only the destination
dialect differs. Live-PostgreSQL execution is covered by test_pg_integration.py
(skipped without TEST_DATABASE_URL) plus the offline DDL render check.
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def source_db(tmp_path):
    """A fresh clone must not need somebody's private live database to test migration."""
    from datetime import date
    from src.db.base import Base
    from src.db.session import create_app_engine, session_factory
    from src.db.models.price import PriceDaily
    from src.db.models.nav import NavDaily
    from src.api.services.participant_service import create
    path = tmp_path / "source.db"
    engine = create_app_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with session_factory(engine)() as s:
        participant = create(s, "Migration fixture")
        # A cash-only opening ledger, independent of demo NAV display fixtures.
        s.add(NavDaily(account_id=f"A-{participant['participant_id']}-CORE",
            date=date(2026, 4, 1), nav=100000000, nav_base100=100, daily_return=0,
            cumulative_return=0, cash_balance=100000000, stale_price_flag=False,
            nav_status="OK", benchmark_version="CORE_V0.3", theme_universe_version="THEME_UNIVERSE_V0.1",
            risk_model_version="RISK_5Y_LW_FROZEN_V0", execution_rule_version="NEXT_AVAILABLE_CLOSE_V0"))
        s.add(PriceDaily(asset_id="us_equity", date=date(2026, 4, 1), price=100.12345, source="test"))
        s.commit()
    engine.dispose()
    return path


def run(cmd, env_extra=None, timeout=600):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    env.pop("TEST_DATABASE_URL", None)
    env.update(env_extra or {})
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)


def test_migration_dry_run_seeded_source(tmp_path, source_db):
    r = run([sys.executable, "scripts/migrate_sqlite_to_postgres.py",
             "--source", str(source_db), "--dest", f"sqlite:///{tmp_path}/never.db", "--dry-run"])
    assert r.returncode == 0, r.stderr
    assert "Ready to migrate" in r.stdout
    assert not (tmp_path / "never.db").exists()


def test_migrate_and_verify_seeded_source(tmp_path, source_db):
    dest = tmp_path / "mirror.db"
    r = run([sys.executable, "scripts/migrate_sqlite_to_postgres.py",
             "--source", str(source_db), "--dest", f"sqlite:///{dest}"])
    assert r.returncode == 0, r.stderr + r.stdout
    rep = json.loads((ROOT / "outputs" / "database" / "migration_report.json").read_text())
    assert rep["source_untouched"] is True
    assert rep["tables"]["prices_daily"]["match"] is True
    r2 = run([sys.executable, "scripts/verify_db_parity.py",
              "--source", str(source_db), "--dest", f"sqlite:///{dest}"])
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "PARITY: PASS" in r2.stdout


def test_migration_refuses_nonempty_dest(tmp_path, source_db):
    dest = tmp_path / "m.db"
    base = [sys.executable, "scripts/migrate_sqlite_to_postgres.py",
            "--source", str(source_db), "--dest", f"sqlite:///{dest}"]
    assert run(base).returncode == 0
    r = run(base)
    assert r.returncode != 0
    assert "not empty" in r.stdout


def test_migration_fails_on_orphans(tmp_path):
    src = tmp_path / "orphan.db"
    con = sqlite3.connect(src)
    con.execute("CREATE TABLE participants (participant_id TEXT PRIMARY KEY, display_name TEXT,"
                " status TEXT, join_date TEXT, leave_date TEXT, created_at TEXT, updated_at TEXT)")
    for t, cols in {
        "themes": "(theme_id TEXT PRIMARY KEY, display_name TEXT, theme_type TEXT, ticker TEXT,"
                  " market TEXT, currency TEXT, active INTEGER, valid_from TEXT, valid_to TEXT,"
                  " universe_version TEXT, inactive_reason TEXT)",
        "accounts": "(account_id TEXT PRIMARY KEY, participant_id TEXT, account_type TEXT,"
                    " shadow_name TEXT, benchmark_version TEXT, inception_date TEXT,"
                    " initial_capital_krw REAL, status TEXT, created_at TEXT)",
        "orders": "(order_id TEXT PRIMARY KEY, account_id TEXT, asset_id TEXT, side TEXT,"
                  " target_weight REAL, submitted_at TEXT, effective_at TEXT, status TEXT,"
                  " created_at TEXT)",
    }.items():
        con.execute(f"CREATE TABLE {t} {cols}")
    for t in ["views", "portfolio_targets", "holdings_daily", "nav_daily",
              "performance_daily", "prices_daily", "events", "model_versions",
              "counters", "forward_state"]:
        con.execute(f"CREATE TABLE {t} (dummy TEXT)")
    con.execute("INSERT INTO orders VALUES ('O1','A-missing','x','buy',0.5,"
                "'2026-01-01T00:00:00+00:00','2026-01-02','pending','2026-01-01T00:00:00+00:00')")
    con.execute("CREATE TABLE trades (trade_id TEXT PRIMARY KEY, order_id TEXT,"
                " account_id TEXT, asset_id TEXT, execution_at TEXT, execution_price REAL,"
                " quantity REAL, gross_value REAL, transaction_cost REAL, net_value REAL)")
    con.execute("INSERT INTO trades VALUES ('T1','O1','A-missing','x','2026-01-02',1,1,1,0,1)")
    con.commit()
    con.close()
    r = run([sys.executable, "scripts/migrate_sqlite_to_postgres.py",
             "--source", str(src), "--dest", f"sqlite:///{tmp_path}/d.db"])
    assert r.returncode != 0
    assert "orphan" in r.stdout.lower()


def test_alembic_upgrade_and_downgrade(tmp_path, monkeypatch):
    db = tmp_path / "al.db"
    env = {"DATABASE_BACKEND": "sqlite", "SQLITE_PATH": str(db), "DATABASE_URL": ""}
    r = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"], env)
    assert r.returncode == 0, r.stderr
    con = sqlite3.connect(db)
    tables = {x[0] for x in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"participants", "trades", "nav_daily", "events"} <= tables
    con.close()
    r2 = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade", "base"], env)
    assert r2.returncode == 0, r2.stderr
    con = sqlite3.connect(db)
    tables = {x[0] for x in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "participants" not in tables
    con.close()


def test_offline_postgres_ddl_renders():
    env = {"DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/robo_advisor"}
    r = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head", "--sql"], env)
    assert r.returncode == 0, r.stderr
    for token in ("TIMESTAMP WITH TIME ZONE", "JSONB", "NUMERIC(24, 8)", "ON DELETE RESTRICT",
                  "CREATE INDEX ix_trades_account_execution"):
        assert token in r.stdout, token
