"""개발용: PostgreSQL 대상 DB의 데이터 테이블을 비운다 (스키마는 유지).

이전(migrate) 정확성을 순수하게 검증하려면 대상이 비어 있어야 한다.
alembic_version 은 건드리지 않으므로 `alembic upgrade head` 를 다시 할 필요가 없다.

    $env:DATABASE_BACKEND = "postgres"
    python scripts/dev_reset_pg.py --yes

이후
    python scripts/migrate_sqlite_to_postgres.py --source data/forward_local.db
    python scripts/verify_db_parity.py --source data/forward_local.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.config import get_backend, get_database_url  # noqa: E402  (.env 로드 포함)

TABLES = [
    "nav_daily", "holdings_daily", "performance_daily", "trades", "orders",
    "portfolio_targets", "views", "accounts", "participants", "events",
    "prices_daily", "themes", "counters", "model_versions", "forward_state",
]


def main() -> int:
    ap = argparse.ArgumentParser(prog="dev_reset_pg")
    ap.add_argument("--yes", action="store_true", help="확인 없이 실행")
    args = ap.parse_args()

    if get_backend() != "postgres":
        print("ERROR: DATABASE_BACKEND=postgres 에서만 실행한다.")
        return 2
    url = get_database_url("postgres")
    shown = url.split("@")[-1] if "@" in url else url
    print(f"대상: {shown}")
    print(f"비울 테이블 {len(TABLES)}개 (스키마와 alembic_version 은 유지)")
    if not args.yes:
        if input("정말 비울까요? 'yes' 입력: ").strip() != "yes":
            print("취소했다.")
            return 1

    from sqlalchemy import create_engine, text
    engine = create_engine(url)
    with engine.connect() as c:
        c.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
        c.commit()
        for t in ("prices_daily", "nav_daily", "events"):
            n = c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  {t}: {n}행")
    print("비우기 완료.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
