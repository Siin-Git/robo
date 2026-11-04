"""캡스톤 2단계: PostgreSQL 두 곳에 스키마를 올린다.

캡스톤 모드는 DB 가 둘이다.

  인증·비교 시연 DB  <- DATABASE_URL
  설계·운용 기록 DB  <- CAPSTONE_DESIGN_DATABASE_URL

둘 다 같은 스키마를 쓴다(테이블 22개). 어느 쪽에 무엇이 들어가는지는
코드가 정하고, 여기서는 **양쪽에 테이블을 만들기만** 한다.

  python scripts/setup_postgres.py --auth-url ... --design-url ...          # 미리보기
  python scripts/setup_postgres.py --auth-url ... --design-url ... --apply  # 실행

URL 을 생략하면 환경변수(DATABASE_URL / CAPSTONE_DESIGN_DATABASE_URL)에서 읽는다.
비밀번호는 출력하지 않는다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 환경변수를 읽기 **전에** .env / .env.local 을 로드한다.
# src/db/config.py 가 import 시점에 dotenv 를 읽는 단일 창구다. 이것을
# 함수 안에서만 import 하면, 아래 기본값을 정할 때 아직 로드가 안 돼서
# ".env.local 에 넣었는데 못 찾는다" 가 된다. 프로세스 환경변수가 항상 우선.
from src.db import config as _dbconfig  # noqa: E402,F401


def safe(url: str) -> str:
    """로그에 찍어도 되는 형태. 사용자·비밀번호는 읽지 않는다."""
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        if p.port:
            host = f"{host}:{p.port}"
        db = p.path.lstrip("/") or "(이름 없음)"
        return f"{p.scheme}://{host}/{db}"
    except Exception:  # noqa: BLE001
        return "(URL 파싱 실패)"


def identity(url: str) -> tuple:
    p = urlsplit(url)
    return (p.hostname, p.port, p.path)


def upgrade(url: str) -> tuple[bool, str]:
    """이 URL 에 alembic upgrade head 를 돌린다."""
    from src.db.config import normalize_pg_url
    url = normalize_pg_url(url)
    env = dict(os.environ, DATABASE_URL=url, DATABASE_BACKEND="postgres",
               PYTHONPATH=str(ROOT))
    # 캡스톤 변수가 남아 있으면 env.py 가 엉뚱한 곳을 볼 수 있다.
    env.pop("CAPSTONE_DESIGN_DATABASE_URL", None)
    env.pop("CAPSTONE_DEMO", None)
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def tables(url: str) -> list[str]:
    from sqlalchemy import create_engine, inspect
    from src.db.config import normalize_pg_url
    engine = create_engine(normalize_pg_url(url))
    try:
        return sorted(t for t in inspect(engine).get_table_names()
                      if t != "alembic_version")
    finally:
        engine.dispose()


def expected() -> set[str]:
    from src.db.base import Base
    import src.db.models  # noqa: F401
    return set(Base.metadata.tables)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="setup_postgres")
    ap.add_argument("--auth-url", default=os.environ.get("DATABASE_URL", "").strip() or None,
                    help="인증·비교 시연 DB (기본: DATABASE_URL)")
    ap.add_argument("--design-url",
                    default=os.environ.get("CAPSTONE_DESIGN_DATABASE_URL", "").strip() or None,
                    help="설계·운용 기록 DB (기본: CAPSTONE_DESIGN_DATABASE_URL)")
    ap.add_argument("--apply", action="store_true", help="실제로 올린다(기본은 미리보기)")
    args = ap.parse_args(argv)

    if not args.auth_url or not args.design_url:
        missing = [n for n, v in (("DATABASE_URL", args.auth_url),
                                  ("CAPSTONE_DESIGN_DATABASE_URL", args.design_url))
                   if not v]
        print(f"URL 이 없다: {', '.join(missing)}")
        print("--auth-url / --design-url 로 직접 주거나 .env.local 에 넣을 것.")
        for name in (".env.local", ".env"):
            f = ROOT / name
            print(f"  {name}: {'있음' if f.is_file() else '없음'}")
        return 2

    print("=====================================")
    print(f"AUTH   : {safe(args.auth_url)}")
    print(f"DESIGN : {safe(args.design_url)}")
    print("=====================================\n")

    if identity(args.auth_url) == identity(args.design_url):
        print("두 URL 이 같은 데이터베이스를 가리킨다. 시연 데이터와 운용 기록이 "
              "같은 테이블에 섞인다. 서로 다른 데이터베이스를 지정할 것.")
        return 1

    want = expected()
    print(f"올릴 테이블: {len(want)}개\n")

    if not args.apply:
        print("미리보기다. 실제로 올리려면 --apply 를 붙일 것.")
        return 0

    problems = []
    for label, url in (("AUTH", args.auth_url), ("DESIGN", args.design_url)):
        print(f"[{label}] alembic upgrade head ...")
        ok, output = upgrade(url)
        if not ok:
            print(output)
            problems.append(f"{label}: 마이그레이션 실패")
            continue
        got = set(tables(url))
        missing = sorted(want - got)
        print(f"[{label}] 테이블 {len(got)}개"
              + (f"  ★ 빠짐: {missing}" if missing else "  (모두 생성됨)"))
        if missing:
            problems.append(f"{label}: 테이블 누락 {missing}")

    if problems:
        print("\n" + "\n".join(problems))
        return 1

    print("\n두 DB 모두 준비됐다. 다음:")
    print("  3단계 - python scripts/migrate_sqlite_to_postgres.py "
          "--source data/portfolio_design.db --dest <DESIGN URL>")
    print("  4단계 - python scripts/verify_db_parity.py "
          "--source data/portfolio_design.db --dest <DESIGN URL>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
