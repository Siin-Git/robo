"""Participant CLI: add / deactivate / reactivate / list (dynamic N, no hardcoding)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.accounts import ensure_personal_accounts, place_target_orders, record_target, versions_from_cfg
from src.forward.config import load_forward_config, resolve
from src.forward.db import connect
from src.forward.runtime import get_database_path, print_banner
from src.forward.frozen import load_frozen_benchmark
from src.forward.participants import (add_participant, deactivate_participant, list_participants,
                                      reactivate_participant)


def main() -> int:
    print_banner()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--name", required=True)
    a.add_argument("--join-date", required=True)
    d = sub.add_parser("deactivate")
    d.add_argument("--id", required=True)
    d.add_argument("--leave-date", required=True)
    r = sub.add_parser("reactivate")
    r.add_argument("--id", required=True)
    sub.add_parser("list")
    args = ap.parse_args()

    cfg = load_forward_config()
    ft = cfg["forward_test"]
    con = connect(get_database_path())
    if args.cmd == "add":
        pid = add_participant(con, args.name, args.join_date, ft["benchmark_version"])
        core_id, pers_id = ensure_personal_accounts(con, pid, args.join_date, cfg,
                                                   ft["benchmark_version"])
        frozen_w, _ = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
        versions = versions_from_cfg(cfg)
        from src.forward.state import live_orders_blocked
        blocked, reason = live_orders_blocked(con)
        for aid in (core_id, pers_id):
            record_target(con, aid, dict(frozen_w), args.join_date, "core", versions,
                          ft["benchmark_version"], pid)
            if blocked:
                print(f"  {aid}: orders deferred ({reason}); first daily run post-launch"
                      " will create them.")
            else:
                place_target_orders(con, aid, dict(frozen_w), f"{args.join_date}T00:00:00+00:00",
                                    args.join_date, ft["benchmark_version"], pid,
                                    kind="INCEPTION_EXECUTION")
        con.commit()
        print(f"added {pid} ({args.name}); accounts {core_id}, {pers_id}")
    elif args.cmd == "deactivate":
        deactivate_participant(con, args.id, args.leave_date, ft["benchmark_version"])
        print(f"deactivated {args.id}")
    elif args.cmd == "reactivate":
        reactivate_participant(con, args.id, ft["benchmark_version"])
        print(f"reactivated {args.id}")
    elif args.cmd == "list":
        for p in list_participants(con):
            print(p["participant_id"], p["display_name"], p["status"], p["join_date"],
                  p["leave_date"] or "-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
