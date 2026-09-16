"""Raw SQLite reader for migration input (stdlib only, no ORM on source).

Reads the live SQLite file exactly as stored (TEXT/REAL/INTEGER) and yields
plain Python values; type conversion to PostgreSQL lives in the migrate script.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def table_columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]


def iter_table(db_path, table: str, order_by: str | None = None):
    """Yield row dicts in deterministic PK order."""
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cols = table_columns(con, table)
    pk_cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()
               if r["pk"]]
    order = order_by or (", ".join(f'"{c}"' for c in pk_cols) if pk_cols else "rowid")
    cur = con.execute(f'SELECT * FROM "{table}" ORDER BY {order}')
    for row in cur:
        yield {c: row[c] for c in cols}
    con.close()


def row_count(db_path, table: str) -> int:
    con = sqlite3.connect(str(db_path))
    n = con.execute(f'SELECT COUNT(*) c FROM "{table}"').fetchone()[0]
    con.close()
    return n


def list_tables(db_path) -> list[str]:
    con = sqlite3.connect(str(db_path))
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        " ORDER BY name").fetchall()]
    con.close()
    return tables
