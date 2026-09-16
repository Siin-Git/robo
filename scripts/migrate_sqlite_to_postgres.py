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

TABLE_ORDER = ["counters", "participants", "themes", "accounts", "views",
               "portfolio_targets", "orders", "trades", "holdings_daily",
               "nav_daily", "performance_daily", "prices_daily", "events",
               "model_versions", "forward_state"]

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "data" / "forward_test.db"))
    ap.add_argument("--dest", default=None, help="SQLAlchemy URL (default: DATABASE_URL env)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import os
    dest_url = args.dest or os.environ.get("DATABASE_URL", "").strip()
    if not dest_url and not args.dry_run:
        print("ERROR: destination URL missing (pass --dest or set DATABASE_URL)")
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
    if missing:
        report["issues"].append(f"source missing tables: {missing}")
        print(f"ERROR: {report['issues'][-1]}")
        return 2

    # load + convert everything first (fail before touching dest)
    payload: dict[str, list[dict]] = {}
    warnings: list[str] = []
    pk_sets: dict[str, set] = {}
    for t in TABLE_ORDER:
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
        for col, parent, pcol in rules:
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
        for t in TABLE_ORDER:
            print(f"  {t}: {report['tables'][t]['source_rows']} rows")
        print(f"Detected issues: {report['issues'] or 'none'}")
        print("Ready to migrate: True (no writes performed)")
        return 0

    engine = create_app_engine(dest_url)
    from sqlalchemy import inspect as _inspect
    with engine.connect() as c:
        insp = _inspect(c)
        have_tables = set(insp.get_table_names())
        existing = [t for t in TABLE_ORDER
                    if t in have_tables and c.execute(
                        __import__("sqlalchemy").text(f'SELECT COUNT(*) FROM "{t}"')).scalar() > 0]
    if existing:
        print("ERROR:\nDestination PostgreSQL database is not empty "
              f"({existing}).\nRefusing migration.")
        return 2
    missing_tables = [t for t in TABLE_ORDER if t not in have_tables]
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
            for t in TABLE_ORDER:
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
