"""로컬 개발용: 스냅샷 가격으로 NAV 시계열을 만든다 (네트워크 없음).

start 일자에 목표 비중대로 최초 체결한 뒤, start~end 사이의 모든 거래일에 대해
평가(valuate)를 반복한다. 결과는 nav_daily / holdings_daily 에 쌓인다.

APP_PROFILE=local 에서만 동작한다. 여러 번 실행해도 결과가 같다(멱등).

    python scripts/dev_build_nav_history.py --start 2026-04-01
    python scripts/dev_build_nav_history.py --start 2026-04-01 --reset-ledger
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("APP_PROFILE", "local")

from src.forward.accounts import versions_from_cfg  # noqa: E402
from src.forward.config import load_forward_config  # noqa: E402
from src.forward.db import connect, log_event, now_iso  # noqa: E402
from src.forward.execution import create_orders, execute_pending  # noqa: E402
from src.forward.ledger import valuate  # noqa: E402
from src.forward.runtime import get_database_path, print_banner  # noqa: E402

LEDGER_TABLES = ("nav_daily", "holdings_daily", "trades", "orders")


def main(argv=None) -> int:
    profile = print_banner()
    if profile != "local":
        print("ERROR: APP_PROFILE=local 에서만 실행할 수 있다 (개발용 스크립트).")
        return 2

    ap = argparse.ArgumentParser(prog="dev_build_nav_history")
    ap.add_argument("--start", default="2026-04-01", help="운용 시작일 (최초 체결일)")
    ap.add_argument("--end", default=None, help="마지막 평가일 (기본: 가격 마지막 날)")
    ap.add_argument("--reset-ledger", action="store_true",
                    help="orders/trades/holdings_daily/nav_daily 를 비우고 다시 만든다")
    args = ap.parse_args(argv)

    cfg = load_forward_config()
    ft = cfg["forward_test"]
    versions = versions_from_cfg(cfg)
    con = connect(get_database_path())

    end = args.end or con.execute("SELECT MAX(date) m FROM prices_daily").fetchone()["m"]
    start = args.start
    dates = [r["date"] for r in con.execute(
        "SELECT DISTINCT date FROM prices_daily WHERE date >= ? AND date <= ? ORDER BY date",
        (start, end))]
    if not dates:
        print(f"ERROR: {start}~{end} 구간에 가격 데이터가 없다.")
        return 2
    start = dates[0]  # 실제 거래일로 보정

    accounts = [dict(r) for r in con.execute(
        "SELECT * FROM accounts WHERE status='active' ORDER BY account_id")]
    if not accounts:
        print("ERROR: 활성 계좌가 없다.")
        return 2

    print(f"\n구간 {start} ~ {end} · 거래일 {len(dates)}일 · 계좌 {len(accounts)}개")

    if args.reset_ledger:
        for t in LEDGER_TABLES:
            n = con.execute(f"DELETE FROM {t}").rowcount
            print(f"  reset {t}: {n}행 삭제")
        con.commit()

    # 목표 비중 날짜를 시작일로 맞춘다 (로컬 전용)
    late = con.execute("SELECT COUNT(*) c FROM portfolio_targets WHERE effective_date > ?",
                       (start,)).fetchone()["c"]
    if late:
        con.execute("UPDATE portfolio_targets SET effective_date = ? WHERE effective_date > ?",
                    (start, start))
        con.commit()
        print(f"  목표 비중 {late}건의 effective_date 를 {start} 로 맞췄다 (로컬 전용).")

    # 1) 최초 주문 (주문이 없는 계좌만)
    for a in accounts:
        if con.execute("SELECT COUNT(*) c FROM orders WHERE account_id=?",
                       (a["account_id"],)).fetchone()["c"]:
            continue
        t = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id=?"
                        " ORDER BY effective_date DESC, created_at DESC, target_id DESC LIMIT 1", (a["account_id"],)).fetchone()
        if not t:
            continue
        oids = create_orders(con, a["account_id"], json.loads(t["weights_json"]),
                             now_iso(), start, ft["benchmark_version"],
                             a["participant_id"], kind="DEV_INITIAL_ORDER")
        log_event(con, "DEV_INITIAL_ORDERS_CREATED", ft["benchmark_version"],
                  a["participant_id"], a["account_id"], {"effective": start, "n": len(oids)})
        print(f"  {a['account_id']}: 최초 주문 {len(oids)}건 (effective={start})")
    con.commit()

    # 2) 거래일마다 체결 + 평가
    cost_bps = float(ft["costs"]["trading_cost_bps"])
    stale_days = int(ft.get("stale_price_days", 14))
    skipped = []
    for i, d in enumerate(dates, 1):
        for a in accounts:
            execute_pending(con, a["account_id"], d, cost_bps,
                            ft["benchmark_version"], a["participant_id"])
            r = valuate(con, a["account_id"], d, versions,
                        float(a["initial_capital_krw"]), stale_days)
            if r.get("status") == "NAV_INCOMPLETE":
                skipped.append((d, a["account_id"], r.get("reason") or r.get("missing")))
        if i % 20 == 0 or i == len(dates):
            print(f"  ... {i}/{len(dates)}일 처리 ({d})")
    con.commit()

    if skipped:
        print(f"\n건너뛴 평가 {len(skipped)}건 (앞부분 일부는 정상): {skipped[:3]}")

    # 3) 요약
    print("\n--- 결과 ---")
    for t in ("orders", "trades", "holdings_daily", "nav_daily"):
        print(f"{t:<16}", con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])

    for a in accounts:
        rows = [dict(r) for r in con.execute(
            "SELECT date, nav, nav_base100, cumulative_return FROM nav_daily"
            " WHERE account_id=? ORDER BY date", (a["account_id"],))]
        if not rows:
            continue
        first, last = rows[0], rows[-1]
        peak, mdd = first["nav"], 0.0
        for r in rows:
            peak = max(peak, r["nav"])
            mdd = min(mdd, r["nav"] / peak - 1.0)
        print(f"\n{a['account_id']} · {len(rows)}일")
        print(f"  {first['date']} NAV {first['nav']:,.0f} (base100 {first['nav_base100']:.2f})")
        print(f"  {last['date']} NAV {last['nav']:,.0f} (base100 {last['nav_base100']:.2f})")
        print(f"  누적수익률 {last['cumulative_return'] * 100:+.2f}% · MDD {mdd * 100:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
