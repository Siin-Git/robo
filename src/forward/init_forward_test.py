"""Initialize the forward test: DB, themes, frozen benchmark, prices, shadows."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.forward.accounts import ensure_shadow_account, place_target_orders, record_target, versions_from_cfg
from src.forward.config import load_forward_config, resolve
from src.forward.db import connect, init_db, log_event
from src.forward.execution import execute_pending
from src.forward.frozen import freeze_benchmark, load_frozen_benchmark
from src.forward.ledger import valuate
from src.forward.prices import bootstrap_from_snapshot
from src.forward.runtime import get_database_path, print_banner
from src.forward.themes import load_theme_config, register_themes

SHADOWS = ("neutral_60_40", "equal_weight", "core_v03")


def shadow_weights(name: str, cfg, frozen_w: dict) -> dict:
    if name == "core_v03":
        return dict(frozen_w)
    if name == "neutral_60_40":
        w = pd.read_csv(resolve(cfg["phase16_outputs"]) / "neutral_60_40_weights.csv",
                        index_col=0)["weight"]
        return {k: float(v) for k, v in w.items()}
    if name == "equal_weight":
        from src.forward.prices import CORE_IDS
        w = {a: 1 / 9 for a in CORE_IDS}
        w["cash"] = 0.0
        return w
    raise ValueError(f"unknown shadow {name} (add via model_versions for new shadows)")


def main() -> int:
    profile = print_banner()
    tag = "LIVE" if profile == "live" else profile.upper()
    cfg = load_forward_config()
    ft = cfg["forward_test"]
    con = connect(get_database_path())
    init_db(con)
    history = {}
    for t in ("participants", "views", "orders", "trades", "nav_daily",
              "holdings_daily", "portfolio_targets", "performance_daily"):
        try:
            history[t] = con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        except Exception:
            history[t] = 0
    if any(history.values()):
        print("ERROR:\nForward-test DB already contains history.\n"
              "Refusing destructive reinitialization.")
        print(history)
        return 2
    theme_cfg = load_theme_config(ROOT / "config" / "themes_v01.yaml")
    n_themes = register_themes(con, theme_cfg)
    frozen_dir = resolve(cfg["frozen_dir"])
    try:
        freeze_benchmark(
            frozen_dir,
            resolve(cfg["phase16_outputs"]) / "core_v03_weights.csv",
            resolve(cfg["phase16_outputs"]) / "run_metadata.json",
            resolve(cfg["phase16_outputs"]) / "bl_methodology.json",
            ROOT / "config" / "optimizer_v0.yaml",
        )
        print(f"Benchmark frozen at {frozen_dir}.")
    except RuntimeError as e:
        print(f"{e} -- reusing existing frozen artifact.")
    frozen_w, frozen_meta = load_frozen_benchmark(frozen_dir)
    con.execute("INSERT OR REPLACE INTO model_versions (version_id, version_type, version,"
                " created_at, payload_json) VALUES ('MV-BENCH', 'benchmark', ?, datetime('now'), ?)",
                (ft["benchmark_version"], str(frozen_meta)))
    con.execute("INSERT OR REPLACE INTO model_versions (version_id, version_type, version,"
                " created_at, payload_json) VALUES ('MV-THEME', 'theme_universe', ?, datetime('now'), ?)",
                (ft["theme_universe_version"], '{"source": "config/themes_v01.yaml"}'))
    con.execute("INSERT OR REPLACE INTO model_versions (version_id, version_type, version,"
                " created_at, payload_json) VALUES ('MV-RISK', 'risk_model', ?, datetime('now'), ?)",
                (ft["risk_model_version"], '{"convention": "5Y weekly Ledoit-Wolf"}'))
    con.commit()

    theme_tickers = {t["theme_id"]: t["ticker"] for t in theme_cfg["themes"] if t.get("active")}
    rep = bootstrap_from_snapshot(con, resolve(cfg["snapshot_dir"]), theme_tickers,
                                  start="2015-01-01", end=ft["model_reference_date"])
    print(f"Prices bootstrapped: {rep['assets'][-3:]}... {rep['start']}~{rep['end']}.")
    log_event(con, "FORWARD_TEST_INITIALIZED", ft["benchmark_version"], payload={
        "themes": n_themes, "price_coverage": rep})

    versions = versions_from_cfg(cfg)
    ref_date = ft["model_reference_date"]
    # Clean-init only: shadow account definitions + model-reference targets.
    # NO orders/trades/NAV are created here, and NO inception is set.
    # First execution happens on later daily runs at then-available prices
    # (no retroactive fills); NAV=100 anchors only after first execution.
    for s in SHADOWS:
        aid = ensure_shadow_account(con, s, ref_date, cfg, ft["benchmark_version"])
        w = shadow_weights(s, cfg, frozen_w)
        record_target(con, aid, w, ref_date, "core" if s == "core_v03" else "shadow",
                      versions, ft["benchmark_version"])
    log_event(con, "LIVE_DB_INITIALIZED", ft["benchmark_version"], payload={
        "profile": profile, "themes": n_themes, "price_coverage": rep,
        "forward_test_inception_at": None, "first_execution_at": None})
    con.commit()
    print("")
    print(f"{tag} FORWARD TEST INITIALIZED")
    print("")
    print("Participants: 0")
    print("Views: 0")
    print("Orders: 0")
    print("Trades: 0")
    print("")
    print("Benchmark:")
    print(f"{ft['benchmark_version']}")
    print("")
    print("Theme Universe:")
    print(f"{ft['theme_universe_version']}")
    print("")
    print("Status:")
    print("READY_FOR_PARTICIPANT_REGISTRATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
