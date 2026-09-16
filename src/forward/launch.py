"""Explicit forward-test launch. Sets forward_test_inception_at = now (Asia/Seoul).

Usage:
    APP_PROFILE=live python -m src.forward.launch

Launch is a one-way gate: no orders, executions, or NAV may predate it, and a
second launch is refused. Demo/validation profiles cannot launch.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.config import load_forward_config, resolve
from src.forward.db import connect, log_event
from src.forward.frozen import load_frozen_benchmark
from src.forward.preflight import run_checks
from src.forward.runtime import get_database_path, get_runtime_profile, print_banner
from src.forward.state import canonical_dates, get_state, now_seoul_iso, set_state_once


def main() -> int:
    profile = print_banner()
    if profile != "live":
        print("ERROR:\nForward-test launch is only allowed in LIVE profile.")
        return 2
    cfg = load_forward_config()
    ft = cfg["forward_test"]
    con = connect(get_database_path())
    if get_state(con, "forward_test_inception_at") is not None:
        print("ERROR:\nForward test has already been launched.\n"
              "Refusing to overwrite the existing inception timestamp.")
        return 2
    if get_state(con, "first_execution_at") is not None:
        print("ERROR:\nfirst_execution_at already recorded; launch state inconsistent.")
        return 2
    frozen_w, frozen_meta = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    if ft["benchmark_version"] != "CORE_V0.3":
        print("ERROR:\nBenchmark is not CORE_V0.3.")
        return 2
    ok, lines, _ = run_checks(con, cfg)
    for ln in lines:
        print(ln)
    if not ok:
        print("ERROR:\nPreflight did not pass; launch forbidden.")
        return 2
    # Demo contamination is a hard launch blocker (checked again explicitly).
    demo_p = con.execute("SELECT COUNT(*) c FROM participants WHERE display_name LIKE 'Demo %'"
                         ).fetchone()["c"] if _has(con, "participants") else 0
    if demo_p:
        print("ERROR:\nDemo participants present in live DB; launch forbidden.")
        return 2
    ts = now_seoul_iso()
    set_state_once(con, "forward_test_inception_at", ts)
    log_event(con, "FORWARD_TEST_LAUNCHED", ft["benchmark_version"], payload={
        "forward_test_inception_at": ts,
        "benchmark_version": ft["benchmark_version"],
        "benchmark_model_date": (frozen_meta.get("run_timestamp", "") or "")[:10],
        "benchmark_snapshot_date": frozen_meta.get("data_end"),
        "theme_universe_version": ft["theme_universe_version"]})
    con.commit()
    d = canonical_dates(con, frozen_meta)
    print("")
    print(f"FORWARD TEST LAUNCHED at {ts}")
    print(f"benchmark_model_date:      {d['benchmark_model_date']}")
    print(f"benchmark_snapshot_date:   {d['benchmark_snapshot_date']}")
    print(f"forward_test_inception_at: {d['forward_test_inception_at']}")
    print(f"first_execution_at:        {d['first_execution_at']}")
    return 0


def _has(con, table: str) -> bool:
    return con.execute("SELECT COUNT(*) c FROM sqlite_master WHERE name = ?",
                       (table,)).fetchone()["c"] > 0


if __name__ == "__main__":
    raise SystemExit(main())
