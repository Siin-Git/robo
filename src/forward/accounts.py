"""Account lifecycle + target recording."""
from __future__ import annotations

import json
import sqlite3

from .db import log_event, now_iso
from .execution import create_orders


def ensure_personal_accounts(con: sqlite3.Connection, participant_id: str, join_date: str,
                             cfg: dict, model_version: str) -> tuple[str, str]:
    """Create core+personal accounts for a participant (idempotent)."""
    ft = cfg["forward_test"]
    core_id, pers_id = f"A-{participant_id}-CORE", f"A-{participant_id}-PERSONAL"
    for aid, atype in ((core_id, "core"), (pers_id, "personal")):
        if con.execute("SELECT 1 FROM accounts WHERE account_id = ?", (aid,)).fetchone():
            continue
        con.execute("INSERT INTO accounts (account_id, participant_id, account_type,"
                    " shadow_name, benchmark_version, inception_date, initial_capital_krw,"
                    " status, created_at) VALUES (?, ?, ?, NULL, ?, ?, ?, 'active', ?)",
                    (aid, participant_id, atype, ft["benchmark_version"], join_date,
                     float(ft["initial_capital_krw"]), now_iso()))
        log_event(con, "ACCOUNT_CREATED", model_version, participant_id, aid,
                  {"account_type": atype, "inception_date": join_date})
    con.commit()
    return core_id, pers_id


def ensure_shadow_account(con: sqlite3.Connection, shadow_name: str, inception_date: str,
                          cfg: dict, model_version: str) -> str:
    aid = f"A-SHADOW-{shadow_name}"
    if con.execute("SELECT 1 FROM accounts WHERE account_id = ?", (aid,)).fetchone() is None:
        ft = cfg["forward_test"]
        con.execute("INSERT INTO accounts (account_id, participant_id, account_type,"
                    " shadow_name, benchmark_version, inception_date, initial_capital_krw,"
                    " status, created_at) VALUES (?, NULL, 'shadow', ?, ?, ?, ?, 'active', ?)",
                    (aid, shadow_name, ft["benchmark_version"], inception_date,
                     float(ft["initial_capital_krw"]), now_iso()))
        log_event(con, "ACCOUNT_CREATED", model_version, None, aid,
                  {"account_type": "shadow", "shadow_name": shadow_name})
        con.commit()
    return aid


def record_target(con: sqlite3.Connection, account_id: str, weights: dict,
                  effective_date: str, kind: str, versions: dict,
                  model_version: str, participant_id=None) -> str:
    from .db import next_id
    tid = next_id(con, "G")
    con.execute("INSERT INTO portfolio_targets (target_id, account_id, effective_date, kind,"
                " weights_json, core_version, theme_universe_version, risk_model_version,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, account_id, effective_date, kind, json.dumps(weights, ensure_ascii=False),
                 versions["benchmark_version"], versions["theme_universe_version"],
                 versions["risk_model_version"], now_iso()))
    log_event(con, "PORTFOLIO_GENERATED", model_version, participant_id, account_id,
              {"target_id": tid, "kind": kind, "effective_date": effective_date,
               "weights": weights})
    con.commit()
    return tid


def place_target_orders(con: sqlite3.Connection, account_id: str, weights: dict,
                        submitted_at: str, effective_at: str, model_version: str,
                        participant_id=None, kind: str = "REBALANCE",
                        baseline: dict | None = None,
                        band: dict | None = None) -> list[str]:
    return create_orders(con, account_id, weights, submitted_at, effective_at,
                         model_version, participant_id, kind, baseline, band)


def versions_from_cfg(cfg: dict) -> dict:
    ft = cfg["forward_test"]
    return {"benchmark_version": ft["benchmark_version"],
            "theme_universe_version": ft["theme_universe_version"],
            "risk_model_version": ft["risk_model_version"],
            "execution_rule_version": ft["execution_rule_version"]}
