"""Views CLI: submit / close / list."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.config import load_forward_config, resolve
from src.forward.db import connect
from src.forward.runtime import get_database_path, print_banner
from src.forward.views import active_views, close_view, submit_view


def main() -> int:
    print_banner()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--participant", required=True)
    s.add_argument("--theme", required=True)
    s.add_argument("--reason", default="")
    s.add_argument("--submitted-at", default=None)
    c = sub.add_parser("close")
    c.add_argument("--participant", required=True)
    c.add_argument("--theme", required=True)
    c.add_argument("--closed-at", default=None)
    l = sub.add_parser("list")
    l.add_argument("--participant", default=None)
    args = ap.parse_args()

    cfg = load_forward_config()
    ft = cfg["forward_test"]
    con = connect(get_database_path())
    from src.forward.db import now_iso
    if args.cmd == "submit":
        r = submit_view(con, args.participant, args.theme, args.submitted_at or now_iso(),
                        args.reason, ft["theme_universe_version"], ft["benchmark_version"],
                        int(ft["weekly_view"]["max_active_themes"]),
                        ft["view_schedule"]["cutoff_time"])
        print(r)
    elif args.cmd == "close":
        print(close_view(con, args.participant, args.theme, args.closed_at or now_iso(),
                         ft["benchmark_version"]))
    elif args.cmd == "list":
        q = "SELECT * FROM views"
        params: tuple = ()
        if args.participant:
            q += " WHERE participant_id = ?"
            params = (args.participant,)
        q += " ORDER BY submitted_at"
        for r in con.execute(q, params).fetchall():
            d = dict(r)
            print(d["view_id"], d["participant_id"], d["theme_id"], d["status"],
                  d["submitted_at"], "->", d["effective_at"], d["end_at"] or "-",
                  d["cycle_week"], (d["reason"] or "")[:60])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
