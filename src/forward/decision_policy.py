"""Use confirmed composition in all batches; preserve unmanaged legacy behavior."""
import json
import os

def latest_decision(con, account_id, asof=None):
    # Legacy stdlib forward fixtures predate the table. Check before querying;
    # a missing-table query would abort a PostgreSQL transaction.
    if hasattr(con, "_con"):
        if con.execute("SELECT to_regclass('portfolio_decisions') t").fetchone()["t"] is None:
            return None
    elif not con.execute("SELECT name FROM sqlite_master WHERE name='portfolio_decisions'").fetchone():
        return None
    rows = con.execute("SELECT * FROM portfolio_decisions WHERE account_id = ? ORDER BY version DESC", (account_id,)).fetchall()
    for row in rows:
        if asof is None or str(row["effective_date"])[:10] <= asof:
            return dict(row)
    return None

def weights(decision):
    v = decision["weights_json"]
    return json.loads(v) if isinstance(v, str) else v

def rebalance_frequency(con, account_id, asof, fallback='monthly'):
    """Use only the calendar-effective confirmation; preserve unmanaged accounts."""
    from .rebalance_schedule import normalize_frequency
    decision = latest_decision(con, account_id, asof)
    provenance = (decision or {}).get('provenance_json') or {}
    if isinstance(provenance, str):
        provenance = json.loads(provenance)
    return normalize_frequency(provenance.get('rebalance_frequency') or fallback)

def awaiting_confirmation(con, account):
    if os.environ.get("CAPSTONE_DEMO") != "1" or os.environ.get("APP_PROFILE") != "local" or not account.get("participant_id"):
        return False
    personal = con.execute("SELECT account_id FROM accounts WHERE participant_id = ? AND account_type='personal'", (account["participant_id"],)).fetchone()
    if not personal:
        return False
    if latest_decision(con, personal["account_id"]):
        return False
    # Existing saved base selections prove a legacy confirmation but do not
    # supply original personal estimates. No snapshot is manufactured for them.
    return not con.execute("SELECT selection_id FROM base_portfolio_selections WHERE participant_id = ? AND status='active'", (account["participant_id"],)).fetchone()
