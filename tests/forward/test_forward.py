"""Forward-test engine tests: synthetic prices + temp DB, no network."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.forward import db as _db
from src.forward.accounts import ensure_personal_accounts, record_target, versions_from_cfg
from src.forward.db import connect, init_db
from src.forward.execution import create_orders, execute_pending
from src.forward.ledger import nav_series, valuate
from src.forward.metrics import perf_metrics
from src.forward.participants import add_participant, deactivate_participant, list_participants
from src.forward.portfolio import build_personalized
from src.forward.prices import CORE_IDS, theme_asset_id, upsert_prices
from src.forward.risk import build_cov_asof
from src.forward.themes import register_themes
from src.forward.views import active_views, close_view, mark_held, submit_view

CFG = {
    "forward_test": {
        "timezone": "Asia/Seoul", "initial_nav": 100.0, "initial_capital_krw": 100000000.0,
        "benchmark_version": "CORE_V0.3", "theme_universe_version": "THEME_UNIVERSE_V0.1",
        "risk_model_version": "RISK_TEST", "execution_rule_version": "NEXT_AVAILABLE_CLOSE_V0",
        "inception_date": "2025-01-06", "stale_price_days": 14,
        "core_rebalance": {"frequency": "monthly"},
        "weekly_view": {"max_active_themes": 2, "direction": "positive_only",
                        "default_if_no_submission": "hold_existing"},
        "view_schedule": {"timezone": "Asia/Seoul", "submission_day": "friday",
                          "cutoff_time": "18:00", "effective_rule": "next_trading_session"},
        "active_sleeve": {"max_total_weight": 0.15, "max_single_theme_weight": 0.10,
                          "max_themes": 2, "one_theme_default_weight": 0.10,
                          "two_theme_default_weight_each": 0.075},
        "risk_guardrail": {"max_vol_increase_pp": 1.0},
        "risk_refresh": {"frequency": "monthly"},
        "execution": {"price_rule": "next_available_close"},
        "costs": {"trading_cost_bps": 5, "slippage_bps": 0, "fx_cost_bps": 0},
        "fractional_shares": True,
    }
}
THEMES = ["semiconductor", "ai", "nuclear"]
CORE_W = {a: 0.105 for a in CORE_IDS}
CORE_W["cash"] = 1.0 - sum(CORE_W.values())


def _prices(n_days=800, seed=0):
    idx = pd.bdate_range("2022-01-03", periods=n_days)
    rng = np.random.default_rng(seed)
    panel = {}
    for a in list(CORE_IDS) + [theme_asset_id(t) for t in THEMES]:
        vol = 0.05 if a == theme_asset_id("nuclear") else 0.01
        panel[a] = pd.Series(100 * np.cumprod(1 + rng.normal(0.001, vol, n_days)), index=idx)
    return pd.DataFrame(panel)


@pytest.fixture()
def con(tmp_path):
    c = connect(tmp_path / "t.db")
    init_db(c)
    register_themes(c, {"universe_version": "THEME_UNIVERSE_V0.1", "themes": [
        {"theme_id": t, "display_name": t, "theme_type": "theme", "ticker": "T",
         "market": "US", "currency": "USD", "active": True,
         "valid_from": "2022-01-01", "valid_to": None,
         "universe_version": "THEME_UNIVERSE_V0.1"} for t in THEMES]})
    panel = _prices()
    upsert_prices(c, panel, "synthetic")
    return c


def _cov(con):
    assets = list(CORE_IDS) + [theme_asset_id(t) for t in THEMES]
    return build_cov_asof(con, assets, "2025-06-30", 3, 52)[0]


def test_participants_dynamic_and_inactive_block(con):
    p1 = add_participant(con, "A", "2025-01-06", "CORE_V0.3")
    p2 = add_participant(con, "B", "2025-02-01", "CORE_V0.3")
    assert len(list_participants(con)) == 2
    assert len(list_participants(con, "active")) == 2
    deactivate_participant(con, p2, "2025-03-01", "CORE_V0.3")
    assert len(list_participants(con, "active")) == 1
    with pytest.raises(ValueError):
        submit_view(con, p2, "ai", "2025-03-03T00:00:00+00:00", "x", "THEME_UNIVERSE_V0.1",
                    "CORE_V0.3")


def test_views_max_two_cutoff_hold_close(con):
    p = add_participant(con, "A", "2025-01-06", "CORE_V0.3")
    r1 = submit_view(con, p, "ai", "2025-01-07T00:00:00+00:00", "r", "THEME_UNIVERSE_V0.1",
                     "CORE_V0.3")
    assert r1["status"] == "new"
    r2 = submit_view(con, p, "nuclear", "2025-01-08T00:00:00+00:00", "r", "THEME_UNIVERSE_V0.1",
                     "CORE_V0.3")
    assert r2["status"] == "new"
    r3 = submit_view(con, p, "semiconductor", "2025-01-09T00:00:00+00:00", "r",
                     "THEME_UNIVERSE_V0.1", "CORE_V0.3")
    assert r3["status"] == "rejected"
    # Friday 2025-01-10 19:00 KST is after cutoff -> next cycle week (2025-01-17)
    late = submit_view(con, p, "ai", "2025-01-10T10:00:00+00:00", "reaffirm",
                       "THEME_UNIVERSE_V0.1", "CORE_V0.3")
    assert late["status"] == "hold" and late["cycle_week"] == "2025-01-17"
    assert mark_held(con, p, "2025-01-10", "CORE_V0.3") >= 2
    close_view(con, p, "ai", "2025-01-13T00:00:00+00:00", "CORE_V0.3")
    assert {v["theme_id"] for v in active_views(con, p)} == {"nuclear"}


def test_active_sleeve_equity_funded_and_sums_to_one(con):
    cov = _cov(con)
    res = build_personalized(CORE_W, [theme_asset_id("ai"), theme_asset_id("semiconductor")],
                             CFG, cov)
    assert res["scaled"] is False
    w = res["weights"]
    assert abs(sum(w.values()) - 1.0) < 1e-9
    assert abs(w[theme_asset_id("ai")] - 0.075) < 1e-9
    # bonds/gold untouched: only equities funded the 15%
    for b in ("us_treasury", "korea_treasury", "tips", "gold", "global_reit"):
        assert abs(w[b] - CORE_W[b]) < 1e-9
    assert abs(sum(w[a] for a in ("us_equity", "developed_ex_us", "emerging_markets",
                                  "korea_equity")) - (4 * 0.105 - 0.15)) < 1e-9


def test_guardrail_scales_volatile_theme(con):
    cov = _cov(con)
    res = build_personalized(CORE_W, [theme_asset_id("nuclear")], CFG, cov)
    assert res["scaled"] is True
    assert res["vol"] <= res["core_vol"] + 0.01 + 1e-9
    assert res["weights"][theme_asset_id("nuclear")] < 0.10


def test_execution_timing_costs_and_nav_identity(con):
    p = add_participant(con, "A", "2025-01-06", "CORE_V0.3")
    core_id, _ = ensure_personal_accounts(con, p, "2025-01-06", CFG, "CORE_V0.3")
    versions = versions_from_cfg(CFG)
    record_target(con, core_id, dict(CORE_W), "2025-01-06", "core", versions, "CORE_V0.3", p)
    # order toward a *changed* target, effective Monday 2025-01-13;
    # Friday 01-10 price exists -> must NOT be used
    moved = dict(CORE_W)
    moved["us_equity"] += 0.01
    moved["cash"] -= 0.01
    create_orders(con, core_id, moved, "2025-01-10T00:00:00+00:00", "2025-01-13",
                  "CORE_V0.3", p)
    execute_pending(con, core_id, "2025-01-10", 5, "CORE_V0.3", p)
    assert con.execute("SELECT COUNT(*) c FROM trades").fetchone()["c"] == 0
    execute_pending(con, core_id, "2025-01-13", 5, "CORE_V0.3", p)
    first = con.execute("SELECT MIN(execution_at) m FROM trades").fetchone()["m"]
    assert first == "2025-01-13"
    r = valuate(con, core_id, "2025-01-13", versions, 100000000.0)
    assert r["status"] == "OK"
    nav = nav_series(con, core_id)
    assert abs(nav[0]["nav_base100"] - 100.0) < 0.05  # only costs drag
    costs = con.execute("SELECT SUM(transaction_cost) c FROM trades").fetchone()["c"]
    assert costs > 0
    # exact cost accounting: cash = capital - buys(gross+cost)
    gross = con.execute("SELECT SUM(gross_value) g FROM trades").fetchone()["g"]
    assert abs(nav[0]["cash_balance"] - (100000000.0 - gross - costs)) < 1e-4
    # cumulative return math
    valuate(con, core_id, "2025-01-20", versions, 100000000.0)
    nav = nav_series(con, core_id)
    assert abs(nav[-1]["cumulative_return"] - (nav[-1]["nav"] / nav[0]["nav"] - 1.0)) < 1e-9


def test_ranking_and_versioning(con):
    assert perf_metrics(__import__("pandas").DataFrame())["status"] == "INSUFFICIENT_HISTORY"
    # shadow version addition does not touch existing history
    con.execute("INSERT INTO model_versions (version_id, version_type, version, created_at,"
                " payload_json) VALUES ('MV-X','benchmark','CORE_V0.4_SHADOW',datetime('now'),'{}')")
    assert con.execute("SELECT COUNT(*) c FROM nav_daily").fetchone()["c"] == 0


def test_deterministic_replay(tmp_path):
    from src.forward.db import connect as _connect
    navs = []
    for k in range(2):
        c = _connect(tmp_path / f"r{k}.db")
        init_db(c)
        upsert_prices(c, _prices(), "synthetic")
        p = add_participant(c, "A", "2025-01-06", "CORE_V0.3")
        core_id, _ = ensure_personal_accounts(c, p, "2025-01-06", CFG, "CORE_V0.3")
        versions = versions_from_cfg(CFG)
        record_target(c, core_id, {"us_equity": 0.0, "cash": 1.0}, "2025-01-05", "core",
                      versions, "CORE_V0.3", p)
        record_target(c, core_id, dict(CORE_W), "2025-01-06", "core", versions, "CORE_V0.3", p)
        create_orders(c, core_id, dict(CORE_W), "2025-01-06T00:00:00+00:00", "2025-01-06",
                      "CORE_V0.3", p)
        execute_pending(c, core_id, "2025-02-28", 5, "CORE_V0.3", p)
        for d in ("2025-01-31", "2025-02-28"):
            valuate(c, core_id, d, versions, 100000000.0)
        navs.append([(r["date"], r["nav"]) for r in nav_series(c, core_id)])
    assert len(navs[0]) > 0
    assert navs[0] == navs[1]
