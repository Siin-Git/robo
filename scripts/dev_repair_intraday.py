"""장중에 받아온 잠정가를 지운다. 로컬 개발 전용.

왜 필요한가
-----------
야후는 장이 열려 있는 동안에도 그날 바를 돌려준다. 그 값이 저장되면
``refresh_live`` 의 증분 규칙(시작점 = 마지막 보유일 + 1일) 때문에 같은 날짜를
다시 받아오지 않는다. 즉 **잠정가가 종가로 굳고 스스로 고쳐지지 않는다.**

이 스크립트는 지정한 날짜의 가격을 해당 시장 자산에 한해 지워서, 다음 실행이
그 날짜부터 다시 받아오게 만든다. 그 날짜로 계산된 보유·NAV 도 함께 지운다
(잘못된 가격으로 만든 평가라서 남겨두면 안 된다).

시장 판정은 하드코딩하지 않고 티커 접미사로 한다(.KS/.KQ = 한국, 그 외 = 미국).

사용:
  python scripts/dev_repair_intraday.py --date 2026-09-29 --market us
  python scripts/dev_repair_intraday.py --date 2026-09-29 --market us --apply

--apply 없이 돌리면 무엇을 지울지만 보여주고 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import argparse
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

KOREA_SUFFIXES = (".KS", ".KQ")


def classify(tickers: dict) -> dict:
    """asset_id -> 'kr' | 'us'. __FX__ 는 저장되지 않으므로 제외한다."""
    out = {}
    for asset, ticker in tickers.items():
        if asset == "__FX__":
            continue
        t = str(ticker or "").upper()
        out[asset] = "kr" if t.endswith(KOREA_SUFFIXES) else "us"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dev_repair_intraday")
    ap.add_argument("--date", required=True, help="지울 거래일 YYYY-MM-DD")
    ap.add_argument("--market", choices=("us", "kr", "all"), default="us")
    ap.add_argument("--apply", action="store_true", help="실제로 지운다(기본: 미리보기)")
    args = ap.parse_args(argv)

    from src.forward.config import load_forward_config, resolve
    from src.forward.db import connect
    from src.forward.frozen import load_frozen_benchmark
    from src.forward.run_daily import tickers_map
    from src.forward.runtime import get_database_path, get_runtime_profile, print_banner

    print_banner()
    if get_runtime_profile() == "live":
        print("ERROR: LIVE 프로파일에서는 실행하지 않는다.")
        return 2

    cfg = load_forward_config()
    con = connect(get_database_path())
    _w, meta = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    market_of = classify(tickers_map(con, meta))

    targets = sorted(a for a, mk in market_of.items()
                     if args.market == "all" or mk == args.market)
    if not targets:
        print("대상 자산이 없다.")
        return 1

    marks = ",".join("?" * len(targets))
    rows = con.execute(
        f"SELECT asset_id, price FROM prices_daily WHERE date = ? AND asset_id IN ({marks})"
        " ORDER BY asset_id", (args.date, *targets)).fetchall()
    n_nav = con.execute("SELECT COUNT(*) AS n FROM nav_daily WHERE date = ?",
                        (args.date,)).fetchone()["n"]
    n_hold = con.execute("SELECT COUNT(*) AS n FROM holdings_daily WHERE date = ?",
                         (args.date,)).fetchone()["n"]
    n_trade = con.execute("SELECT COUNT(*) AS n FROM trades WHERE execution_at = ?",
                          (args.date,)).fetchone()["n"]

    print(f"\n[{args.date}] market={args.market}")
    print(f"  지울 가격 {len(rows)}건")
    for r in rows:
        print(f"    {r['asset_id']:24s} {float(r['price']):,.4f}")
    print(f"  함께 지울 평가: holdings_daily {n_hold}건, nav_daily {n_nav}건")

    if n_trade:
        print(f"\n  ** 경고: 이 날짜에 체결 {n_trade}건이 있다. **")
        print("  체결 가격이 잠정가였다면 수량과 현금이 잘못 계산됐다는 뜻이다.")
        print("  가격만 지우면 원장이 어긋나므로, 체결까지 되돌릴지 먼저 판단할 것.")
        if args.apply:
            print("  중단한다.")
            return 2

    if not rows and not n_nav and not n_hold:
        print("\n  지울 것이 없다.")
        return 0

    if not args.apply:
        print("\n  미리보기다. 실제로 지우려면 --apply 를 붙일 것.")
        print("  (지우기 전에 DB 를 복사해 둘 것)")
        return 0

    con.execute(f"DELETE FROM prices_daily WHERE date = ? AND asset_id IN ({marks})",
                (args.date, *targets))
    con.execute("DELETE FROM holdings_daily WHERE date = ?", (args.date,))
    con.execute("DELETE FROM nav_daily WHERE date = ?", (args.date,))
    from src.forward.db import log_event
    log_event(con, "INTRADAY_PRICES_REPAIRED",
              cfg["forward_test"]["benchmark_version"],
              payload={"date": args.date, "market": args.market,
                       "prices_removed": len(rows), "holdings_removed": n_hold,
                       "nav_removed": n_nav,
                       "reason": "prices were fetched while the market was open"})
    con.commit()
    print("\n  지웠다. 다음 실행이 그 날짜부터 다시 받아온다.")
    print("  (events 에 INTRADAY_PRICES_REPAIRED 로 기록했다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
