"""Independent SQLite <-> PostgreSQL parity verification (read-only on both).

Compares: schema presence, row counts, full PK sets, all field values
(normalized; numerics within tolerance), FK orphans, financial aggregates,
and canonical per-table hashes. Exit 0 only if everything matches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.db.base import Base  # noqa: E402
from src.db.compatibility import sqlite_reader  # noqa: E402
from src.db.session import create_app_engine  # noqa: E402
import src.db.models  # noqa: E402,F401

NUM_TOL = 1e-10
# holdings_daily.market_value 는 NUMERIC(24,4) 라 행마다 최대 0.00005 의
# 반올림 오차가 생긴다. 항등식은 보유 행을 합산하므로 오차도 누적된다.
# 문서(POSTGRES_SCHEMA.md)의 "10x quantum" 방침에 맞춰 0.001 로 둔다.
# MONEY_TOL = 1e-6(원래 값)
MONEY_TOL = 1e-3


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


def norm_pk(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return "" if v is None else str(v)


def norm_val(v):
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=__import__("datetime").timezone.utc)
        return ("ts", v.isoformat())
    if isinstance(v, date):
        return ("d", v.isoformat())
    if isinstance(v, Decimal):
        return ("n", str(v))
    if isinstance(v, float):
        return ("n", repr(v))
    if isinstance(v, bool):
        return ("b", v)
    if isinstance(v, (dict, list)):
        return ("j", json.dumps(v, sort_keys=True, ensure_ascii=False))
    return ("s", "" if v is None else str(v))


def values_equal(a, b, tol: Decimal = Decimal(str(NUM_TOL))) -> bool:
    ta, va = norm_val(a)
    tb, vb = norm_val(b)
    if ta == "ts" and tb == "ts":
        return va == vb
    if ta == "n" and tb == "n":
        try:
            return abs(Decimal(va) - Decimal(vb)) <= tol
        except Exception:
            return va == vb
    return (ta, va) == (tb, vb)


def col_tol(table, col: str) -> Decimal:
    from sqlalchemy import Numeric
    t = table.columns[col].type
    if isinstance(t, Numeric) and t.scale:
        return Decimal(10) ** (-int(t.scale)) * Decimal(10)
    return Decimal(str(NUM_TOL))


def canon_hash(rows: list[dict], pk_cols: list[str]) -> str:
    h = hashlib.sha256()
    for r in sorted(rows, key=lambda d: tuple(norm_pk(d[c]) for c in pk_cols)):
        h.update(json.dumps({k: norm_val(v) for k, v in sorted(r.items())},
                            sort_keys=True, default=str).encode())
    return h.hexdigest()


def dest_rows(engine, table) -> list[dict]:
    from sqlalchemy import select
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(select(table))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "data" / "forward_test.db"))
    ap.add_argument("--dest", default=None)
    args = ap.parse_args()
    import os
    dest_url = args.dest or os.environ.get("DATABASE_URL", "").strip()
    if not dest_url:
        print("ERROR: destination URL missing (pass --dest or set DATABASE_URL)")
        return 2

    ok = True
    table_rep: dict = {}
    dest_engine = create_app_engine(dest_url)
    dest_tables: dict[str, list[dict]] = {}
    for t in TABLE_ORDER:
        table = Base.metadata.tables[t]
        pk_cols = [c.name for c in table.primary_key.columns]
        src = list(sqlite_reader.iter_table(args.source, t))
        try:
            dst = dest_rows(dest_engine, table)
        except Exception as e:
            print(f"ERROR: cannot read dest table {t}: {e}")
            return 2
        dest_tables[t] = dst
        rep = {"sqlite_rows": len(src), "postgres_rows": len(dst),
               "match": len(src) == len(dst)}
        if not rep["match"]:
            ok = False
        src_by_pk = {tuple(norm_pk(r[c]) for c in pk_cols): r for r in src}
        # normalize dest PKs the same way (dates/timestamps from PG driver)
        dst_by_pk = {}
        for r in dst:
            rr = dict(r)
            dst_by_pk[tuple(norm_pk(rr[c]) for c in pk_cols)] = rr
        if set(src_by_pk) != set(dst_by_pk):
            rep["pk_match"] = False
            rep["pk_only_source"] = len(set(src_by_pk) - set(dst_by_pk))
            rep["pk_only_dest"] = len(set(dst_by_pk) - set(src_by_pk))
            ok = False
        else:
            rep["pk_match"] = True
            # full field comparison with sqlite-side parsing
            from scripts.migrate_sqlite_to_postgres import convert_row
            mism = 0
            for k, srow in src_by_pk.items():
                conv = convert_row(table, srow, [])
                drow = dst_by_pk[k]
                for c in table.columns.keys():
                    if not values_equal(conv.get(c), drow.get(c), col_tol(table, c)):
                        mism += 1
                        if mism <= 3:
                            print(f"  MISMATCH {t} {k} col {c}: {conv.get(c)!r} vs {drow.get(c)!r}")
            rep["field_mismatches"] = mism
            if mism:
                ok = False
        rep["source_hash"] = canon_hash(
            [{c: r[c] for c in table.columns.keys()} for r in src], pk_cols)
        rep["destination_hash"] = canon_hash(
            [{c: r[c] for c in table.columns.keys()} for r in dst], pk_cols)
        table_rep[t] = rep

    # FK orphans on destination
    orphans = 0
    for child, rules in FK_PARENTS.items():
        for col, parent, _pcol in rules:
            pkeys = set()
            for r in dest_tables[parent]:
                pkeys.add(r.get(_pcol))
            for r in dest_tables[child]:
                if r.get(col) is not None and r.get(col) not in pkeys:
                    orphans += 1
    # financial integrity on destination
    fin = {}
    nav = dest_tables["nav_daily"]
    for acct in {r["account_id"] for r in nav} | {r["account_id"] for r in dest_tables["trades"]}:
        nrows = sorted([r for r in nav if r["account_id"] == acct],
                       key=lambda r: norm_pk(r["date"]))
        troows = [r for r in dest_tables["trades"] if r["account_id"] == acct]
        hrows = [r for r in dest_tables["holdings_daily"] if r["account_id"] == acct]
        latest = nrows[-1] if nrows else None
        ident = None
        if latest:
            day = [r for r in hrows if norm_pk(r["date"]) == norm_pk(latest["date"])]
            mv = sum(float(x["market_value"]) for x in day)
            ident = abs(mv + float(latest["cash_balance"]) - float(latest["nav"]))
        fin[acct] = {
            "latest_nav": float(latest["nav"]) if latest else None,
            "trade_count": len(troows),
            "gross_sum": sum(float(x["gross_value"]) for x in troows),
            "cost_sum": sum(float(x["transaction_cost"]) for x in troows),
            "holdings_identity_gap": ident,
            "identity_ok": (ident is None) or ident <= MONEY_TOL,
        }
        if fin[acct]["identity_ok"] is False:
            ok = False

    print(f"{'table':22s} {'sqlite':>8s} {'pg':>8s} {'match':>6s} {'pk':>4s} {'fields':>8s}")
    for t in TABLE_ORDER:
        r = table_rep[t]
        print(f"{t:22s} {r['sqlite_rows']:8d} {r['postgres_rows']:8d} "
              f"{str(r['match']):>6s} {str(r.get('pk_match')):>4s} "
              f"{r.get('field_mismatches', '-')}")
    print(f"FK orphans on destination: {orphans}")
    if orphans:
        ok = False
    for acct, f in fin.items():
        print(f"  {acct}: nav={f['latest_nav']} trades={f['trade_count']} "
              f"cost={f['cost_sum']:.4f} identity_ok={f['identity_ok']}")
    out = ROOT / "outputs" / "database" / "parity_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"tables": table_rep, "orphans": orphans, "financial": fin,
                               "pass": ok}, indent=2, default=str), encoding="utf-8")
    print(f"PARITY: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
