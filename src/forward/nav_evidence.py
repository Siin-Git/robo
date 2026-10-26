"""Read-only checks for observed forward NAV. Never repairs or infers provenance."""
import json
import math


def payload(value):
    return value if isinstance(value, dict) else json.loads(value or '{}')


def normal_forward_nav(con, account_id, day, benchmark_version):
    row = con.execute('SELECT * FROM nav_daily WHERE account_id=? AND date=?',
                      (account_id, day)).fetchone()
    if not row:
        return None
    nav = float(row['nav'])
    cash = float(row['cash_balance'])
    if (row['nav_status'] != 'OK' or row['stale_price_flag'] or not math.isfinite(nav)
            or nav <= 0 or not math.isfinite(cash) or row['benchmark_version'] != benchmark_version):
        return None
    holdings = con.execute('SELECT COALESCE(SUM(market_value),0) v FROM holdings_daily WHERE account_id=? AND date=?',
                           (account_id, day)).fetchone()['v']
    if not math.isclose(nav, cash + float(holdings), rel_tol=1e-8, abs_tol=.01):
        return None
    evidence = [payload(r['payload_json']) for r in con.execute(
        "SELECT payload_json FROM events WHERE event_type='NAV_CALCULATED' AND account_id=?",
        (account_id,)).fetchall()]
    matching = [p for p in evidence if p.get('date') == day]
    if (any(p.get('data_kind') in {'TEST_FIXTURE', 'HISTORICAL_REPLAY'} for p in evidence)
            or not matching or any(p.get('data_kind') != 'FORWARD_SIMULATION' for p in matching)):
        return None
    if not any(isinstance(p.get('nav'), (float, int)) and math.isclose(float(p['nav']), nav, rel_tol=1e-8)
               for p in matching):
        return None
    return {'status': 'OK', 'nav': nav}
