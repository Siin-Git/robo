"""Shared starts using two disposable databases and synthetic prices only."""
from datetime import date, datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
from contextlib import closing
from uuid import uuid4
import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
import sqlite3

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import User, Theme, PriceDaily
from src.db.models.demo_cohort import DemoCohort, DemoSlot
from src.db.models.operational import ForwardState
from src.api.services import auth_service, participant_service, onboarding_service, _common as C
from src.api.services.frontier_service import get_frontier
from src.forward import competition as gate
from src.forward.config import load_forward_config
from src.forward.execution import create_orders, execute_pending
from src.forward.ledger import valuate
from src.forward.prices import CORE_IDS
from src.forward.run_daily import _execute_daily
from src.forward.accounts import versions_from_cfg


@pytest.fixture(params=["sqlite", "postgres"])
def build(request, tmp_path, monkeypatch):
    pg_urls = [os.environ.get(k) for k in ("TEST_AUTH_DATABASE_URL", "TEST_DESIGN_DATABASE_URL")]
    if request.param == "postgres" and not all(pg_urls):
        pytest.skip("isolated PostgreSQL test database URLs not configured")
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("CAPSTONE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORWARD_EXECUTOR", "actions")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("TZ", "Asia/Seoul")
    monkeypatch.delenv("CAPSTONE_MARKET_COMPARISON", raising=False)
    monkeypatch.setattr(C, "now_utc", lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    clock = {"now": datetime(2026, 10, 3, tzinfo=gate.KST), "asof": "2026-10-02"}
    monkeypatch.setattr(gate, "now_kst", lambda: clock["now"])
    ids = [*CORE_IDS, "theme:ai"]
    monkeypatch.setattr("src.forward.prices.refresh_live", lambda *a: {
        "asof": clock["asof"], "new_points": 0, "stale": []})
    covariance = pd.DataFrame(np.eye(len(ids)) * .01, index=ids, columns=ids)
    monkeypatch.setattr("src.forward.run_daily.load_or_build_cov", lambda *a: (covariance, {}))
    engines = []
    connections = []
    schemas = []

    def setup(number=2):
        monkeypatch.setattr("src.local.capstone.COHORT_SIZE", number)
        if request.param == "postgres":
            scoped = []
            for url in pg_urls:
                schema = "shared_start_" + uuid4().hex
                admin = create_engine(url)
                with admin.begin() as conn:
                    conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                schemas.append((admin, schema))
                parsed = make_url(url)
                options = parsed.query.get("options", "") + f" -c search_path={schema}"
                rendered = urlsplit(parsed.update_query_dict({"options": options}).render_as_string(hide_password=False))
                # libpq URLs use percent-encoding, not form-style '+' spaces.
                # Preserve all original options while isolating the test schema.
                scoped.append(urlunsplit(rendered._replace(query=urlencode(parse_qsl(rendered.query), quote_via=quote))))
            monkeypatch.setenv("DATABASE_BACKEND", "postgres")
            monkeypatch.setenv("DATABASE_URL", scoped[0])
            monkeypatch.setenv("CAPSTONE_DESIGN_DATABASE_URL", scoped[1])
            auth_engine, operating_engine = [create_engine(url) for url in scoped]
        else:
            auth_engine = create_engine(f"sqlite:///{tmp_path / 'capstone_demo.db'}")
            operating_engine = create_engine(f"sqlite:///{tmp_path / 'portfolio_design.db'}")
        engines.extend([auth_engine, operating_engine])
        for engine in engines:
            Base.metadata.create_all(engine)
        auth = sessionmaker(bind=auth_engine)
        operation = sessionmaker(bind=operating_engine)
        users = []
        with auth() as db:
            db.add(DemoCohort(cohort_id="shared-test", prepared_count=0, created_at=C.now_utc()))
            db.add(ForwardState(key="demo_active_cohort", value="shared-test", updated_at=C.now_utc()))
            for index in range(number):
                user = auth_service.register(db, f"participant-{index}@example.com", "disposable-test-only-123", f"Test {index}")
                users.append(user)
                db.add(DemoSlot(slot_id=f"slot-{index}", cohort_id="shared-test", slot_number=index + 1,
                    invite_hash=sha256(str(index).encode()).hexdigest(), email_normalized=user["email"],
                    user_id=user["user_id"], draft_json={}))
            db.commit()
        with operation() as db:
            db.add(Theme(theme_id="ai", display_name="AI", theme_type="theme", ticker="AIQ",
                market="US", currency="USD", active=True, universe_version="THEME_UNIVERSE_V0.1"))
            for user in users:
                participant_service.create(db, "Test", participant_id=user["participant_id"])
                db.add(User(user_id=user["user_id"], participant_id=user["participant_id"],
                    email=user["email"], email_normalized=user["email"], password_hash="!reference-only",
                    role="user", status="disabled", created_at=C.now_utc(), updated_at=C.now_utc()))
            for asset in ids:
                db.add(PriceDaily(asset_id=asset, date=date(2026, 10, 2), price=100, source="SYNTHETIC_TEST"))
            db.commit()
        if request.param == "postgres":
            from src.forward.db import connect
            reopen = lambda: connect(None)  # Exact production/Actions design-DB routing.
        else:
            reopen = lambda: sqlite3.connect(tmp_path / "portfolio_design.db")
        con = reopen()
        con.row_factory = sqlite3.Row
        connections.append(con)
        cfg = load_forward_config()

        def confirm(index, reason="disposable competition test"):
            user = users[index]
            with operation() as db:
                result = onboarding_service.complete(db, user["user_id"], user["participant_id"],
                    get_frontier()["benchmark_frontier_id"], ["ai"], reason)
                db.commit()
            with auth() as db:
                db.get(DemoSlot, f"slot-{index}").confirmed_at = C.now_utc()
                db.commit()
            return result

        def prices(day):
            for asset in ids:
                con.execute("INSERT INTO prices_daily VALUES (?,?,?,?)", (asset, day, 101, "SYNTHETIC_TEST"))
            con.commit()
            clock["asof"] = day

        return SimpleNamespace(con=con, auth=auth, operation=operation, users=users,
            confirm=confirm, prices=prices, clock=clock, cfg=cfg, directory=tmp_path, reopen=reopen)

    yield setup
    for con in connections:
        con.close()
    for engine in engines:
        engine.dispose()
    for admin, schema in schemas:
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def ledger_counts(con):
    return [con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("trades", "holdings_daily", "nav_daily")]


@pytest.mark.parametrize("number", [2, 15])
def test_shared_start_blocks_early_users_and_preserves_pending_then_runs(build, number):
    x = build(number)
    x.confirm(0)
    # Existing initial order from the old implementation: retain its exact row.
    aid = f"A-{x.users[0]['participant_id']}-PERSONAL"
    decision = x.con.execute("SELECT weights_json FROM portfolio_decisions WHERE account_id=?", (aid,)).fetchone()
    import json
    target = json.loads(decision[0])["us_equity"]
    x.con.execute("INSERT INTO orders VALUES ('OLD',?,'us_equity','buy',?,'2026-10-01','2026-10-02','pending','2026-10-01')", (aid, target))
    x.con.commit()
    old = tuple(x.con.execute("SELECT * FROM orders WHERE order_id='OLD'").fetchone())
    from src.forward.frozen import load_frozen_benchmark
    from src.forward.config import resolve
    core_weight = load_frozen_benchmark(resolve(x.cfg["frozen_dir"]))[0]["us_equity"]
    core_account = f"A-{x.users[0]['participant_id']}-CORE"
    x.con.execute("INSERT INTO orders VALUES ('OLD_CORE',?,'us_equity','buy',?,'2026-10-01','2026-10-02','pending','2026-10-01')", (core_account, core_weight))
    x.con.commit()
    code, stats = _execute_daily(x.con, x.cfg, "2026-10-03")
    assert code == 0 and stats["reason"] == "PARTICIPANTS_NOT_READY"
    assert stats["ready"] == 1 and ledger_counts(x.con) == [0, 0, 0]
    assert x.con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2
    with pytest.raises(gate.StartError, match="PARTICIPANTS_NOT_READY"):
        gate.schedule_start(x.con, "2026-10-07")
    # Direct calls also fail closed; bypassing the daily wrapper cannot trade.
    assert create_orders(x.con, aid, {"us_equity": 1}, "2026-10-03", "2026-10-03", "V") == []
    assert execute_pending(x.con, aid, "2026-10-09", 5, "V") == []
    assert valuate(x.con, aid, "2026-10-09", versions_from_cfg(x.cfg), 1e8)["status"] == "NAV_INCOMPLETE"
    for index in range(1, number):
        x.confirm(index)
    assert gate.policy(x.con)["reason"] == "START_NOT_SCHEDULED"
    gate.schedule_start(x.con, "2026-10-07")
    assert gate.schedule_start(x.con, "2026-10-07")["start_date"] == "2026-10-07"
    assert all(len(r[0]) <= 256 for r in x.con.execute("SELECT value FROM forward_state"))
    x.prices("2026-10-07")  # Even future fixture prices and a future job date cannot bypass real KST time.
    code, stats = _execute_daily(x.con, x.cfg, "2026-10-09")
    assert code == 0 and stats["reason"] == "AWAITING_T0"
    assert tuple(x.con.execute("SELECT * FROM orders WHERE order_id='OLD'").fetchone()) == old
    assert ledger_counts(x.con) == [0, 0, 0]
    x.clock["now"] = datetime(2026, 10, 7, tzinfo=gate.KST)
    assert gate.policy(x.con)["status"] == "STARTED"
    code, stats = _execute_daily(x.con, x.cfg, "2026-10-07")
    assert code == 0 and stats["status"] == "PASS"
    assert x.con.execute("SELECT COUNT(DISTINCT account_id) FROM trades").fetchone()[0] == 2 * number
    assert x.con.execute("SELECT MIN(execution_at) FROM trades").fetchone()[0] == "2026-10-07"
    assert tuple(x.con.execute("SELECT MIN(date) first,MAX(date) last,COUNT(*) n FROM nav_daily").fetchone()) == ("2026-10-07", "2026-10-07", 2 * number)
    assert x.con.execute("SELECT COUNT(*) FROM orders WHERE account_id=? AND asset_id='us_equity'", (aid,)).fetchone()[0] == 1
    assert x.con.execute("SELECT COUNT(*) FROM orders WHERE account_id=? AND asset_id='us_equity'", (core_account,)).fetchone()[0] == 1
    assert gate.schedule_start(x.con, "2026-10-07")["start_date"] == "2026-10-07"
    counts = ledger_counts(x.con)
    _execute_daily(x.con, x.cfg, "2026-10-07")
    assert ledger_counts(x.con) == counts
    for nav in x.con.execute("SELECT * FROM nav_daily"):
        held = x.con.execute("SELECT SUM(market_value) FROM holdings_daily WHERE account_id=? AND date=?", (nav["account_id"], nav["date"])).fetchone()[0]
        assert nav["nav"] == pytest.approx(held + nav["cash_balance"])
    with closing(x.reopen()) as reopened:
        reopened.row_factory = sqlite3.Row
        assert gate.policy(reopened)["start_date"] == "2026-10-07"
        assert gate.policy(reopened)["status"] == "STARTED"


def test_schedule_refuses_past_or_too_early_date_and_cannot_overwrite(build):
    x = build()
    for i in range(2):
        x.confirm(i)
    with pytest.raises(gate.StartError, match="PAST_T0_FORBIDDEN"):
        gate.schedule_start(x.con, "2026-10-02")
    x.clock["now"] = datetime(2026, 9, 30, tzinfo=gate.KST)
    with pytest.raises(gate.StartError, match="T0_BEFORE_DECISION_EFFECTIVE_DATE"):
        gate.schedule_start(x.con, "2026-10-01")
    gate.schedule_start(x.con, "2026-10-07")
    with pytest.raises(gate.StartError, match="START_ALREADY_SCHEDULED"):
        gate.schedule_start(x.con, "2026-10-08")


def test_conflicting_pending_order_is_retained_and_schedule_refused(build):
    x = build()
    for i in range(2):
        x.confirm(i)
    aid = f"A-{x.users[0]['participant_id']}-PERSONAL"
    x.con.execute("INSERT INTO orders VALUES ('CONFLICT',?,'us_equity','buy',.99,'2026-10-01','2026-10-02','pending','2026-10-01')", (aid,))
    x.con.commit()
    with pytest.raises(gate.StartError, match="PENDING_INITIAL_ORDER_CONFLICT"):
        gate.schedule_start(x.con, "2026-10-07")
    assert x.con.execute("SELECT status FROM orders WHERE order_id='CONFLICT'").fetchone()[0] == "pending"
    assert gate.saved_start(x.con) is None and ledger_counts(x.con) == [0, 0, 0]


def test_auth_failure_is_fail_closed_without_secret_in_result(build, monkeypatch):
    x = build()
    monkeypatch.setattr(gate, "read_cohort", lambda: (_ for _ in ()).throw(gate.StartError("COHORT_READ_FAILED")))
    _, stats = _execute_daily(x.con, x.cfg, "2026-10-03")
    assert stats["reason"] == "COHORT_READ_FAILED"
    assert ledger_counts(x.con) == [0, 0, 0]


def test_schedule_refuses_unequal_capital_without_changing_existing_amounts(build):
    x = build()
    for i in range(2):
        x.confirm(i)
    aid = f"A-{x.users[1]['participant_id']}-PERSONAL"
    x.con.execute("UPDATE accounts SET initial_capital_krw=50000000 WHERE account_id=?", (aid,))
    x.con.commit()
    with pytest.raises(gate.StartError, match="INITIAL_CAPITAL_MISMATCH"):
        gate.schedule_start(x.con, "2026-10-07")
    assert gate.saved_start(x.con) is None
    assert x.con.execute("SELECT initial_capital_krw FROM accounts WHERE account_id=?", (aid,)).fetchone()[0] == 50000000
    assert ledger_counts(x.con) == [0, 0, 0]


def test_roster_change_after_scheduling_stops_everyone(build):
    x = build()
    for i in range(2):
        x.confirm(i)
    gate.schedule_start(x.con, "2026-10-07")
    with x.auth() as db:
        db.get(User, x.users[1]["user_id"]).status = "disabled"
        db.commit()
    x.clock["now"] = datetime(2026, 10, 7, tzinfo=gate.KST)
    x.prices("2026-10-07")
    _, stats = _execute_daily(x.con, x.cfg, "2026-10-07")
    assert stats["reason"] == "PARTICIPANTS_NOT_READY"
    assert ledger_counts(x.con) == [0, 0, 0]


def test_actions_cli_waits_then_starts_only_with_post_t0_prices(build, monkeypatch):
    x = build()
    from src.forward.run_daily import main
    monkeypatch.setattr("src.forward.runtime.kst_today", lambda: x.clock["now"].date())
    monkeypatch.setattr("src.forward.market_hours.now_kst", lambda: x.clock["now"])
    x.clock["now"] = datetime(2026, 10, 3, 7, 30, tzinfo=gate.KST)
    x.confirm(0)
    assert main([]) == 0
    assert ledger_counts(x.con) == [0, 0, 0]
    x.confirm(1)
    gate.schedule_start(x.con, "2026-10-07")
    assert main([]) == 0  # Same slot can retry after its gate wait.
    assert ledger_counts(x.con) == [0, 0, 0]
    x.clock["now"] = datetime(2026, 10, 7, 7, 30, tzinfo=gate.KST)
    assert main([]) == 0  # STARTED permits orders, but old prices cannot fill them.
    assert ledger_counts(x.con) == [0, 0, 0]
    assert x.con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] > 0
    x.prices("2026-10-07")
    x.clock["now"] = datetime(2026, 10, 8, 7, 30, tzinfo=gate.KST)
    assert main([]) == 0
    counts = ledger_counts(x.con)
    assert all(n > 0 for n in counts)
    assert x.con.execute("SELECT MIN(execution_at) FROM trades").fetchone()[0] == "2026-10-07"
    assert main([]) == 0 and ledger_counts(x.con) == counts


def test_wait_job_remains_retryable_and_lock_and_success_still_deduplicate(build):
    x = build()
    from src.forward.job_cli import enter_job, finish_job
    from src.forward.jobs import complete_job
    ctx = {"scheduled_for": "2026-10-07", "github_run_id": "test", "dry_run": False, "jobs_db_url": None}
    path = x.directory / "portfolio_design.db"
    first, decision = enter_job(path, "daily", ctx)
    assert decision == "run"
    assert enter_job(path, "daily", ctx)[1] == "locked"
    finish_job(path, first, decision, 0, {"status": "COMPETITION_WAIT", "reason": "AWAITING_T0"}, ctx)
    second, decision = enter_job(path, "daily", ctx)
    assert decision == "run"
    complete_job(None, second, {"status": "PASS"}, sqlite_path=path)
    assert enter_job(path, "daily", ctx)[1] == "skipped"


def test_armed_initial_decision_survives_redesign_and_later_order_rules_stay_intact(build, monkeypatch):
    x = build()
    for i in range(2):
        x.confirm(i)
    schedule = gate.schedule_start(x.con, "2026-10-07")
    original = schedule["members"][0]
    aid = original["personal_account_id"]
    # A later version with a future effective date cannot replace the armed
    # initial snapshot or delay its associated CORE account.
    monkeypatch.setattr(C, "now_utc", lambda: datetime(2026, 10, 10, tzinfo=timezone.utc))
    x.confirm(0, reason="new revision after shared start was armed")
    from src.forward.decision_policy import latest_decision
    revision = latest_decision(x.con, aid)
    assert revision["decision_id"] != original["decision_id"]
    x.clock["now"] = datetime(2026, 10, 7, tzinfo=gate.KST)
    x.prices("2026-10-07")
    assert _execute_daily(x.con, x.cfg, "2026-10-07")[0] == 0
    assert x.con.execute("SELECT COUNT(DISTINCT account_id) FROM trades").fetchone()[0] == 4
    assert x.con.execute("SELECT 1 FROM events WHERE event_type=? AND account_id=?",
                         ("DECISION_ORDER:" + original["decision_id"], aid)).fetchone()
    assert not x.con.execute("SELECT 1 FROM events WHERE event_type=? AND account_id=?",
                            ("DECISION_ORDER:" + revision["decision_id"], aid)).fetchone()
    assert x.con.execute("SELECT COUNT(*) FROM portfolio_decisions WHERE account_id=?", (aid,)).fetchone()[0] == 2
    # Cross-date pending reuse is limited to initial orders. After the first
    # fills, the original per-effective-date deduplication remains unchanged.
    x.con.execute("INSERT INTO orders VALUES ('LATER',?,'us_equity','buy',.2,'2026-10-07','2026-10-08','pending','2026-10-07')", (aid,))
    x.con.commit()
    assert len(create_orders(x.con, aid, {"us_equity": .3}, "2026-10-07", "2026-10-09", "V", baseline={})) == 1


def test_existing_trade_is_not_deleted_and_cannot_be_valued_before_start(build):
    x = build()
    for i in range(2):
        x.confirm(i)
    aid = f"A-{x.users[0]['participant_id']}-PERSONAL"
    x.con.execute("INSERT INTO orders VALUES ('OLD_FILL',?,'us_equity','buy',.1,'2026-10-01','2026-10-02','executed','2026-10-01')", (aid,))
    x.con.execute("INSERT INTO trades VALUES ('OLD_TRADE','OLD_FILL',?,'us_equity','2026-10-02',100,1,100,0,100)", (aid,))
    x.con.commit()
    assert valuate(x.con, aid, "2026-10-02", versions_from_cfg(x.cfg), 1e8)["status"] == "NAV_INCOMPLETE"
    with pytest.raises(gate.StartError, match="EXISTING_OPERATING_HISTORY"):
        gate.schedule_start(x.con, "2026-10-07")
    assert ledger_counts(x.con) == [1, 0, 0]


def test_weekly_monthly_cannot_create_pre_start_orders(build, monkeypatch, tmp_path):
    x = build()
    x.confirm(0)
    from src.forward.run_weekly import _execute_weekly
    from src.forward.run_monthly import _execute_monthly
    monkeypatch.setattr("src.forward.run_monthly.rebuild_cov", lambda *a: (pd.DataFrame([[.01]], index=["us_equity"], columns=["us_equity"]), {}))
    from src.forward.config import resolve
    monkeypatch.setattr("src.forward.config.resolve", lambda p: tmp_path / "risk.npz" if str(p).startswith("outputs/forward/") else resolve(p))
    assert _execute_weekly(x.con, x.cfg, "2026-10-02")[1]["status"] == "COMPETITION_WAIT"
    assert _execute_monthly(x.con, x.cfg, "2026", "10", "2026-10-31", False)[1]["status"] == "COMPETITION_WAIT"
    assert x.con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0
    assert ledger_counts(x.con) == [0, 0, 0]
