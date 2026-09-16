"""Simulated execution: target-weight orders filled at next available close.

Look-ahead rule: an order may only consume prices on/after its effective_at
date (effective_at itself is already a future session at submission time).
Costs are deducted from cash on every trade.
"""
from __future__ import annotations

import sqlite3

from .db import log_event, next_id
from .prices import next_available_close, price_on_or_before


def current_weights(con: sqlite3.Connection, account_id: str, asof: str) -> dict:
    """Latest holdings weights (drifted reality) if holdings exist, else latest targets."""
    h = con.execute("SELECT asset_id, weight FROM holdings_daily WHERE account_id = ?"
                    " AND date <= ? AND date = (SELECT MAX(date) FROM holdings_daily"
                    " WHERE account_id = ? AND date <= ?)",
                    (account_id, asof, account_id, asof)).fetchall()
    if h:
        return {r["asset_id"]: float(r["weight"]) for r in h}
    row = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                      " AND effective_date <= ? ORDER BY effective_date DESC LIMIT 1",
                      (account_id, asof)).fetchone()
    if row is None:
        return {}
    import json
    return json.loads(row["weights_json"])


def holding_qty(con: sqlite3.Connection, account_id: str, asset_id: str, asof: str) -> float:
    row = con.execute("SELECT COALESCE(SUM(quantity), 0) AS q FROM trades WHERE account_id = ?"
                      " AND asset_id = ? AND execution_at <= ?",
                      (account_id, asset_id, asof)).fetchone()
    return float(row["q"])


def create_orders(con: sqlite3.Connection, account_id: str, target_w: dict,
                  submitted_at: str, effective_at: str, model_version: str,
                  participant_id=None, kind: str = "REBALANCE",
                  baseline: dict | None = None) -> list[str]:
    """Create target-weight orders for assets whose weight changed vs baseline.

    baseline None = build from zero (inception). Weekly active batches pass the
    previous target (change-only orders, no drift churn); monthly/core passes
    holdings-based weights (full drift correction).
    """
    cur = dict(baseline) if baseline is not None else {}
    oids = []
    for asset, tw in sorted(target_w.items()):
        if asset == "cash":
            continue
        cw = cur.get(asset, 0.0)
        if abs(tw - cw) < 1e-9:
            continue
        oid = next_id(con, "O")
        con.execute("INSERT INTO orders (order_id, account_id, asset_id, side, target_weight,"
                    " submitted_at, effective_at, status, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                    (oid, account_id, asset, "buy" if tw > cw else "sell",
                     float(tw), submitted_at, effective_at, submitted_at))
        log_event(con, "ORDER_CREATED", model_version, participant_id, account_id,
                  {"order_id": oid, "asset": asset, "target_weight": float(tw), "kind": kind})
        oids.append(oid)
    con.commit()
    return oids


def nav_before_trades(con: sqlite3.Connection, account_id: str, exec_date: str,
                      initial_capital: float) -> tuple[float, dict, float]:
    """Holdings value + cash just before trades on exec_date. Returns (nav, qty, cash)."""
    assets = [r["asset_id"] for r in con.execute(
        "SELECT DISTINCT asset_id FROM trades WHERE account_id = ?", (account_id,)).fetchall()]
    qty, mv = {}, 0.0
    for a in assets:
        q = holding_qty(con, account_id, a, exec_date)
        px, _, _ = price_on_or_before(con, a, exec_date)
        if px is None:
            raise RuntimeError(f"execution price missing for {a} on {exec_date}")
        qty[a] = q
        mv += q * px
    cash = initial_capital
    for r in con.execute("SELECT quantity, gross_value, transaction_cost FROM trades"
                         " WHERE account_id = ? AND execution_at <= ?", (account_id, exec_date)).fetchall():
        if r["quantity"] > 0:
            cash -= r["gross_value"] + r["transaction_cost"]
        else:
            cash += r["gross_value"] - r["transaction_cost"]
    return mv + cash, qty, cash


def execute_pending(con: sqlite3.Connection, account_id: str, asof_date: str,
                    cost_bps: float, model_version: str,
                    participant_id=None) -> list[str]:
    """Execute all pending orders whose next available close is <= asof_date."""
    init = con.execute("SELECT initial_capital_krw FROM accounts WHERE account_id = ?",
                       (account_id,)).fetchone()
    capital = float(init["initial_capital_krw"])
    pending = [dict(r) for r in con.execute(
        "SELECT * FROM orders WHERE account_id = ? AND status = 'pending'"
        " ORDER BY effective_at, asset_id", (account_id,)).fetchall()]
    # group by execution date across assets
    plan: dict[str, list[dict]] = {}
    inception_floor = None
    try:
        from .state import get_state as _get_state
        inception_floor = _get_state(con, "forward_test_inception_at")
        inception_floor = inception_floor[:10] if inception_floor else None
    except Exception:
        inception_floor = None
    for o in pending:
        d = next_available_close(con, o["asset_id"], o["effective_at"])
        if d is None or d < o["effective_at"] or d > asof_date:
            continue
        if inception_floor is not None and d < inception_floor:
            # Retroactive execution is forbidden: leave pending, audit it.
            from .db import log_event as _le
            _le(con, "RETROACTIVE_EXECUTION_BLOCKED", model_version, participant_id,
                o["account_id"], {"order_id": o["order_id"], "blocked_date": d,
                                  "inception": inception_floor})
            continue
        plan.setdefault(d, []).append(o)
    tids = []
    for exec_date in sorted(plan):
        nav_pre, qty_now, _ = nav_before_trades(con, account_id, exec_date, capital)
        # target weights snapshot per order (target at order creation)
        tgts = {}
        for o in plan[exec_date]:
            tw = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id = ?"
                             " AND effective_date <= ? ORDER BY effective_date DESC LIMIT 1",
                             (account_id, o["effective_at"])).fetchone()
            import json
            tgts[o["order_id"]] = json.loads(tw["weights_json"]) if tw else {}
        # size sequentially in asset order; scale buys if cash would go negative
        pxmap = {}
        for o in plan[exec_date]:
            px, _, _ = price_on_or_before(con, o["asset_id"], exec_date)
            pxmap[o["order_id"]] = px
        # two-pass: compute raw deltas, then scale buys to fit cash
        raw = []
        for o in plan[exec_date]:
            tw = tgts[o["order_id"]].get(o["asset_id"], 0.0)
            target_qty = tw * nav_pre / pxmap[o["order_id"]]
            raw.append((o, target_qty - qty_now.get(o["asset_id"], 0.0)))
        cash_now = nav_before_trades(con, account_id, exec_date, capital)[2]
        # process sells first (free cash), then buys
        ordered = sorted(raw, key=lambda t: (t[0]["side"] == "buy", t[0]["asset_id"]))
        scale = 1.0
        for _ in range(5):
            need, have = 0.0, cash_now
            for o, dq in ordered:
                px = pxmap[o["order_id"]]
                q = dq * (scale if o["side"] == "buy" else 1.0)
                if o["side"] == "buy":
                    need += q * px * (1 + cost_bps / 1e4)
                else:
                    have += (-q) * px * (1 - cost_bps / 1e4)
            if need <= have + 1e-6:
                break
            scale *= (have / need) * 0.999
        else:
            raise RuntimeError("could not fit trades into cash")
        if scale < 1.0 - 1e-9:
            log_event(con, "CASH_SCALED", model_version, participant_id, account_id,
                      {"scale": scale, "exec_date": exec_date})
        for o, dq in ordered:
            px = pxmap[o["order_id"]]
            q = dq * (scale if o["side"] == "buy" else 1.0)
            if abs(q) < 1e-12:
                con.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?",
                            (o["order_id"],))
                continue
            gross = abs(q) * px
            cost = gross * cost_bps / 1e4
            tid = next_id(con, "T")
            net = gross + cost if q > 0 else -(gross - cost)
            con.execute("INSERT INTO trades (trade_id, order_id, account_id, asset_id,"
                        " execution_at, execution_price, quantity, gross_value,"
                        " transaction_cost, net_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (tid, o["order_id"], account_id, o["asset_id"], exec_date, px,
                         float(q), float(gross), float(cost), float(net)))
            con.execute("UPDATE orders SET status = 'executed' WHERE order_id = ?",
                        (o["order_id"],))
            log_event(con, "TRADE_EXECUTED", model_version, participant_id, account_id,
                      {"trade_id": tid, "order_id": o["order_id"], "asset": o["asset_id"],
                       "execution_at": exec_date, "price": px, "quantity": float(q),
                       "cost": float(cost)})
            tids.append(tid)
    con.commit()
    return tids
