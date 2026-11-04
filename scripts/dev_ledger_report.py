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
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 맨 프롬프트에서 그냥 실행하면 APP_PROFILE 이 없어 live 로 떨어지고 빈
# forward_test.db 를 연다. 캡스톤 운용 기록을 보는 도구이므로 기본값을 여기서
# 정한다. setdefault 라 run_daily_task.bat 처럼 이미 지정한 쪽이 우선이다.
# DATABASE_BACKEND 는 건드리지 않는다 - 고정하면 PostgreSQL 전환을 막는다.
os.environ.setdefault("APP_PROFILE", "local")
os.environ.setdefault("CAPSTONE_DEMO", "1")

TABLES = ("participants", "accounts", "prices_daily", "portfolio_targets",
          "orders", "trades", "holdings_daily", "nav_daily", "events")


def _count(con, table: str) -> int | None:
    """테이블이 없으면 None. PostgreSQL 은 실패한 쿼리가 트랜잭션을 중단시켜,
    롤백하지 않으면 이후 모든 조회가 같이 실패한다."""
    try:
        return con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dev_ledger_report")
    ap.add_argument("--db", default=None, help="DB 경로 (기본: 현재 프로파일의 DB)")
    args = ap.parse_args(argv)

    if args.db:
        # 파일을 직접 지정하면 읽기 전용으로 연다(실수로 쓰지 않도록).
        db_path = Path(args.db).resolve()
        print("=====================================")
        print(f"DATABASE: {db_path}  (직접 지정)")
        print("=====================================")
        if not db_path.is_file():
            print(f"ERROR: DB 파일이 없다: {db_path}")
            return 1
        con = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    else:
        # 프로파일이 가리키는 곳. PostgreSQL 이면 어댑터를 거친다.
        # 이 스크립트는 SELECT 만 한다(쓰기 경로가 없다).
        from src.forward.runtime import get_database_path, print_banner
        from src.forward.db import connect
        print_banner()
        con = connect(get_database_path())

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
            except Exception:
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

    # 벤치마크(그림자) 계좌는 참가자가 없는 것이 정상이다. 비교 기준선이지
    # 누군가의 포트폴리오가 아니다. 참가자 합계에서 빼고 따로 센다.
    shadows = [r["account_id"] for r in con.execute(
        "SELECT account_id FROM accounts WHERE account_type = 'shadow'").fetchall()]
    shadow_rows = {}
    if shadows:
        marks = ",".join("?" * len(shadows))
        for table in ("orders", "trades", "holdings_daily", "nav_daily"):
            try:
                shadow_rows[table] = con.execute(
                    f"SELECT COUNT(*) AS n FROM {table}"
                    f" WHERE account_id IN ({marks})", shadows).fetchone()["n"]
            except Exception:
                try:
                    con.rollback()
                except Exception:
                    pass
                shadow_rows[table] = 0
        print(f"  벤치마크 계좌 {len(shadows)}개 (참가자 없음): "
              + ", ".join(f"{t} {shadow_rows[t]}" for t in
                          ("orders", "trades", "holdings_daily", "nav_daily")))

    # 4a. 참가자 합계 + 벤치마크가 테이블 전체와 같아야 한다(주인 없는 행이 없어야 한다)
    for table, key in (("orders", "ord"), ("trades", "trd"),
                       ("holdings_daily", "hold"), ("nav_daily", "nav")):
        total = _count(con, table) or 0
        accounted = totals[key] + shadow_rows.get(table, 0)
        if total != accounted:
            problems.append(f"{table}: 전체 {total} != 참가자 {totals[key]}"
                            f" + 벤치마크 {shadow_rows.get(table, 0)}"
                            f" (어디에도 속하지 않는 행 {total - accounted}개)")

    # 4b. 계좌 구성이 참가자마다 온전한지 본다.
    #
    # 여기 있던 검사는 "한 계좌가 두 참가자에 속하는가" 였는데, 두 가지가 틀렸다.
    #
    #   1) HAVING 에서 SELECT 별칭(k)을 썼다. SQLite 는 받아주지만 PostgreSQL 은
    #      HAVING 을 SELECT 보다 먼저 평가해서 "column k does not exist" 로 죽는다.
    #      표준은 PostgreSQL 쪽이고, 전환하면서 드러났다.
    #   2) 고쳐도 아무것도 잡지 못한다. account_id 가 기본키라 그룹마다 행이
    #      정확히 하나고, COUNT(DISTINCT participant_id) 는 1 을 넘을 수 없다.
    #
    # 그래서 실제로 깨질 수 있는 불변식으로 바꾼다. 참가자는 core 와 personal 을
    # 하나씩 가져야 한다. 인원을 13 -> 15 로 늘릴 때 이메일만 늘고 계좌가 따라
    # 생기지 않는 사고가 실제로 있었고, 그런 건 이 검사가 잡는다.
    #
    # 판정은 파이썬에서 한다. HAVING 에 집계를 또 쓰면 같은 함정을 반복하게 된다.
    for r in con.execute(
            "SELECT participant_id,"
            " SUM(CASE WHEN account_type = 'core' THEN 1 ELSE 0 END) n_core,"
            " SUM(CASE WHEN account_type = 'personal' THEN 1 ELSE 0 END) n_personal,"
            " COUNT(*) n_all"
            " FROM accounts WHERE participant_id IS NOT NULL"
            " GROUP BY participant_id").fetchall():
        # PostgreSQL 의 SUM 은 bigint/numeric 으로 돌아온다. int 로 맞춰서 비교한다.
        got = (int(r["n_core"]), int(r["n_personal"]), int(r["n_all"]))
        if got != (1, 1, 2):
            problems.append(
                f"{r['participant_id']}: core {got[0]}, personal {got[1]},"
                f" 합계 {got[2]} (1, 1, 2 여야 한다)")

    # 4b-2. 벤치마크 계좌는 참가자에 붙으면 안 된다. 붙는 순간 그 참가자의 수익률에
    # 섞여서 "사용자별로 독립적으로 쌓인다" 는 주장이 무너진다.
    for r in con.execute("SELECT account_id, participant_id, shadow_name FROM accounts"
                         " WHERE account_type = 'shadow'").fetchall():
        if r["participant_id"] is not None:
            problems.append(f"벤치마크 계좌 {r['account_id']} 에 참가자"
                            f" {r['participant_id']} 가 붙어 있다")
        if not r["shadow_name"]:
            problems.append(f"벤치마크 계좌 {r['account_id']} 에 shadow_name 이 없다")

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
    # 균등성은 참가자 계좌끼리만 본다. 벤치마크는 비중 구성이 달라 수가 다르다.
    per = [r["n"] for r in con.execute(
        "SELECT COUNT(*) n FROM orders o JOIN accounts a"
        " ON a.account_id = o.account_id"
        " WHERE a.account_type <> 'shadow' GROUP BY o.account_id").fetchall()]
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
