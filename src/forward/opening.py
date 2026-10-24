"""Immutable opening balances inherited from an explicitly labelled replay.

These are positions, not live trades or NAV observations. Normal executions
are added only from the forward boundary onward; prior queries see no opening.
"""
import json

EVENT = "REPLAY_FORWARD_OPENING"


def opening(con, account_id, asof=None):
    rows = con.execute("SELECT payload_json FROM events WHERE event_type=? AND account_id=?",
                       (EVENT, account_id)).fetchall()
    if len(rows) > 1:
        raise RuntimeError("AMBIGUOUS_OPENING_BALANCE")
    if not rows:
        return None
    value = rows[0]["payload_json"]
    value = json.loads(value) if isinstance(value, str) else value
    if asof is not None and asof < value["forward_start"]:
        return None
    return value


def assets(con, account_id, asof):
    result = {r["asset_id"] for r in con.execute(
        "SELECT DISTINCT asset_id FROM trades WHERE account_id=? AND execution_at<=?", (account_id, asof))}
    inherited = opening(con, account_id, asof)
    if inherited:
        result.update(p["asset_id"] for p in inherited["holdings"])
    return sorted(result)


def cash(con, account_id, asof, initial_capital):
    inherited = opening(con, account_id, asof)
    balance = float(inherited["cash_balance"]) if inherited else initial_capital
    for row in con.execute("SELECT quantity,gross_value,transaction_cost,execution_at FROM trades WHERE account_id=? AND execution_at<=?",
                           (account_id, asof)):
        if inherited and row["execution_at"] < inherited["forward_start"]:
            raise RuntimeError("TRADE_BEFORE_OPENING")
        balance += (-float(row["gross_value"]) if row["quantity"] > 0 else float(row["gross_value"])) - float(row["transaction_cost"])
    return balance
