"""DB status overview (read-only). Usage: python -m src.db.status"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.db.config import get_backend, get_database_url  # noqa: E402


def main() -> int:
    print("SQLite Source:")
    sqlite_path = ROOT / "data" / "forward_test.db"
    print("OK" if sqlite_path.exists() else f"MISSING ({sqlite_path})")
    print("")
    print("PostgreSQL:")
    url = None
    try:
        import os
        url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL not set")
        from sqlalchemy import create_engine, text
        eng = create_engine(url, connect_args={"connect_timeout": 5})
        with eng.connect() as c:
            rev = None
            try:
                rev = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except Exception:
                rev = "(no alembic revision)"
            print(f"CONNECTED ({_redact(url)})")
            print("")
            print("Schema Revision:")
            print(rev)
    except Exception as e:
        print(f"NOT CONNECTED ({e})")
        print("")
        print("Schema Revision:")
        print("unknown")
    print("")
    print("Parity:")
    prep = ROOT / "outputs" / "database" / "parity_report.json"
    if prep.exists():
        try:
            print("PASS" if json.loads(prep.read_text())["pass"] else "FAIL")
        except Exception:
            print("UNKNOWN")
    else:
        print("NOT RUN")
    print("")
    print("Operational Primary:")
    print("SQLITE")
    return 0


def _redact(url: str) -> str:
    try:
        from sqlalchemy.engine import make_url
        u = make_url(url)
        return str(u.set(password="***")) if u.password else url
    except Exception:
        return url.split("@")[-1]


if __name__ == "__main__":
    raise SystemExit(main())
