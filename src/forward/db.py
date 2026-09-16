"""SQLite storage for the forward-test system (stdlib only)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
  participant_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  status TEXT NOT NULL,
  join_date TEXT NOT NULL,
  leave_date TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  participant_id TEXT,
  account_type TEXT NOT NULL,
  shadow_name TEXT,
  benchmark_version TEXT NOT NULL,
  inception_date TEXT NOT NULL,
  initial_capital_krw REAL NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS themes (
  theme_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  theme_type TEXT NOT NULL,
  ticker TEXT,
  market TEXT,
  currency TEXT,
  active INTEGER NOT NULL,
  valid_from TEXT,
  valid_to TEXT,
  universe_version TEXT NOT NULL,
  inactive_reason TEXT
);
CREATE TABLE IF NOT EXISTS views (
  view_id TEXT PRIMARY KEY,
  participant_id TEXT NOT NULL,
  theme_id TEXT NOT NULL,
  status TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  effective_at TEXT NOT NULL,
  end_at TEXT,
  reason TEXT,
  theme_universe_version TEXT NOT NULL,
  cycle_week TEXT NOT NULL,
  cycle_date TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_targets (
  target_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  effective_date TEXT NOT NULL,
  kind TEXT NOT NULL,
  weights_json TEXT NOT NULL,
  core_version TEXT NOT NULL,
  theme_universe_version TEXT NOT NULL,
  risk_model_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
  order_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  side TEXT NOT NULL,
  target_weight REAL NOT NULL,
  submitted_at TEXT NOT NULL,
  effective_at TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
  trade_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  account_id TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  execution_at TEXT NOT NULL,
  execution_price REAL NOT NULL,
  quantity REAL NOT NULL,
  gross_value REAL NOT NULL,
  transaction_cost REAL NOT NULL,
  net_value REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS holdings_daily (
  account_id TEXT NOT NULL,
  date TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  quantity REAL NOT NULL,
  price REAL NOT NULL,
  market_value REAL NOT NULL,
  weight REAL NOT NULL,
  PRIMARY KEY (account_id, date, asset_id)
);
CREATE TABLE IF NOT EXISTS nav_daily (
  account_id TEXT NOT NULL,
  date TEXT NOT NULL,
  nav REAL NOT NULL,
  nav_base100 REAL NOT NULL,
  daily_return REAL,
  cumulative_return REAL NOT NULL,
  cash_balance REAL NOT NULL,
  stale_price_flag INTEGER NOT NULL,
  nav_status TEXT NOT NULL,
  benchmark_version TEXT NOT NULL,
  theme_universe_version TEXT NOT NULL,
  risk_model_version TEXT NOT NULL,
  execution_rule_version TEXT NOT NULL,
  PRIMARY KEY (account_id, date)
);
CREATE TABLE IF NOT EXISTS performance_daily (
  account_id TEXT NOT NULL,
  date TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  PRIMARY KEY (account_id, date)
);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  participant_id TEXT,
  account_id TEXT,
  timestamp TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  model_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_versions (
  version_id TEXT PRIMARY KEY,
  version_type TEXT NOT NULL,
  version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices_daily (
  asset_id TEXT NOT NULL,
  date TEXT NOT NULL,
  price REAL NOT NULL,
  source TEXT NOT NULL,
  PRIMARY KEY (asset_id, date)
);
CREATE TABLE IF NOT EXISTS counters (
  name TEXT PRIMARY KEY,
  value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS forward_state (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS scheduled_jobs (
  job_id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL,
  scheduled_for TEXT NOT NULL,
  started_at TEXT,
  completed_at TEXT,
  status TEXT NOT NULL,
  error_message TEXT,
  github_run_id TEXT,
  stats_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_jobs_type_scheduled
  ON scheduled_jobs (job_type, scheduled_for);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON scheduled_jobs (status);
"""


def connect(db_path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_id(con: sqlite3.Connection, prefix: str, width: int = 3) -> str:
    cur = con.execute("SELECT value FROM counters WHERE name = ?", (prefix,))
    row = cur.fetchone()
    n = (row["value"] + 1) if row else 1
    con.execute("INSERT OR REPLACE INTO counters (name, value) VALUES (?, ?)", (prefix, n))
    return f"{prefix}{n:0{width}d}"


def log_event(con: sqlite3.Connection, event_type: str, model_version: str,
              participant_id=None, account_id=None, payload=None,
              timestamp: str | None = None) -> str:
    eid = next_id(con, "E", 6)
    con.execute(
        "INSERT INTO events (event_id, event_type, participant_id, account_id, timestamp,"
        " payload_json, model_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (eid, event_type, participant_id, account_id, timestamp or now_iso(),
         json.dumps(payload or {}, ensure_ascii=False), model_version),
    )
    return eid
