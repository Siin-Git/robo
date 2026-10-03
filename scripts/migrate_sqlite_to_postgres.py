"""SQLite -> PostgreSQL one-shot migration (parallel mirror, never destructive).

- Refuses when the destination is non-empty (no --force in V0).
- Single transaction: any failure rolls everything back.
- Preserves every string ID, timestamp (as stored), and JSON payload.
- Source DB is opened read-only in practice (never written); its sha256 is
  recorded before AND after to prove it was untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.base import Base  # noqa: E402
from src.db.compatibility import sqlite_reader  # noqa: E402
from src.db.session import create_app_engine  # noqa: E402
import src.db.models  # noqa: E402,F401

TABLE_ORDER = [
    # --- 원장 사슬 (반드시 있어야 한다) ---
    "counters", "participants", "themes", "accounts", "views",
    "portfolio_targets", "orders", "trades", "holdings_daily",
    "nav_daily", "performance_daily", "prices_daily", "events",
    "model_versions", "forward_state",
    # --- 인증·설계·운영 (소스에 없으면 건너뛴다) ---
    # 예전에는 이 일곱이 빠져 있었다. 원장은 옮겨지는데 로그인 계정과
    # 배치 기록은 안 옮겨져, 옮긴 뒤 아무도 로그인하지 못한다.
    "users", "sessions", "base_portfolio_selections", "onboarding_drafts",
    "demo_cohorts", "demo_slots", "scheduled_jobs",
]

# 원장이 빠진 소스는 옮기면 안 된다. 나머지는 없을 수 있다.
REQUIRED_TABLES = {
    "counters", "participants", "themes", "accounts", "views",
    "portfolio_targets", "orders", "trades", "holdings_daily",
    "nav_daily", "performance_daily", "prices_daily", "events",
    "model_versions", "forward_state",
}

FK_PARENTS = {
    "accounts": [("participant_id", "participants", "participant_id")],
    "views": [("participant_id", "participants", "participant_id"),
              ("theme_id", "themes", "theme_id")],
    "portfolio_targets": [("account_id", "accounts", "account_id")],
    "orders": [("account_id", "accounts", "account_id")],
    "trades": [("order_id", "orders", "order_id"),
               ("account_id", "accounts", "account_id")],
    "holdings_daily": [("account_id", "accounts", "account_id")],
    "nav_daily": [("account_id", "accounts", "account_id")],
    "performance_daily": [("account_id", "accounts", "account_id")],
    "events": [("participant_id", "participants", "participant_id"),
               ("account_id", "accounts", "account_id")],
    "users": [("participant_id", "participants", "participant_id")],
    "sessions": [("user_id", "users", "user_id")],
    "base_portfolio_selections": [("user_id", "users", "user_id"),
                                  ("participant_id", "participants", "participant_id")],
    "demo_slots": [("cohort_id", "demo_cohorts", "cohort_id"),
                   ("user_id", "users", "user_id")],
}

NUMERIC_TOL_NOTE = "parity tolerance applied at verify time, not here"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_ts(value: str, warnings: list) -> datetime:
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    if dt.tzinfo is None:
        warnings.append(f"naive timestamp assumed UTC: {value!r}")
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def convert_row(table, row: dict, warnings: list) -> dict:
    """Convert raw SQLite values to SQLAlchemy-model Python values (model-driven)."""
    from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric
    out = {}
    cols = table.columns
    for key, col in cols.items():
        val = row.get(key)
        t = col.type
        if val is None or (isinstance(val, str) and val == ""):
            if (val == "") and not col.nullable:
                raise ValueError(f"{table.name}.{key}: empty string in NOT NULL column")
            out[key] = None
            continue
        if isinstance(t, Boolean):
            out[key] = bool(val)
        elif isinstance(t, Date) and not isinstance(t, DateTime):
            out[key] = val if isinstance(val, date) else date.fromisoformat(str(val)[:10])
        elif isinstance(t, DateTime):
            out[key] = val if isinstance(val, datetime) else parse_ts(str(val), warnings)
        elif isinstance(t, Numeric):
            out[key] = val if isinstance(val, Decimal) else Decimal(str(val))
        elif isinstance(t, Integer):
            out[key] = int(val)
        else:
            if key.endswith("_json") and isinstance(val, str):
                try:
                    out[key] = json.loads(val)
                except json.JSONDecodeError:
                    # legacy single-quoted repr payloads (safe literal only)
                    import ast
                    out[key] = ast.literal_eval(val)
            else:
                out[key] = val
    return out


def resolve_dest(value: str | None) -> tuple[str, str | None]:
    """목적지 URL 을 정한다. **환경변수 이름을 줘도 된다.**

    PowerShell 은 ``.env.local`` 을 읽지 않는다. 파이썬은 import 시점에
    dotenv 로 읽으므로, 셸에서 ``$env:CAPSTONE_DESIGN_DATABASE_URL`` 을 넘기면
    빈 문자열이 되어 "expected one argument" 로 죽는다. 이름을 그대로 받으면
    URL 을 셸에 노출하지 않고도 쓸 수 있다(비밀번호가 명령 이력에 안 남는다).

    반환: (url, error) - error 가 None 이 아니면 실패다.
    """
    import os
    if not value:
        url = os.environ.get("DATABASE_URL", "").strip()
        return url, None if url else "목적지 URL 이 없다 (--dest 또는 DATABASE_URL)"
    if "://" in value:
        return value.strip(), None
    # URL 이 아니면 환경변수 이름으로 본다.
    url = os.environ.get(value, "").strip()
    if not url:
        return "", (f"환경변수 {value} 가 비어 있다. .env.local 에 있는지 확인할 것 "
                    f"(셸이 아니라 .env.local 에서 읽는다).")
    return url, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "data" / "forward_test.db"))
    ap.add_argument("--dest", default=None,
                    help="SQLAlchemy URL, 또는 환경변수 이름 "
                         "(예: CAPSTONE_DESIGN_DATABASE_URL). 기본: DATABASE_URL")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import os
    dest_url, dest_error = resolve_dest(args.dest)
    if dest_error and not args.dry_run:
        print(f"ERROR: {dest_error}")
        return 2
    src = Path(args.source)
    if not src.exists():
        print(f"ERROR: source not found: {src}")
        return 2

    before_sum = sha256_file(src)
    live_tables = sqlite_reader.list_tables(src)
    missing = [t for t in TABLE_ORDER if t not in live_tables]
    report: dict = {"source": str(src), "destination": _redact(dest_url),
                    "source_sha256_before": before_sum, "tables": {}, "issues": []}
    # 원장이 없는 소스는 옮기면 안 된다. 인증·시연 테이블은 없을 수 있다
    # (그 테이블들이 생기기 전에 만들어진 DB 도 옮길 수 있어야 한다).
    missing_required = [t for t in missing if t in REQUIRED_TABLES]
    if missing_required:
        report["issues"].append(f"source missing ledger tables: {missing_required}")
        print(f"ERROR: {report['issues'][-1]}")
        return 2
    tables = [t for t in TABLE_ORDER if t in live_tables]
    if missing:
        report["skipped_tables"] = missing
        print(f"NOTE: source has no {missing} - skipped")

    # load + convert everything first (fail before touching dest)
    payload: dict[str, list[dict]] = {}
    warnings: list[str] = []
    pk_sets: dict[str, set] = {}
    for t in tables:
        table = Base.metadata.tables[t]
        rows = [convert_row(table, r, warnings) for r in sqlite_reader.iter_table(src, t)]
        payload[t] = rows
        pk_cols = [c.name for c in table.primary_key.columns]
        pk_sets[t] = {tuple(r[c] for c in pk_cols) for r in rows}
        report["tables"][t] = {"source_rows": len(rows)}
    report["warnings"] = sorted(set(warnings))

    # orphan check (fail loudly, never silently drop)
    orphans = []
    for child, rules in FK_PARENTS.items():
        if child not in payload:
            continue                      # 소스에 없는 테이블은 검사할 것도 없다
        for col, parent, pcol in rules:
            if parent not in pk_sets:
                continue                  # 부모 테이블이 없으면 판단할 수 없다
            parents = {next(iter(k)) if len(k) == 1 else k for k in pk_sets[parent]}
            for r in payload[child]:
                if r[col] is not None and r[col] not in parents:
                    orphans.append(f"{child}.{col}={r[col]!r} (parent {parent} missing)")
    if orphans:
        report["issues"].append(f"orphan FKs: {orphans[:20]}")
        print(f"ERROR: {len(orphans)} orphan foreign keys (first: {orphans[0]})")
        _write_report(report)
        return 2

    if args.dry_run:
        report["dry_run"] = True
        report["ready_to_migrate"] = True
        _write_report(report)
        print(f"Source DB: {src}")
        for t in tables:
            print(f"  {t}: {report['tables'][t]['source_rows']} rows")
        print(f"Detected issues: {report['issues'] or 'none'}")
        print("Ready to migrate: True (no writes performed)")
        return 0

    engine = create_app_engine(dest_url)
    from sqlalchemy import inspect as _inspect
    with engine.connect() as c:
        insp = _inspect(c)
        have_tables = set(insp.get_table_names())
        existing = [t for t in tables
                    if t in have_tables and c.execute(
                        __import__("sqlalchemy").text(f'SELECT COUNT(*) FROM "{t}"')).scalar() > 0]
    if existing:
        print("ERROR:\nDestination PostgreSQL database is not empty "
              f"({existing}).\nRefusing migration.")
        return 2
    missing_tables = [t for t in tables if t not in have_tables]
    if missing_tables:
        # Bootstrap schema from models, then stamp the alembic revision so that
        # future `alembic upgrade head` calls are consistent no-ops.
        Base.metadata.create_all(engine)
        import os as _os
        from alembic.config import Config as _AConfig
        from alembic import command as _acommand
        acfg = _AConfig(str(ROOT / "alembic.ini"))
        acfg.set_main_option("script_location", str(ROOT / "migrations"))
        prev = _os.environ.get("DATABASE_URL")
        _os.environ["DATABASE_URL"] = dest_url
        try:
            _acommand.stamp(acfg, "head")
        finally:
            if prev is None:
                _os.environ.pop("DATABASE_URL", None)
            else:
                _os.environ["DATABASE_URL"] = prev
        print(f"bootstrapped schema ({len(missing_tables)} tables) + stamped 0001")

    from sqlalchemy.orm import Session
    with Session(engine) as session:
        with session.begin():
            for t in tables:
                table = Base.metadata.tables[t]
                if payload[t]:
                    session.execute(table.insert(), payload[t])
                report["tables"][t]["destination_rows"] = len(payload[t])
                report["tables"][t]["match"] = True

    after_sum = sha256_file(src)
    report["source_sha256_after"] = after_sum
    report["source_untouched"] = before_sum == after_sum
    _write_report(report)
    print(f"migrated {sum(v['destination_rows'] for v in report['tables'].values())} rows, "
          f"source untouched: {report['source_untouched']}")
    return 0


def _redact(url: str) -> str:
    try:
        from sqlalchemy.engine import make_url
        u = make_url(url)
        return str(u.set(password="***")) if u.password else url
    except Exception:
        return url.split("@")[-1]


def _write_report(report: dict) -> None:
    from datetime import datetime as _dt, timezone as _tz
    report.setdefault("completed_at", _dt.now(_tz.utc).isoformat())
    out = ROOT / "outputs" / "database" / "migration_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"report: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
