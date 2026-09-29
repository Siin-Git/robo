"""실시간 종가 준비 점검 (읽기 전용).

5단계(실시간 가격) 시작 전에 "refresh_live 가 지금 돌 수 있는가"만 확인한다.
DB 에 아무것도 쓰지 않고, 주문·체결도 만들지 않는다.

확인 항목
  1) 현재 prices_daily 커버리지 (자산별 마지막 날짜, __FX__ 포함)
  2) frozen 벤치마크 + 활성 테마에서 만들어지는 티커 맵
  3) 각 티커가 Yahoo chart API 에서 실제로 내려오는지
  4) refresh_live 가 'no FX data available' 로 죽을 조건에 걸리는지

사용:
  python scripts/dev_check_live_prices.py
  python scripts/dev_check_live_prices.py --days 10   # 조회 창 크기
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.forward.config import load_forward_config, resolve          # noqa: E402
from src.forward.db import connect                                   # noqa: E402
from src.forward.frozen import load_frozen_benchmark                 # noqa: E402
from src.forward.run_daily import tickers_map                        # noqa: E402
from src.forward.runtime import get_database_path, print_banner      # noqa: E402


def main(argv=None) -> int:
    print_banner()
    ap = argparse.ArgumentParser(prog="dev_check_live_prices")
    ap.add_argument("--days", type=int, default=14, help="조회 창(일)")
    args = ap.parse_args(argv)

    cfg = load_forward_config()
    con = connect(get_database_path())

    # --- 1. 현재 커버리지 --------------------------------------------------
    print("\n[1] prices_daily 커버리지")
    rows = con.execute("SELECT asset_id, COUNT(*) AS n, MIN(date) AS a, MAX(date) AS b"
                       " FROM prices_daily GROUP BY asset_id ORDER BY asset_id").fetchall()
    if not rows:
        print("  (비어 있음)")
    have = {}
    for r in rows:
        have[r["asset_id"]] = r["b"]
        print(f"  {r['asset_id']:24s} {r['n']:6d} rows  {r['a']} .. {r['b']}")
    fx_rows = have.get("__FX__")
    print(f"\n  __FX__ 저장 여부: {'있음 (' + str(fx_rows) + ' 까지)' if fx_rows else '없음 (0 rows)'}")

    # --- 2. 티커 맵 -------------------------------------------------------
    print("\n[2] 티커 맵 (frozen tickers + 활성 테마)")
    _w, meta = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    tmap = tickers_map(con, meta)
    for aid, t in sorted(tmap.items()):
        print(f"  {aid:24s} -> {t}")

    # --- 3. 실제 조회 -----------------------------------------------------
    print(f"\n[3] Yahoo chart API 조회 (최근 {args.days}일, 쓰기 없음)")
    from src.data.provider import get_default_provider
    provider = get_default_provider()
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=args.days)).isoformat()
    ok, fail = [], []
    for aid, ticker in sorted(tmap.items()):
        try:
            s = provider.get_price_history(ticker, start, end)
            ok.append(aid)
            print(f"  OK   {aid:24s} {ticker:12s} rows={len(s):3d} "
                  f"last={s.index[-1].date()} px={float(s.iloc[-1]):,.4f}")
        except Exception as exc:  # noqa: BLE001 - 진단이 목적이다
            fail.append((aid, ticker, str(exc)[:100]))
            print(f"  FAIL {aid:24s} {ticker:12s} {type(exc).__name__}: {str(exc)[:80]}")

    # --- 4. 판정 ----------------------------------------------------------
    print("\n[4] 판정")
    fx_fetch_ok = "__FX__" in ok
    if fx_fetch_ok:
        print("  FX 조회 성공 -> refresh_live 가 'no FX data available' 로 죽지 않는다.")
    elif fx_rows:
        print("  FX 조회 실패했지만 저장된 __FX__ 가 있어 stale 로 처리된다(진행 가능).")
    else:
        print("  ** FX 조회도 실패하고 저장된 __FX__ 도 없다 -> refresh_live 가"
              " RuntimeError('no FX data available') 로 멈춘다. 먼저 이걸 해결해야 한다. **")
    print(f"  성공 {len(ok)} / 실패 {len(fail)} (실패 자산은 stale 로 보고되고 건너뛴다)")
    for aid, ticker, msg in fail:
        print(f"    - {aid} ({ticker}): {msg}")

    print("\n  * 이 스크립트는 DB 를 읽기만 했다. 아무것도 쓰지 않았다.")
    con.close()
    return 0 if fx_fetch_ok or fx_rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
