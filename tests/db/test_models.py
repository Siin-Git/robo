"""DB layer tests: models, precision, timestamps, JSON, constraints.

Backend-portable (run on SQLite via type variants). PostgreSQL-specific live
behavior is covered by test_pg_integration.py (skipped without a server).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from src.db.base import Base
from src.db.models import Account, Event, NavDaily, Participant, Trade
from src.db.repositories.forward import EventRepository, NavRepository, TradeRepository
from src.db.session import create_app_engine, session_factory


@pytest.fixture()
def session(tmp_path):
    engine = create_app_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    S = session_factory(engine)
    with S() as s:
        yield s


def test_table_names_exact():
    assert set(Base.metadata.tables) == {
        "participants", "accounts", "themes", "views", "portfolio_targets",
        "orders", "trades", "holdings_daily", "nav_daily", "performance_daily",
        "prices_daily", "events", "model_versions", "counters", "forward_state",
        "users", "sessions", "scheduled_jobs", "base_portfolio_selections",
        "onboarding_drafts", "demo_cohorts", "demo_slots", "portfolio_decisions", "portfolio_choices"}


def test_required_columns():
    assert set(Base.metadata.tables["events"].columns.keys()) == {
        "event_id", "event_type", "participant_id", "account_id", "timestamp",
        "payload_json", "model_version"}
    assert set(Base.metadata.tables["nav_daily"].columns.keys()) == {
        "account_id", "date", "nav", "nav_base100", "daily_return",
        "cumulative_return", "cash_balance", "stale_price_flag", "nav_status",
        "benchmark_version", "theme_universe_version", "risk_model_version",
        "execution_rule_version"}


def test_weight_nav_precision_roundtrip(session):
    from decimal import Decimal
    session.add(Participant(participant_id="P001", display_name="A", status="active",
                            join_date=date(2026, 1, 1), leave_date=None,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc)))
    session.add(Account(account_id="A-1", participant_id="P001", account_type="core",
                        shadow_name=None, benchmark_version="CORE_V0.3",
                        inception_date=date(2026, 1, 1), initial_capital_krw=Decimal("100000000"),
                        status="active", created_at=datetime.now(timezone.utc)))
    session.add(NavDaily(account_id="A-1", date=date(2026, 1, 2), nav=Decimal("100000000.12345678"),
                         nav_base100=Decimal("100"), daily_return=None,
                         cumulative_return=Decimal("0"), cash_balance=Decimal("5000.25"),
                         stale_price_flag=False, nav_status="OK", benchmark_version="V",
                         theme_universe_version="T", risk_model_version="R",
                         execution_rule_version="E"))
    session.commit()
    nav = session.get(NavDaily, ("A-1", date(2026, 1, 2)))
    assert nav.nav == Decimal("100000000.12345678")
    assert nav.cash_balance == Decimal("5000.25")


def test_timezone_wallclock_roundtrip(session):
    ts = datetime(2026, 9, 12, 17, 18, 40, 780314, tzinfo=timezone.utc)
    session.add(Event(event_id="E000001", event_type="X", participant_id=None,
                      account_id=None, timestamp=ts, payload_json={"b": 1, "a": [1, 2]},
                      model_version="CORE_V0.3"))
    session.commit()
    back = session.get(Event, "E000001")
    assert back.timestamp.replace(tzinfo=None) == ts.replace(tzinfo=None)
    assert back.payload_json == {"a": [1, 2], "b": 1}  # JSON semantic match


def test_fk_orphan_insert_fails(session):
    session.add(Trade(trade_id="T1", order_id="O-missing", account_id="A-missing",
                      asset_id="x", execution_at=date(2026, 1, 1), execution_price=1,
                      quantity=1, gross_value=1, transaction_cost=0, net_value=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_nav_duplicate_pk_fails(session):
    session.add(Participant(participant_id="P9", display_name="A", status="active",
                            join_date=date(2026, 1, 1), leave_date=None,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc)))
    session.add(Account(account_id="A-1", participant_id="P9", account_type="core",
                        shadow_name=None, benchmark_version="V",
                        inception_date=date(2026, 1, 1), initial_capital_krw=100,
                        status="active", created_at=datetime.now(timezone.utc)))
    session.commit()
    kw = dict(account_id="A-1", date=date(2026, 1, 2), nav=1, nav_base100=100,
              daily_return=None, cumulative_return=0, cash_balance=1,
              stale_price_flag=False, nav_status="OK", benchmark_version="V",
              theme_universe_version="T", risk_model_version="R", execution_rule_version="E")
    session.add(NavDaily(**kw))
    session.commit()
    session.add(NavDaily(**kw))
    with pytest.raises(IntegrityError):
        session.commit()


def test_append_only_repositories_expose_no_mutation():
    assert hasattr(TradeRepository, "record")
    assert hasattr(EventRepository, "append")
    assert hasattr(NavRepository, "record")
    for repo in (TradeRepository, EventRepository, NavRepository):
        assert not hasattr(repo, "delete")
        assert not hasattr(repo, "update")
