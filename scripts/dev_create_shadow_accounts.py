"""벤치마크(그림자) 계좌를 설계 DB 에 만든다. 계좌 행만 만들고 끝낸다.

왜 필요한가
-----------
성과 화면의 ``Neutral 60/40`` 과 ``Equal Weight`` 선은
``benchmark_service.shadow_performance`` 가 그린다. 그 함수는
``account_type='shadow'`` 인 계좌의 ``nav_daily`` 를 읽고, 계좌가 없으면
에러 대신 빈 배열을 돌려준다. 그래서 선이 조용히 안 그려진다.

live 프로파일은 ``init_forward_test.py`` 가 초기화하면서 그림자 계좌를
만든다. 캡스톤 설계 DB 는 API 가 사용자별로 계좌를 만들다 보니 그 단계를
거치지 않아 세 계좌가 비어 있다.

무엇을 하지 않는가
------------------
목표도, 주문도, NAV 도 만들지 않는다. **계좌 행만** 만든다.

``run_monthly`` 이 이미 ``account_type IN ('core','shadow')`` 를 돌면서 세
그림자의 가중치를 계산하고 목표와 주문을 만든다. 계좌만 있으면 다음 배치가
나머지를 알아서 채운다. 여기서 목표까지 만들면 같은 일을 두 곳에서 하게 된다.

과거를 채우지 않는 이유
-----------------------
참가자 계좌는 09-28 부터 기록이 있다. 그림자를 같은 날부터 맞추려면 이미
지나간 날짜에 거래와 NAV 를 써야 한다. 가격이 있으니 계산은 되지만, 그것은
이 원장이 지키기로 한 "소급 기록 없음" 을 깨는 일이다. 벤치마크 선은 오늘부터
시작해서 며칠 뒤 참가자 선과 나란해진다.

사용
----
  python scripts/dev_create_shadow_accounts.py            # 미리보기
  python scripts/dev_create_shadow_accounts.py --apply    # 실제 생성

이미 있으면 건너뛴다(``ensure_shadow_account`` 가 멱등이다).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# DB 설정을 import 하기 전에 고정한다. src/db/config.py 가 import 시점에
# .env 를 읽고, src/forward/runtime.py 가 그것을 창구로 쓴다. 나중에 바꾸면
# 이미 결정된 경로가 남는다.
#
# 맨 프롬프트에서 그냥 실행하면 APP_PROFILE 이 없어 live 로 떨어지고
# data/forward_test.db(빈 파일)를 연다. 이 스크립트는 캡스톤 설계 DB 전용이라
# 호출자가 다른 곳으로 돌릴 수 없게 못을 박는다(seed_capstone 과 같은 방식).
os.environ.update(APP_PROFILE="local", CAPSTONE_DEMO="1", DATABASE_BACKEND="sqlite")

from src.forward.accounts import ensure_shadow_account          # noqa: E402
from src.forward.config import load_forward_config, resolve     # noqa: E402
from src.forward.db import connect                              # noqa: E402
from src.forward.runtime import get_database_path, print_banner  # noqa: E402

SHADOWS = ("core_v03", "neutral_60_40", "equal_weight")
DISPLAY = {"core_v03": "CORE V0.3", "neutral_60_40": "Neutral 60/40",
           "equal_weight": "Equal Weight"}


def weights_available(name: str, cfg) -> tuple[bool, str]:
    """만들기 전에 가중치를 구할 수 있는지 본다. 빈 계좌를 남기지 않기 위해서다."""
    if name == "core_v03":
        return True, "frozen 벤치마크"
    if name == "equal_weight":
        return True, "코어 9종 균등"
    path = resolve(cfg["phase16_outputs"]) / "neutral_60_40_weights.csv"
    if not path.exists():
        return False, f"없음: {path}"
    try:
        import pandas as pd
        w = pd.read_csv(path, index_col=0)["weight"]
        return True, f"{path.name} · 자산 {len(w)}종 · 합계 {float(w.sum()):.6f}"
    except Exception as exc:  # noqa: BLE001
        return False, f"읽기 실패: {exc}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dev_create_shadow_accounts")
    ap.add_argument("--apply", action="store_true", help="실제로 만든다(기본은 미리보기)")
    ap.add_argument("--inception", default=None,
                    help="운용 시작일 YYYY-MM-DD (기본: 오늘)")
    args = ap.parse_args(argv)

    print_banner()
    cfg = load_forward_config()
    con = connect(get_database_path())

    from datetime import date
    inception = args.inception or date.today().isoformat()

    # 엉뚱한 DB 를 열었을 때 traceback 대신 무슨 일인지 말한다.
    if con.execute("SELECT COUNT(*) c FROM sqlite_master WHERE type='table'"
                   " AND name='accounts'").fetchone()["c"] == 0:
        print(f"\n이 DB 에는 accounts 테이블이 없다: {get_database_path()}")
        print("캡스톤 설계 DB 가 아니다. 먼저 API 를 한 번 띄우거나")
        print("python scripts/dev_seed_design_db.py 를 돌려 DB 를 만들 것.")
        return 1

    existing = {r["shadow_name"] for r in con.execute(
        "SELECT shadow_name FROM accounts WHERE account_type='shadow'").fetchall()}

    print(f"\n운용 시작일: {inception}")
    print(f"이미 있는 그림자 계좌: {sorted(existing) or '없음'}\n")

    ok = True
    for name in SHADOWS:
        available, note = weights_available(name, cfg)
        state = "이미 있음" if name in existing else ("만든다" if available else "불가")
        print(f"  {DISPLAY[name]:16s} {state:10s} {note}")
        if not available and name not in existing:
            ok = False
    if not ok:
        print("\n가중치를 구할 수 없는 그림자가 있다. 만들지 않는다.")
        return 1

    if not args.apply:
        print("\n미리보기다. 실제로 만들려면 --apply 를 붙일 것.")
        return 0

    made = []
    for name in SHADOWS:
        if name in existing:
            continue
        aid = ensure_shadow_account(con, name, inception, cfg,
                                    cfg["forward_test"]["benchmark_version"])
        made.append(aid)
    con.commit()

    rows = con.execute("SELECT account_id, shadow_name, inception_date, status"
                       " FROM accounts WHERE account_type='shadow'"
                       " ORDER BY shadow_name").fetchall()
    print(f"\n새로 만든 계좌 {len(made)}개")
    for r in rows:
        print(f"  {r['account_id']:28s} {r['shadow_name']:16s} "
              f"{r['inception_date']}  {r['status']}")

    print("\n다음: 장이 닫힌 시간에 scripts\\run_daily_task.bat 을 돌릴 것.")
    print("  run_monthly 이 세 계좌의 목표와 주문을 만들고,")
    print("  그다음 종가에 체결되면서 NAV 가 쌓인다.")
    print("  NAV 가 이틀치 모이면 성과 화면에 벤치마크 선이 그려진다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
