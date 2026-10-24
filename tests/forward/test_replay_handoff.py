"""Disposable fixtures only; no production credentials or copied accounts."""
from datetime import datetime
import copy
import json

import pytest

from tests.forward.test_competition_start import build
from src.forward import competition as gate
from src.forward.handoff import snapshot, apply, digest
from src.forward.opening import opening
from src.forward.execution import holding_qty, create_orders, execute_pending, current_weights
from src.forward.ledger import cash_balance, valuate
from src.forward.accounts import versions_from_cfg
from src.forward.run_daily import _execute_daily
from scripts.replay_handoff import build_plan


def prepare(build):
    x = build(15)
    for i in range(15):
        x.confirm(i)
    x.prices("2026-10-05")
    # Explicit test provenance, confined to the disposable fixture databases.
    x.con.execute("UPDATE prices_daily SET source='ISOLATED_PRICE_TEST'")
    aid = f"A-{x.users[0]['participant_id']}-PERSONAL"
    x.con.execute("INSERT INTO orders VALUES ('OLD-HANDOFF',?,'us_equity','buy',0.5,'2026-10-01','2026-10-02','pending','2026-10-01')", (aid,))
    x.con.commit()
    x.clock["now"] = datetime(2026, 10, 6, tzinfo=gate.KST)
    source = snapshot(x.con, "2026-10-01", "2026-10-06", "2026-10-07")
    try:
        plan = build_plan(source)
    except Exception as error:
        pytest.fail(getattr(error, "stderr", str(error)))
    return x, plan


def test_atomic_handoff_idempotence_and_forward_balances(build, monkeypatch):
    x, plan = prepare(build)
    # Replaying the identical source must produce an identical reviewed checksum.
    assert digest(build_plan(plan["source"])) == digest(plan)
    aid = plan["source"]["members"][0]["personal_account_id"]
    value = plan["openings"][aid]
    original_decisions = [tuple(r) for r in x.con.execute("SELECT * FROM portfolio_decisions ORDER BY decision_id")]
    broken = copy.deepcopy(plan)
    broken["openings"][aid]["cash_balance"] += 100
    with pytest.raises(ValueError, match="IDENTITY"):
        apply(x.con, broken, digest(broken))
    # Inject failure after schedule writes: opening, cancellation and schedule roll back together.
    from src.forward import handoff
    real_log = handoff.log_event
    def fail(*args, **kwargs):
        if args[1] == "REPLAY_FORWARD_OPENING":
            raise RuntimeError("test interruption")
        return real_log(*args, **kwargs)
    monkeypatch.setattr(handoff, "log_event", fail)
    with pytest.raises(RuntimeError, match="test interruption"):
        apply(x.con, plan, digest(plan))
    assert gate.saved_start(x.con) is None
    assert not opening(x.con, aid)
    assert x.con.execute("SELECT status FROM orders WHERE order_id='OLD-HANDOFF'").fetchone()[0] == 'pending'
    monkeypatch.setattr(handoff, "log_event", real_log)
    receipt = apply(x.con, plan, digest(plan))
    assert receipt["openings"] == 30 and receipt["archives"] == 15
    assert apply(x.con, plan, digest(plan))["reused"]
    assert receipt["cancelled_pending"] == 1
    assert x.con.execute("SELECT status FROM orders WHERE order_id='OLD-HANDOFF'").fetchone()[0] == 'cancelled'
    from src.api.services.continuity_service import own
    member = plan["source"]["members"][0]
    with x.operation() as session:
        assert own(session, member["participant_id"], "wrong-owner") == {"available": False}
        report = own(session, member["participant_id"], member["user_id"])
        assert report["available"] and report["forward_observations"] == 0
        assert all(p["data_kind"] == "HISTORICAL_REPLAY" for p in report["series"])
    assert original_decisions == [tuple(r) for r in x.con.execute("SELECT * FROM portfolio_decisions ORDER BY decision_id")]
    assert x.con.execute("SELECT COUNT(*) FROM nav_daily").fetchone()[0] == 0
    assert holding_qty(x.con, aid, value["holdings"][0]["asset_id"], "2026-10-06") == 0
    assert gate.policy(x.con)["reason"] == "AWAITING_T0"
    x.prices("2026-10-07")
    x.con.execute("UPDATE prices_daily SET source='ISOLATED_PRICE_TEST'")
    x.con.commit()
    x.clock["now"] = datetime(2026, 10, 7, tzinfo=gate.KST)
    code, stats = _execute_daily(x.con, x.cfg, "2026-10-07", use_stored_prices=True)
    assert code == 0 and stats["status"] == "PASS" and stats["valuated"] == 30, stats
    assert x.con.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0  # no second initial buy
    assert x.con.execute("SELECT COUNT(*) FROM nav_daily").fetchone()[0] == 30
    row = x.con.execute("SELECT * FROM nav_daily WHERE account_id=?", (aid,)).fetchone()
    assert row["nav"] == pytest.approx(value["nav"])
    assert row["cash_balance"] == pytest.approx(value["cash_balance"])
    _execute_daily(x.con, x.cfg, "2026-10-07", use_stored_prices=True)
    assert x.con.execute("SELECT COUNT(*) FROM nav_daily").fetchone()[0] == 30
    with x.operation() as session:
        report = own(session, member["participant_id"], member["user_id"])
        assert report["forward_observations"] == 1
        assert report["series"][-1]["data_kind"] == 'FORWARD_SIMULATION'
        assert report["series"][-1]["personal_index"] == pytest.approx(report["series"][-2]["personal_index"])
    # Sell inherited positions, then buy again: cash/quantities must use opening + live fills.
    baseline = current_weights(x.con, aid, "2026-10-07")
    create_orders(x.con, aid, {"cash": 1}, "2026-10-07", "2026-10-07", "test", baseline=baseline)
    assert execute_pending(x.con, aid, "2026-10-07", 5, "test")
    assert all(abs(holding_qty(x.con, aid, p["asset_id"], "2026-10-07")) < 1e-6 for p in value["holdings"])
    balance = cash_balance(x.con, aid, "2026-10-07", 1e8)
    assert balance == pytest.approx(value["nav"] - sum(p["market_value"] for p in value["holdings"]) * .0005)
    result = valuate(x.con, aid, "2026-10-07", versions_from_cfg(x.cfg), 1e8)
    assert result["status"] == "OK" and result["nav"] == pytest.approx(balance)
    create_orders(x.con, aid, {"us_equity": 1}, "2026-10-07", "2026-10-07", "test", baseline={})
    assert execute_pending(x.con, aid, "2026-10-07", 5, "test")
    nav = valuate(x.con, aid, "2026-10-07", versions_from_cfg(x.cfg), 1e8)
    assert nav["nav"] == pytest.approx(balance / 1.0005)
    kinds = [json.loads(r[0])["data_kind"] for r in x.con.execute("SELECT payload_json FROM events WHERE event_type='NAV_CALCULATED'")]
    assert set(kinds) == {"FORWARD_SIMULATION"}


def test_handoff_refuses_changed_inputs_and_synthetic_prices(build):
    x, plan = prepare(build)
    x.con.execute("UPDATE prices_daily SET price=price+1 WHERE date='2026-10-05'")
    x.con.commit()
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        apply(x.con, plan, digest(plan))
    assert gate.saved_start(x.con) is None
    x.con.execute("UPDATE prices_daily SET source='SYNTHETIC_TEST'")
    x.con.commit()
    with pytest.raises(ValueError, match="UNVERIFIED_PRICE_SOURCE"):
        snapshot(x.con, "2026-10-01", "2026-10-06", "2026-10-07")
