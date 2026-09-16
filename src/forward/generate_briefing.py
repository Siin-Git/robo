"""Generate briefing: latest exports, plots, dashboard, weekly snapshot."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.briefing import export_latest, plots, render_dashboard, weekly_snapshot
from src.forward.config import load_forward_config, resolve
from src.forward.db import connect
from src.forward.runtime import get_database_path, print_banner


def main() -> int:
    print_banner()
    cfg = load_forward_config()
    con = connect(get_database_path())
    out = resolve("outputs/forward/latest")
    status = export_latest(con, cfg, out)
    plots(con, out)
    weekly_snapshot(con, cfg, _last_friday_label(con), resolve("outputs/forward"))
    render_dashboard(con, out)
    print("system_status:", status)
    rk = out / "participant_rankings.csv"
    try:
        import pandas as pd
        df = pd.read_csv(rk) if rk.stat().st_size > 0 else pd.DataFrame()
    except Exception:
        df = pd.DataFrame()
    if not df.empty:
        cols = [c for c in ("display_name", "weekly_active_return", "cum_active", "mdd", "te")
                if c in df.columns]
        print(df[cols].to_string(index=False))
    else:
        print("(no ranked participants yet)")
    return 0


def _last_friday_label(con) -> str:
    row = con.execute("SELECT MAX(date) m FROM nav_daily").fetchone()
    d = date.fromisoformat(row["m"]) if row and row["m"] else date.today()
    return (d + timedelta(days=(4 - d.weekday()))).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
