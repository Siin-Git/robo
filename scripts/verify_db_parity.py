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
    args = ap.parse_args()
    import os
    dest_url, dest_error = resolve_dest(args.dest)
    if dest_error:
        print(f"ERROR: {dest_error}")
        return 2

    ok = True
    table_rep: dict = {}
    dest_engine = create_app_engine(dest_url)
    dest_tables: dict[str, list[dict]] = {}
    # 소스에 없는 테이블은 비교 대상이 아니다. 원장이 없으면 검증 자체가 의미 없다.
    live = set(sqlite_reader.list_tables(args.source))
    missing_required = sorted(REQUIRED_TABLES - live)
    if missing_required:
        print(f"ERROR: source missing ledger tables: {missing_required}")
        return 2
    tables = [t for t in TABLE_ORDER if t in live]
    skipped = [t for t in TABLE_ORDER if t not in live]
    if skipped:
        print(f"NOTE: source has no {skipped} - not compared")
    for t in tables:
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
        if child not in dest_tables:
            continue                      # 소스에 없던 테이블
        for col, parent, _pcol in rules:
            if parent not in dest_tables:
                continue
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
        # 회계 항등식(보유 평가액 + 현금 = NAV)은 **원장이 있는 계좌**에만 적용된다.
        #
        # 시연 DB(capstone_demo.db)의 NAV 는 차트용 가상 경로다. 보유도 체결도
        # 없고 cash_balance 도 0이라, 식에 넣으면 gap 이 NAV 값 그대로 나와
        # 언제나 실패한다. 애초에 만족하도록 만든 데이터가 아니다.
        #
        # 보유가 하나라도 있으면(또는 체결이 있으면) 그때는 반드시 맞아야 하므로
        # 검사를 건너뛰지 않는다. 그래야 진짜 불일치를 놓치지 않는다.
        has_ledger = bool(hrows) or bool(troows)
        if latest and has_ledger:
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
    for t in tables:
        r = table_rep[t]
        print(f"{t:22s} {r['sqlite_rows']:8d} {r['postgres_rows']:8d} "
              f"{str(r['match']):>6s} {str(r.get('pk_match')):>4s} "
              f"{r.get('field_mismatches', '-')}")
    print(f"FK orphans on destination: {orphans}")
    if orphans:
        ok = False
    checked = [a for a, f in fin.items() if f["holdings_identity_gap"] is not None]
    skipped = [a for a in fin if a not in checked]
    for acct in sorted(fin):
        f = fin[acct]
        state = "identity_ok=True" if f["holdings_identity_gap"] is None else (
            f"identity_ok={f['identity_ok']}")
        if f["holdings_identity_gap"] is None:
            state = "identity=n/a (원장 없음)"
        print(f"  {acct}: nav={f['latest_nav']} trades={f['trade_count']} "
              f"cost={f['cost_sum']:.4f} {state}")
    print(f"회계 항등식: {len(checked)}개 계좌 검사"
          + (f", {len(skipped)}개는 원장이 없어 해당 없음" if skipped else ""))
    out = ROOT / "outputs" / "database" / "parity_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"tables": table_rep, "orphans": orphans, "financial": fin,
                               "pass": ok}, indent=2, default=str), encoding="utf-8")
    print(f"PARITY: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
