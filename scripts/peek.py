"""로컬 DB 훑어보기: python scripts/peek.py"""
import sqlite3

con = sqlite3.connect("data/forward_local.db")
con.row_factory = sqlite3.Row

print("-- 행 수")
for t in ("prices_daily", "orders", "trades", "holdings_daily", "nav_daily"):
    print(f"{t:<16}", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])

print("\n-- NAV")
for r in con.execute("SELECT account_id, date, ROUND(nav) nav, ROUND(cash_balance) cash,"
                     " nav_status FROM nav_daily ORDER BY account_id, date"):
    print(dict(r))

print("\n-- 보유 (CORE)")
for r in con.execute("SELECT asset_id, ROUND(quantity,2) q, ROUND(market_value) mv,"
                     " ROUND(weight,4) w FROM holdings_daily"
                     " WHERE account_id = ? ORDER BY asset_id", ("A-P001-CORE",)):
    print(dict(r))