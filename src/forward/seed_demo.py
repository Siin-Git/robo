"""Seed demo participants (explicit runs only, never automatic)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.accounts import ensure_personal_accounts, place_target_orders, record_target, versions_from_cfg
from src.forward.config import load_forward_config, resolve
from src.forward.db import connect, now_iso
from src.forward.runtime import get_database_path, get_runtime_profile, print_banner
from src.forward.frozen import load_frozen_benchmark
from src.forward.participants import add_participant
from src.forward.views import submit_view

DEMO = [
    ("Demo Alice", [("semiconductor", "AI server capex cycle"), ("ai", "enterprise adoption")]),
    ("Demo Bob", [("nuclear", "baseload demand growth")]),
    ("Demo Carol", [("defense", "order backlog visibility"), ("cybersecurity", "spending resilience")]),
]


def main() -> int:
    profile = print_banner()
    if profile == "live":
        print("ERROR:\nDemo seeding is not allowed in LIVE profile.")
        return 2
    from src.forward.db import init_db
    _probe = connect(get_database_path())
    has = _probe.execute("SELECT COUNT(*) c FROM sqlite_master WHERE name='participants'").fetchone()["c"]
    _probe.close()
    if not has:
        from src.forward.init_forward_test import main as _init_main
        rc = _init_main()
        if rc != 0:
            return rc
    cfg = load_forward_config()
    ft = cfg["forward_test"]
    con = connect(get_database_path())
    frozen_w, _ = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
    versions = versions_from_cfg(cfg)
    join = ft["model_reference_date"]
    for name, views in DEMO:
        pid = add_participant(con, name, join, ft["benchmark_version"])
        core_id, pers_id = ensure_personal_accounts(con, pid, join, cfg, ft["benchmark_version"])
        for aid in (core_id, pers_id):
            record_target(con, aid, dict(frozen_w), join, "core", versions,
                          ft["benchmark_version"], pid)
            place_target_orders(con, aid, dict(frozen_w), f"{join}T00:00:00+00:00", join,
                                ft["benchmark_version"], pid, kind="INCEPTION_EXECUTION")
        for theme, reason in views:
            r = submit_view(con, pid, theme, now_iso(), reason,
                            ft["theme_universe_version"], ft["benchmark_version"],
                            int(ft["weekly_view"]["max_active_themes"]),
                            ft["view_schedule"]["cutoff_time"])
            print(pid, name, r)
    con.commit()
    print("seeded 3 demo participants (views pending next-session execution)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
