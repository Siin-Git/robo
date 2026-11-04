"""Preflight: verify the forward test is safe to launch. No mutations."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.config import load_forward_config, resolve
from src.forward.db import connect
from src.forward.frozen import load_frozen_benchmark
from src.forward.runtime import get_database_path, print_banner
from src.forward.views import resolve_view_schedule


def check_view_schedule() -> tuple[bool, list[str]]:
    cases = [
        # (submitted_at UTC, expected cycle_date, expected effective_at)
        ("2026-09-11T08:59:00+00:00", "2026-09-11", "2026-09-14"),  # Fri 17:59 KST
        ("2026-09-11T09:01:00+00:00", "2026-09-18", "2026-09-21"),  # Fri 18:01 KST
        ("2026-09-12T00:00:00+00:00", "2026-09-18", "2026-09-21"),  # Saturday
        ("2026-09-13T12:00:00+00:00", "2026-09-18", "2026-09-21"),  # Sunday
        ("2026-09-09T00:00:00+00:00", "2026-09-11", "2026-09-10"),  # Wed -> Thu
    ]
    bad = []
    for ts, cyc, eff in cases:
        s = resolve_view_schedule(ts)
        if s["cycle_date"] != cyc or s["effective_at"] != eff:
            bad.append(f"{ts}: got {(s['cycle_date'], s['effective_at'])}, want {(cyc, eff)}")
    return (not bad, bad)


def run_checks(con, cfg: dict) -> tuple[bool, list[str], dict]:
    """All preflight checks without printing. Returns (ok, lines, details)."""
    ft = cfg["forward_test"]
    lines: list[str] = []
    details: dict = {}
    ok = True

    def rep(name: str, passed: bool, detail: str = ""):
        nonlocal ok
        if not passed:
            ok = False
        lines.append(f"{name}: {'PASS' if passed else 'FAIL'}{(' ' + detail) if detail else ''}")

    try:
        frozen_w, frozen_meta = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
        rep("Benchmark frozen", True, ft["benchmark_version"])
    except Exception as e:
        frozen_w, frozen_meta = None, {}
        rep("Benchmark frozen", False, str(e))
    n_themes = con.execute("SELECT COUNT(*) c FROM themes WHERE active").fetchone()["c"] \
        if _has(con, "themes") else 0
    rep("Theme registry", n_themes >= 1, f"{n_themes} active")
    demo_p = con.execute("SELECT COUNT(*) c FROM participants WHERE display_name LIKE 'Demo %'").fetchone()["c"] \
        if _has(con, "participants") else 0
    demo_e = con.execute("SELECT COUNT(*) c FROM events WHERE payload_json LIKE '%Demo %'").fetchone()["c"] \
        if _has(con, "events") else 0
    rep("Demo contamination", demo_p == 0 and demo_e == 0,
        "NONE" if demo_p == 0 and demo_e == 0 else f"participants={demo_p} events={demo_e}")
    n_trades = con.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] if _has(con, "trades") else 0
    n_nav = con.execute("SELECT COUNT(*) c FROM nav_daily").fetchone()["c"] if _has(con, "nav_daily") else 0
    rep("Existing live history", True, f"trades={n_trades} nav={n_nav}")
    vs_ok, vs_bad = check_view_schedule()
    rep("View schedule test", vs_ok, "; ".join(vs_bad))
    bad_px = con.execute("SELECT COUNT(*) c FROM trades t JOIN orders o ON t.order_id = o.order_id"
                         " WHERE t.execution_at < o.effective_at").fetchone()["c"] \
        if _has(con, "trades") and _has(con, "orders") else 0
    rep("Execution timing test", bad_px == 0, f"{bad_px} violations" if bad_px else "")
    lastpx = con.execute("SELECT MAX(date) m FROM prices_daily").fetchone()["m"] \
        if _has(con, "prices_daily") else None
    fresh = lastpx is not None and (date.today() - date.fromisoformat(lastpx)).days <= int(
        cfg["forward_test"].get("stale_price_days", 14)) + 7
    rep("Market data freshness", fresh, f"latest={lastpx}")
    acct_ok, acct_bad = True, []
    if _has(con, "nav_daily"):
        for a in con.execute("SELECT account_id FROM accounts").fetchall():
            h = con.execute("SELECT date, SUM(weight) s FROM holdings_daily WHERE account_id = ?"
                            " GROUP BY date ORDER BY date DESC LIMIT 1",
                            (a["account_id"],)).fetchone()
            n = con.execute("SELECT nav, cash_balance FROM nav_daily WHERE account_id = ?"
                            " ORDER BY date DESC LIMIT 1", (a["account_id"],)).fetchone()
            if h and n and abs((h["s"] + n["cash_balance"] / n["nav"]) - 1.0) > 1e-6:
                acct_ok = False
                acct_bad.append(a["account_id"])
    rep("DB accounting issue", acct_ok, "; ".join(acct_bad))
    # lifecycle invariants (§16)
    from src.forward.state import canonical_dates, check_invariants
    inv = check_invariants(canonical_dates(con, frozen_meta or {}))
    rep("Lifecycle invariants", not inv, "; ".join(inv))
    details.update({"trades": n_trades, "nav": n_nav, "latest_prices": lastpx,
                    "frozen_meta": frozen_meta or {}})
    return ok, lines, details


def main() -> int:
    profile = print_banner()
    cfg = load_forward_config()
    ft = cfg["forward_test"]
    dbp = get_database_path()
    con = connect(dbp)
    ok, lines, details = run_checks(con, cfg)
    fm = details.get("frozen_meta", {})
    from src.forward.state import get_state
    inception = get_state(con, "forward_test_inception_at")
    first_exec = get_state(con, "first_execution_at")

    print("")
    print("FORWARD TEST PREFLIGHT")
    print("")
    print(f"Profile:\n{profile.upper()}")
    print("")
    print(f"Benchmark:\n{ft['benchmark_version']}")
    print("")
    print(f"Benchmark Model Date:\n{(fm.get('run_timestamp', '') or '')[:10]}")
    print("")
    print(f"Benchmark Snapshot Date:\n{fm.get('data_end')}")
    print("")
    print(f"Forward Test Inception:\n{inception or 'NOT STARTED'}")
    print("")
    print(f"First Execution:\n{first_exec or 'NOT STARTED'}")
    print("")
    print(f"Demo contamination:\n{'NONE' if 'Demo contamination: PASS' in str(lines) else 'FOUND'}")
    print("")
    for ln in lines:
        print(ln)
    print("")
    print(f"READY TO LAUNCH: {'YES' if ok else 'NO'}")
    return 0 if ok else 1


def _has(con, table: str) -> bool:
    return con.execute("SELECT COUNT(*) c FROM sqlite_master WHERE name = ?",
                       (table,)).fetchone()["c"] > 0


if __name__ == "__main__":
    raise SystemExit(main())
