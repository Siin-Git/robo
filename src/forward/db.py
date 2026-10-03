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


def connect(db_path):
    """DATABASE_BACKEND 에 따라 SQLite 파일 또는 PostgreSQL 에 연결한다."""
    import os
    # src.db.config 를 import 하면 .env / .env.local 이 로드된다(프로세스 환경변수 우선).
    try:
        from ..db.config import get_backend as _get_backend
        backend = _get_backend()
    except Exception:
        backend = os.environ.get("DATABASE_BACKEND", "sqlite").strip().lower()
    if backend == "postgres":
        # 캡스톤 모드에서 엔진이 기록을 남길 곳은 인증 DB 가 아니라 설계 DB 다.
        # SQLite 경로는 get_database_path() 가 그 구분을 해 주지만, postgres
        # 경로는 예전에 DATABASE_URL 하나만 봤다. 그대로 두면 운용 기록이
        # 인증·시연 DB 에 섞인다(조용히 일어난다).
        # 캡스톤 모드가 아니면 None 이 돌아와 예전 동작 그대로다.
        url = ""
        try:
            from ..db.config import get_design_database_url
        except ImportError:  # 경량 실행 환경 - DATABASE_URL 로 간다
            pass
        else:
            url = get_design_database_url(backend) or ""
        if not url:
            url = os.environ.get("DATABASE_URL", "").strip()
        if not url:
            raise ValueError("DATABASE_URL is not set (required for postgres backend)")
        from .pg_adapter import connect_postgres
        return connect_postgres(url)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_design_schema(db_path)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _ensure_design_schema(db_path: Path) -> None:
    """캡스톤 설계 DB 를 forward 가 먼저 열 때 API 와 같은 스키마로 만든다.

    API(`design_workspace`)는 SQLAlchemy 모델로 테이블을 만든다. forward 의
    자체 SCHEMA 로 먼저 만들면 두 스키마가 어긋나므로, 이 경우에만 모델 기준으로
    생성한다. 다른 DB 파일에는 관여하지 않는다.
    """
    from .runtime import capstone_design_db
    design = capstone_design_db()
    if design is None or Path(design).resolve() != db_path.resolve():
        return
    try:
        from src.db.base import Base
        import src.db.models  # noqa: F401  (모든 모델 등록)
        from src.db.session import create_app_engine
        from src.db.design_schema import ensure_design_schema
        ensure_design_schema(create_app_engine(f"sqlite:///{db_path}"))
    except Exception as exc:  # noqa: BLE001 - 조용히 빈 DB 를 만드는 편이 더 나쁘다
        raise RuntimeError(
            f"설계 DB 스키마를 만들 수 없다({db_path}). API 를 한 번 실행해 "
            f"테이블을 생성한 뒤 다시 시도할 것: {exc}") from exc


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    con.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def next_id(con: sqlite3.Connection, prefix: str, width: int = 3) -> str:
    n = con.execute("INSERT INTO counters (name,value) VALUES (?,1) "
                    "ON CONFLICT (name) DO UPDATE SET value=counters.value+1 RETURNING value", (prefix,)).fetchone()["value"]
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
