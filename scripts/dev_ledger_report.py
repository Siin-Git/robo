"""운용 기록 현황 + 사용자별 독립성 점검 (읽기 전용).

매일 run_daily 후에 돌려서 "기록이 사용자별로 독립적으로 쌓이는지"를 확인한다.
시연 때 그대로 보여줄 수 있는 근거 출력이다. DB 에 아무것도 쓰지 않는다.

사용:
  python scripts/dev_ledger_report.py
  python scripts/dev_ledger_report.py --db data/forward_local.db   # 다른 DB 지정
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TABLES = ("participants", "accounts", "prices_daily", "portfolio_targets",
          "orders", "trades", "holdings_daily", "nav_daily", "events")


def _count(con, table: str) -> int | None:
    try:
        return con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    except sqlite3.OperationalError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dev_ledger_report")
    ap.add_argument("--db", default=None, help="DB 경로 (기본: 현재 프로파일의 DB)")
    args = ap.parse_args(argv)

    if args.db:
        db_path = Path(args.db).resolve()
        print("=====================================")
        print(f"DATABASE: {db_path}  (직접 지정)")
        print("=====================================")
    else:
        from src.forward.runtime import get_database_path, print_banner
        print_banner()
        db_path = get_database_path()
    if not db_path.is_file():
        print(f"ERROR: DB 파일이 없다: {db_path}")
        return 1

    con = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    # --- 1. 테이블 행 수 --------------------------------------------------
    print("\n[1] 테이블 행 수")
    for t in TABLES:
        n = _count(con, t)
        print(f"  {t:20s} {'(없음)' if n is None else f'{n:8d}'}")

    # --- 2. 가격 커버리지 -------------------------------------------------
    print("\n[2] 가격 커버리지")
    row = con.execute("SELECT COUNT(DISTINCT asset_id) k, MIN(date) a, MAX(date) b"
                      " FROM prices_daily").fetchone()
    if row and row["k"]:
        print(f"  자산 {row['k']}종  {row['a']} .. {row['b']}")
        fx = con.execute("SELECT COUNT(*) AS n FROM prices_daily"
                         " WHERE asset_id='__FX__'").fetchone()["n"]
        print(f"  __FX__ {fx} rows  (환산용으로만 쓰이고 저장되지 않는 것이 정상)")
    else:
        print("  (비어 있음)")

    # --- 3. 참가자별 기록 -------------------------------------------------
    print("\n[3] 참가자별 기록")
    parts = con.execute("SELECT participant_id, display_name FROM participants"
                        " ORDER BY participant_id").fetchall()
    if not parts:
        print("  (참가자 없음)")
    header = f"  {'participant':12s} {'name':14s} {'acc':>3s} {'ord':>5s} {'trd':>5s} " \
             f"{'hold':>5s} {'nav':>4s} {'last nav':>10s} {'cum%':>8s}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    totals = dict(acc=0, ord=0, trd=0, hold=0, nav=0)
    for p in parts:
        pid = p["participant_id"]
        aids = [r["account_id"] for r in con.execute(
            "SELECT account_id FROM accounts WHERE participant_id = ?", (pid,)).fetchall()]
        if not aids:
            print(f"  {pid:12s} {(p['display_name'] or '')[:14]:14s}   0     -     -"
                  f"     -    -          -        -")
            continue
        q = ",".join("?" * len(aids))

        def n_of(table, ids=aids, marks=q):
            try:
                return con.execute(f"SELECT COUNT(*) AS n FROM {table}"
                                   f" WHERE account_id IN ({marks})", ids).fetchone()["n"]
            except sqlite3.OperationalError:
                return 0

        n_ord, n_trd = n_of("orders"), n_of("trades")
        n_hold, n_nav = n_of("holdings_daily"), n_of("nav_daily")
        last = con.execute(f"SELECT date, cumulative_return FROM nav_daily"
                           f" WHERE account_id IN ({q}) ORDER BY date DESC LIMIT 1",
                           aids).fetchone()
        last_d = last["date"] if last else "-"
        cum = f"{float(last['cumulative_return']) * 100:+.2f}" if last else "-"
        print(f"  {pid:12s} {(p['display_name'] or '')[:14]:14s} {len(aids):3d} "
              f"{n_ord:5d} {n_trd:5d} {n_hold:5d} {n_nav:4d} {last_d:>10s} {cum:>8s}")
        totals["acc"] += len(aids)
        totals["ord"] += n_ord
        totals["trd"] += n_trd
        totals["hold"] += n_hold
        totals["nav"] += n_nav
    print("  " + "-" * (len(header) - 2))
    print(f"  {'합계':12s} {'':14s} {totals['acc']:3d} {totals['ord']:5d} "
          f"{totals['trd']:5d} {totals['hold']:5d} {totals['nav']:4d}")

    # --- 4. 독립성 점검 ---------------------------------------------------
    print("\n[4] 독립성 점검")
    problems = []

    # 4a. 참가자 합계가 테이블 전체와 같아야 한다(주인 없는 행이 없어야 한다)
    for table, key in (("orders", "ord"), ("trades", "trd"),
                       ("holdings_daily", "hold"), ("nav_daily", "nav")):
        total = _count(con, table) or 0
        if total != totals[key]:
            problems.append(f"{table}: 전체 {total} != 참가자 합계 {totals[key]}"
                            f" (참가자에 연결되지 않은 행 {total - totals[key]}개)")

    # 4b. 계좌 하나가 두 참가자에 속하면 안 된다
    dup = con.execute("SELECT account_id, COUNT(DISTINCT participant_id) k FROM accounts"
                      " GROUP BY account_id HAVING k > 1").fetchall()
    if dup:
        problems.append(f"여러 참가자에 걸친 계좌: {[r['account_id'] for r in dup]}")

    # 4c. 기록이 있는 계좌가 accounts 에 없으면 안 된다
    orphan = con.execute("SELECT DISTINCT o.account_id FROM orders o"
                         " LEFT JOIN accounts a ON a.account_id = o.account_id"
                         " WHERE a.account_id IS NULL").fetchall()
    if orphan:
        problems.append(f"accounts 에 없는 계좌의 주문: {[r['account_id'] for r in orphan]}")

    # 4d. 주문이 있는 계좌 수 / 균등성
    row = con.execute("SELECT COUNT(DISTINCT account_id) k FROM orders").fetchone()
    n_acc_with_orders = row["k"] if row else 0
    n_acc = _count(con, "accounts") or 0
    print(f"  주문이 있는 계좌: {n_acc_with_orders} / 전체 계좌 {n_acc}")
    per = [r["n"] for r in con.execute("SELECT COUNT(*) n FROM orders"
                                       " GROUP BY account_id").fetchall()]
    if per:
        print(f"  계좌별 주문 수: 최소 {min(per)} / 최대 {max(per)}"
              f"{'  (균등)' if min(per) == max(per) else '  (불균등 - 개인화 차이일 수 있다)'}")

    if problems:
        print("\n  ** 문제 발견 **")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  통과: 모든 기록이 참가자에 정확히 하나씩 연결되어 있다.")

    con.close()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
