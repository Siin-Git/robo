"""캡스톤 설계 DB(portfolio_design.db)를 npm/Node 없이 채운다. 로컬 개발 전용.

scripts/start_demo.py 는 Next.js 웹까지 띄우므로 Node·npm 이 필요하다. 백엔드
작업만 할 때는 그게 필요 없다. 이 스크립트는 같은 환경을 만들고 FastAPI 를
TestClient 로 직접 호출해서, 실제 서비스와 똑같은 경로로 설계 DB 를 채운다.

채워지는 것(전부 API 의 기존 로직이 한다. 여기서 직접 INSERT 하지 않는다):
  - themes          : capstone_demo.db 에서 복사 (get_design_db)
  - prices_daily    : DESIGN_PRICE_SOURCE 의 가격 이력 1회 복사 (load_reference_prices)
  - participants    : 로그인한 사용자별로 생성 (get_design_db)

이미 가격이 있으면 덮어쓰지 않는다. 계정·NAV·보유·거래는 복사하지 않는다.

사용:
  python scripts/dev_seed_design_db.py                 # 시연 계정 전원
  python scripts/dev_seed_design_db.py --users 1       # 1명만
  python scripts/dev_seed_design_db.py --skip-seed     # capstone_demo.db 시드 생략
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _report(db_path: Path, label: str) -> None:
    print(f"\n[{label}] {db_path}")
    if not db_path.is_file():
        print("  (파일 없음)")
        return
    con = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        for table in ("prices_daily", "themes", "participants", "accounts",
                      "nav_daily", "trades"):
            try:
                n = con.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            except sqlite3.OperationalError:
                print(f"  {table:16s} (테이블 없음)")
                continue
            extra = ""
            if table == "prices_daily" and n:
                r = con.execute("SELECT MIN(date) a, MAX(date) b,"
                                " COUNT(DISTINCT asset_id) k FROM prices_daily").fetchone()
                extra = f"  자산 {r['k']}종  {r['a']} .. {r['b']}"
            if table == "themes" and n:
                k = con.execute("SELECT COUNT(*) AS n FROM themes WHERE active").fetchone()["n"]
                extra = f"  (활성 {k})"
            print(f"  {table:16s} {n:7d} rows{extra}")
    finally:
        con.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dev_seed_design_db")
    ap.add_argument("--users", type=int, default=None,
                    help="로그인시킬 사용자 수 (기본: 시연 계정 전원)")
    ap.add_argument("--skip-seed", action="store_true",
                    help="capstone_demo.db 시드(src.local.seed_capstone) 생략")
    ap.add_argument("--price-source", default=None,
                    help="가격 이력 원본 DB (기본: data/forward_local.db)")
    args = ap.parse_args(argv)

    # --- 환경: start_demo.py 와 동일하게 맞춘다 (로컬 전용) -----------------
    os.environ.update(APP_PROFILE="local", DATABASE_BACKEND="sqlite", CAPSTONE_DEMO="1")
    os.environ.setdefault("AUTH_COOKIE_SECURE", "false")
    os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "false")
    source = Path(args.price_source) if args.price_source else ROOT / "data" / "forward_local.db"
    if source.is_file():
        os.environ.setdefault("DESIGN_PRICE_SOURCE", str(source))
    else:
        print(f"경고: 가격 원본이 없다({source}). 설계 DB 에 가격이 채워지지 않는다.")

    print("=====================================")
    print("PROFILE: LOCAL  (CAPSTONE_DEMO=1)")
    print(f"DESIGN_PRICE_SOURCE: {os.environ.get('DESIGN_PRICE_SOURCE', '(없음)')}")
    print("=====================================")

    # --- 1. 시연 계정 (capstone_demo.db) -----------------------------------
    if not args.skip_seed:
        print("\n[1] capstone_demo.db 시드")
        from src.local import seed_capstone
        seed_capstone.main()
    else:
        print("\n[1] 시드 생략(--skip-seed)")

    from sqlalchemy.engine import make_url
    from src.db.config import get_database_url
    auth_db = Path(make_url(get_database_url()).database).resolve()
    design_db = auth_db.with_name("portfolio_design.db")
    _report(auth_db, "시연 DB (건드리지 않는다)")
    _report(design_db, "설계 DB (채우기 전)")

    # --- 2. 로그인 + 설계 엔드포인트 호출 ----------------------------------
    print("\n[2] 로그인 후 설계 워크스페이스 초기화")
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.local.capstone import EMAILS, PASSWORD

    n_ok = 0
    with TestClient(app) as client:
        wanted = len(EMAILS) if args.users is None else args.users
        for email in EMAILS[:max(1, min(wanted, len(EMAILS)))]:
            res = client.post("/api/v1/auth/login",
                              json={"email": email, "password": PASSWORD})
            if res.status_code != 200:
                print(f"  FAIL login {email}: {res.status_code} {res.text[:120]}")
                continue
            # get_design_db 가 걸린 엔드포인트여야 설계 DB 초기화가 일어난다.
            got = client.get("/api/v1/me/portfolio")
            # 아직 포트폴리오를 안 만든 사용자는 404/409 가 정상이다. 목적은 의존성 실행.
            mark = "OK" if got.status_code < 500 else "ERR"
            if got.status_code < 500:
                n_ok += 1
            print(f"  {mark:3s} {email:26s} /me/portfolio -> {got.status_code}")
            client.cookies.clear()
    print(f"\n  초기화된 사용자: {n_ok}명")

    # --- 3. 결과 ----------------------------------------------------------
    _report(design_db, "설계 DB (채운 후)")
    print("\n다음: python scripts/dev_check_live_prices.py --days 7")
    print("  -> [1] 에 가격이, [2] 에 theme:* 티커가 보이면 성공이다.")
    return 0 if n_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
