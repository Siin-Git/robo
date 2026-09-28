"""로컬 개발용: 스냅샷 가격만으로 최초 주문 → 체결 → 평가까지 한 번 돌린다.

네트워크를 쓰지 않는다. run_daily 는 항상 '오늘' 기준이고 실행 모드에서
yfinance 를 호출하므로, 스냅샷 마지막 거래일 기준으로 원장을 만들어 보려면
이 스크립트를 쓴다.

APP_PROFILE=local 에서만 동작한다 (data/forward_local.db).
여러 번 실행해도 결과가 같아야 한다 (멱등성 확인용).

    python -m scripts.dev_bootstrap_ledger
    python -m scripts.dev_bootstrap_ledger --asof 2026-09-11
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
from src.forward.runtime import get_database_path, get_runtime_profile, print_banner  # noqa: E402


def main(argv=None) -> int:
    profile = print_banner()
    if profile != "local":
        print("ERROR: APP_PROFILE=local 에서만 실행할 수 있다 (개발용 스크립트).")
        return 2

    ap = argparse.ArgumentParser(prog="dev_bootstrap_ledger")
    ap.add_argument("--asof", default=None,
                    help="기준 거래일 (기본: prices_daily 의 마지막 날짜)")
    ap.add_argument("--dry-run", action="store_true", help="쓰기 없이 계획만 출력")
    ap.add_argument("--backdate-targets", action="store_true",
                    help="portfolio_targets.effective_date 를 asof 로 내린다 "
                         "(로컬 DB 전용. 가격이 계정 생성일보다 오래됐을 때만)")
    args = ap.parse_args(argv)

    cfg = load_forward_config()
    ft = cfg["forward_test"]
    versions = versions_from_cfg(cfg)
    con = connect(get_database_path())

    asof = args.asof or con.execute(
        "SELECT MAX(date) m FROM prices_daily").fetchone()["m"]
    if asof is None:
        print("ERROR: prices_daily 가 비어 있다. 먼저 python -m src.local.init")
        return 2

    accounts = [dict(r) for r in con.execute(
        "SELECT * FROM accounts WHERE status='active' ORDER BY account_id")]
    print(f"\nasof = {asof} · 활성 계좌 {len(accounts)}개")
    if not accounts:
        print("계좌가 없다. 먼저 테스트 계정을 만들 것.")
        return 2

    if args.dry_run:
        for a in accounts:
            n_ord = con.execute("SELECT COUNT(*) c FROM orders WHERE account_id=?",
                                (a["account_id"],)).fetchone()["c"]
            n_nav = con.execute("SELECT COUNT(*) c FROM nav_daily WHERE account_id=?",
                                (a["account_id"],)).fetchone()["c"]
            print(f"  {a['account_id']}: 주문 {n_ord}건, NAV {n_nav}행 "
                  f"→ {'주문 생성 예정' if n_ord == 0 else '주문 있음(생성 생략)'}")
        print("DRY RUN: 아무것도 쓰지 않았다.")
        return 0

    # 0) 목표 비중의 effective_date 가 asof 보다 뒤면 체결이 불가능하다.
    #    (execute_pending 은 effective_date <= 주문 effective_at 인 목표만 읽는다)
    late = con.execute("SELECT COUNT(*) c FROM portfolio_targets WHERE effective_date > ?",
                       (asof,)).fetchone()["c"]
    if late:
        if args.backdate_targets:
            con.execute("UPDATE portfolio_targets SET effective_date = ?"
                        " WHERE effective_date > ?", (asof, asof))
            con.commit()
            print(f"  목표 비중 {late}건의 effective_date 를 {asof} 로 내렸다 (로컬 전용).")
        else:
            print(f"\n경고: 목표 비중 {late}건이 asof({asof})보다 뒤 날짜다.")
            print("      가격 데이터가 계정 생성일보다 오래돼서 체결이 불가능하다.")
            print("      해결: 가격을 최신화하거나, --backdate-targets 로 로컬에서 날짜를 맞춘다.")

    # 1) 최초 주문 — 주문이 하나도 없는 계좌에만 생성한다 (재실행해도 중복 없음)
    for a in accounts:
        n_ord = con.execute("SELECT COUNT(*) c FROM orders WHERE account_id=?",
                            (a["account_id"],)).fetchone()["c"]
        if n_ord:
            print(f"  {a['account_id']}: 기존 주문 {n_ord}건 → 생성 생략")
            continue
        t = con.execute("SELECT weights_json FROM portfolio_targets WHERE account_id=?"
                        " ORDER BY effective_date DESC, created_at DESC, target_id DESC LIMIT 1",
                        (a["account_id"],)).fetchone()
        if not t:
            print(f"  {a['account_id']}: 목표 비중 없음 → 건너뜀")
            continue
        oids = create_orders(con, a["account_id"], json.loads(t["weights_json"]),
                             now_iso(), asof, ft["benchmark_version"],
                             a["participant_id"], kind="DEV_INITIAL_ORDER")
        log_event(con, "DEV_INITIAL_ORDERS_CREATED", ft["benchmark_version"],
                  a["participant_id"], a["account_id"], {"effective": asof, "n": len(oids)})
        print(f"  {a['account_id']}: 주문 {len(oids)}건 생성 (effective={asof})")
    con.commit()

    # 2) 체결 — next available close <= asof 인 주문만
    for a in accounts:
        filled = execute_pending(con, a["account_id"], asof,
                                 float(ft["costs"]["trading_cost_bps"]),
                                 ft["benchmark_version"], a["participant_id"])
        print(f"  {a['account_id']}: 체결 {len(filled)}건")
    con.commit()

    # 3) 평가 — holdings_daily + nav_daily 기록
    for a in accounts:
        r = valuate(con, a["account_id"], asof, versions,
                    float(a["initial_capital_krw"]),
                    int(ft.get("stale_price_days", 14)))
        print(f"  {a['account_id']}: status={r.get('status')} nav={r.get('nav')}")
    con.commit()

    # 4) 결과 요약
    print("\n--- 결과 ---")
    for t in ("orders", "trades", "holdings_daily", "nav_daily"):
        n = con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        print(f"{t:<16} {n}")
    for r in con.execute("SELECT account_id, date, nav, cash_balance, nav_status"
                         " FROM nav_daily ORDER BY account_id, date"):
        print(dict(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
