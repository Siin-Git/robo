"""Local preview DB initializer: live-safe, idempotent seed of frozen artifacts.

Usage:
    python -m src.local.init
Creates data/forward_local.db via the same engine path as the app and refuses
to touch live/demo/validation DBs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

os.environ["APP_PROFILE"] = "local"
os.environ["DATABASE_BACKEND"] = "sqlite"

from src.db.base import Base  # noqa: E402
from src.db.session import create_app_engine  # noqa: E402
from src.forward.runtime import ROOT as FWD_ROOT, get_database_path, print_banner  # noqa: E402


def main() -> int:
    print_banner("local")
    db_path = get_database_path("local")
    if db_path.exists():
        print(f"Local DB already exists at {db_path.relative_to(ROOT)} -- leaving as is.")
        print("To reset, run: python -m src.local.reset")
        return 0
    engine = create_app_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    # Seed frozen/theme artifacts into the local DB by replaying the same
    # frozen copy + theme registration that init_forward_test does, but without
    # ever opening the live DB file.
    from src.forward.config import resolve as _resolve  # noqa: E402
    from src.forward.db import connect as _connect, init_db as _init_db  # noqa: E402
    from src.forward.frozen import freeze_benchmark  # noqa: E402
    from src.forward.themes import load_theme_config as _load_fwd_themes, register_themes  # noqa: E402

    # Ensure frozen artifact exists (built from Phase 1.6 outputs, not from live DB).
    frozen_dir = _resolve("outputs/frozen/CORE_V0.3")
    try:
        freeze_benchmark(frozen_dir,
                         _resolve("outputs/latest/core_v03_weights.csv"),
                         _resolve("outputs/latest/run_metadata.json"),
                         _resolve("outputs/latest/bl_methodology.json"),
                         ROOT / "config" / "optimizer_v0.yaml")
    except RuntimeError:
        pass  # already frozen — reuse

    # Register theme universe V0.1 into the local DB (via the forward sqlite layer).
    fwd_con = _connect(db_path)
    _init_db(fwd_con)
    th_cfg = _load_fwd_themes(FWD_ROOT / "config" / "themes_v01.yaml")
    register_themes(fwd_con, th_cfg)

    # Bootstrap price snapshot into local DB (same helper as live, but local file).
    from src.forward.prices import bootstrap_from_snapshot  # noqa: E402
    from src.forward.config import load_forward_config  # noqa: E402
    fcfg = load_forward_config()
    theme_tickers = {t["theme_id"]: t["ticker"] for t in th_cfg["themes"] if t.get("active")}
    rep = bootstrap_from_snapshot(fwd_con, _resolve(fcfg["snapshot_dir"]), theme_tickers,
                                  start="2015-01-01", end=fcfg["forward_test"]["model_reference_date"])
    print(f"Local DB initialized at {db_path.relative_to(ROOT)}")
    print(f"Prices: {rep['start']}~{rep['end']} ({len(rep['assets'])} assets)")
    print("Ready. Create a user with: python -m src.local.create_test_user")
    return 0


def load_theme_config(path):  # kept for backwards compat; unused
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    raise SystemExit(main())
