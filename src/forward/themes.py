"""Theme registry (versioned, append-only semantics)."""
from __future__ import annotations

import sqlite3

import yaml


def load_theme_config(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def register_themes(con: sqlite3.Connection, theme_cfg: dict) -> int:
    n = 0
    for t in theme_cfg["themes"]:
        con.execute(
            "INSERT OR REPLACE INTO themes (theme_id, display_name, theme_type, ticker, market,"
            " currency, active, valid_from, valid_to, universe_version, inactive_reason)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (t["theme_id"], t["display_name"], t["theme_type"], t.get("ticker"),
             t.get("market"), t.get("currency"), bool(t.get("active")),
             t.get("valid_from"), t.get("valid_to"),
             t.get("universe_version", theme_cfg["universe_version"]),
             t.get("inactive_reason")),
        )
        n += 1
    con.commit()
    return n


def active_themes(con: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT * FROM themes WHERE active = 1 ORDER BY theme_id").fetchall()]


def get_theme(con: sqlite3.Connection, theme_id: str) -> dict:
    row = con.execute("SELECT * FROM themes WHERE theme_id = ?", (theme_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown theme {theme_id}")
    return dict(row)


def require_tradable(con: sqlite3.Connection, theme_id: str) -> dict:
    t = get_theme(con, theme_id)
    if not t["active"] or not t["ticker"]:
        raise ValueError(f"theme {theme_id} is not tradable in this universe version")
    return t
