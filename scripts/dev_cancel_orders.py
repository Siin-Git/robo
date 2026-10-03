"""대기 중인 주문을 취소한다 (기본은 미리보기).

중복 생성된 주문을 체결 전에 멈추는 용도다. **행을 지우지 않는다.**
원장에서 삭제는 하면 안 되고, execute_pending 이 status='pending' 만 집으므로
'cancelled' 로 바꾸는 것으로 충분한다. 취소 기록은 events 에 남는다.

  python scripts/dev_cancel_orders.py --account-type shadow --effective-at 2026-10-01
  python scripts/dev_cancel_orders.py --account-type shadow --effective-at 2026-10-01 --apply

왜 필요했나: 2026-10-01 에 작업 기록(scheduled_jobs)이 인증 DB 로 가는 버그 때문에
월간 리밸런싱이 두 번 돌았고, 벤치마크 계좌 3개에 중복 주문 26건이 생겼다.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# dev_ledger_report 와 같은 이유로 프로파일을 여기서 정한다. DATABASE_BACKEND 는
# 건드리지 않는다 - .env.local 이 SQLite/PostgreSQL 을 정하게 둔다.
os.environ.setdefault("APP_PROFILE", "local")
os.environ.setdefault("CAPSTONE_DEMO", "1")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dev_cancel_orders")
    ap.add_argument("--effective-at", default=date.today().isoformat(),
                    help="이 effective_at 의 주문만 (기본: 오늘)")
    ap.add_argument("--account-type", default=None,
                    help="core / personal / shadow 중 하나로 한정")
    ap.add_argument("--account", default=None, help="계좌 하나로 한정")
    ap.add_argument("--keep", type=int, default=0,
                    help="계좌·자산마다 남길 개수 (기본 0 = 해당 조건 전부 취소)")
    ap.add_argument("--apply", action="store_true", help="실제로 취소한다 (기본은 미리보기)")
    args = ap.parse_args(argv)

    from src.forward.runtime import get_database_path, print_banner
    from src.forward.db import connect, log_event
    print_banner()
    con = connect(get_database_path())

    where = ["o.status = 'pending'", "o.effective_at = ?"]
    params: list = [args.effective_at]
    if args.account_type:
        where.append("a.account_type = ?")
        params.append(args.account_type)
    if args.account:
        where.append("o.account_id = ?")
        params.append(args.account)

    rows = [dict(r) for r in con.execute(
        "SELECT o.order_id, o.account_id, o.asset_id, o.side, o.effective_at,"
        " o.submitted_at, a.account_type"
        " FROM orders o JOIN accounts a ON a.account_id = o.account_id"
        " WHERE " + " AND ".join(where) +
        " ORDER BY o.account_id, o.asset_id, o.submitted_at, o.order_id",
        tuple(params)).fetchall()]

    if not rows:
        print(f"\neffective_at={args.effective_at} 에 대기 중인 주문이 없다. 할 일 없음.")
        return 0

    # 계좌·자산마다 앞의 --keep 개는 남긴다. 기본값 0 이면 전부 대상이다.
    seen: dict[tuple, int] = {}
    targets = []
    for r in rows:
        key = (r["account_id"], r["asset_id"])
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > args.keep:
            targets.append(r)

    print(f"\n대기 중 {len(rows)}건 중 취소 대상 {len(targets)}건"
          f"  (effective_at={args.effective_at}"
          + (f", account_type={args.account_type}" if args.account_type else "") + ")\n")
    print(f"  {'order_id':10s} {'account':26s} {'asset':22s} {'side':5s} submitted_at")
    print("  " + "-" * 86)
    for r in targets:
        print(f"  {r['order_id']:10s} {r['account_id']:26s} {r['asset_id']:22s}"
              f" {r['side']:5s} {r['submitted_at']}")

    if not args.apply:
        print("\n미리보기다. 실제로 취소하려면 --apply 를 붙일 것. 아무것도 쓰지 않았다.")
        return 0

    by_account: dict[str, list[str]] = {}
    for r in targets:
        con.execute("UPDATE orders SET status = 'cancelled' WHERE order_id = ?",
                    (r["order_id"],))
        by_account.setdefault(r["account_id"], []).append(r["order_id"])

    for account_id, oids in by_account.items():
        log_event(con, "ORDERS_CANCELLED", "manual-cleanup", account_id=account_id,
                  payload={"order_ids": oids, "effective_at": args.effective_at,
                           "reason": "duplicate monthly rebalance (scheduled_jobs "
                                     "routed to the auth DB on postgres)"})
    con.commit()

    left = con.execute(
        "SELECT COUNT(*) c FROM orders WHERE status = 'pending' AND effective_at = ?",
        (args.effective_at,)).fetchone()["c"]
    print(f"\n{len(targets)}건 취소했다. {args.effective_at} 에 남은 대기 주문: {left}건")
    print("events 에 ORDERS_CANCELLED 로 기록됐다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
