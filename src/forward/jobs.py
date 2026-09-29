"""Scheduled-job registry: idempotent claims + locking + failure recording.

Backend-agnostic (SQLite file or PostgreSQL URL via SQLAlchemy Core) so the
same code runs locally today and against Neon tomorrow. The financial CLIs
themselves are untouched; this layer only gates and records their runs.

Claim protocol (every attempt recorded, decisions from the latest row):
  success present  -> record 'skipped' (idempotent rerun, exit 0)
  running fresh    -> 'locked' (concurrent duplicate blocked, exit 0)
  otherwise        -> insert 'running' and proceed ('run')
Stale `running` rows (> stale_hours) are treated as abandoned and reclaimed.
Atomicity: SQLite uses BEGIN IMMEDIATE (single writer); PostgreSQL takes a
transaction-scoped advisory lock on the slot. No unique constraint is used so
failed/skipped attempts stay visible for audit.
"""
from __future__ import annotations

import contextlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert, select, text, update

STALE_HOURS = 6


def _now():
    return datetime.now(timezone.utc)


def _table():
    from src.db.base import Base
    import src.db.models  # noqa: F401
    return Base.metadata.tables["scheduled_jobs"]


def _engine_for(db_url: str | None, sqlite_path=None):
    from src.db.session import create_app_engine
    if db_url:
        return create_app_engine(db_url)
    # 운영 데이터가 PostgreSQL 이면 작업 기록도 같은 DB 에 둔다.
    # 이전에는 무조건 SQLite 파일로 가서, 재배포 시 기록이 사라지고
    # 중복 실행 방지(scheduled_jobs)가 무력화됐다.
    try:
        from src.db.config import get_backend
        if get_backend() == "postgres":
            return create_app_engine()
    except Exception:
        pass
    return create_app_engine(f"sqlite:///{sqlite_path}")


def _ensure_jobs_table(engine) -> None:
    from sqlalchemy import inspect as _inspect
    with engine.connect() as conn:
        if _inspect(conn).has_table("scheduled_jobs"):
            return
        if engine.dialect.name == "sqlite":
            from src.db.base import Base
            import src.db.models  # noqa: F401
            Base.metadata.tables["scheduled_jobs"].create(conn)
        else:
            raise RuntimeError("scheduled_jobs table missing: run `alembic upgrade head` first")


@contextlib.contextmanager
def _claim_txn(engine, slot: str):
    """Yield a connection holding the slot lock for check-then-insert.

    SQLite: AUTOCOMMIT + explicit BEGIN IMMEDIATE (real single-writer lock;
    a concurrent claimant blocks, then sees the winner's row).
    PostgreSQL: transaction-scoped advisory lock on the slot.
    """
    if engine.dialect.name == "sqlite":
        conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        try:
            conn.execute(text("BEGIN IMMEDIATE"))
            yield conn
            conn.execute(text("COMMIT"))
        except BaseException:
            try:
                conn.execute(text("ROLLBACK"))
            except Exception:
                pass
            raise
        finally:
            conn.close()
    else:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:slot))"),
                         {"slot": slot})
            yield conn


def _age_hours(started) -> float:
    if started is None:
        return float("inf")
    now = _now()
    base = started if started.tzinfo else started.replace(tzinfo=None)
    ref = now if started.tzinfo else now.replace(tzinfo=None)
    return (ref - base).total_seconds() / 3600


def claim_job(db_url: str | None, job_type: str, scheduled_for: str,
              github_run_id: str | None = None, stale_hours: int = STALE_HOURS,
              sqlite_path=None) -> tuple[str | None, str]:
    """Returns (job_id, decision) with decision in {run, skipped, locked}."""
    from datetime import date as _date
    engine = _engine_for(db_url, sqlite_path)
    _ensure_jobs_table(engine)
    table = _table()
    sched = _date.fromisoformat(str(scheduled_for)[:10])
    slot = f"{job_type}|{sched.isoformat()}"
    job_id = f"{job_type}-{sched.isoformat()}-{uuid.uuid4().hex[:8]}"
    with _claim_txn(engine, slot) as conn:
        # "이미 성공했는가"는 존재 여부로 물어야 한다. 건너뛴 기록도 행으로
        # 남기므로, 가장 최근 행만 보면 두 번째 건너뜀 뒤에 세 번째 시도가
        # 통과한다(그 행의 status 가 'skipped' 라서). 실제로 그렇게 뚫렸다.
        done = conn.execute(select(table).where(
            table.c.job_type == job_type,
            table.c.scheduled_for == sched,
            table.c.status == "success")).fetchone()
        if done is not None:
            conn.execute(insert(table).values(
                job_id=job_id, job_type=job_type, scheduled_for=sched,
                started_at=_now(), completed_at=_now(), status="skipped",
                error_message=None, github_run_id=github_run_id, stats_json={}))
            return None, "skipped"
        # 진행 중인 시도가 있는지는 건너뜀 기록을 빼고 본다.
        existing = conn.execute(select(table).where(
            table.c.job_type == job_type,
            table.c.scheduled_for == sched,
            table.c.status != "skipped").order_by(
            table.c.started_at.desc())).fetchone()
        if existing is not None:
            status = existing._mapping["status"]
            if status == "running" and _age_hours(existing._mapping["started_at"]) < stale_hours:
                return None, "locked"
            # failed / stale running -> new attempt proceeds
        conn.execute(insert(table).values(
            job_id=job_id, job_type=job_type, scheduled_for=sched,
            started_at=_now(), completed_at=None, status="running",
            error_message=None, github_run_id=github_run_id, stats_json={}))
    return job_id, "run"


def complete_job(db_url: str | None, job_id: str, stats: dict | None = None,
                 sqlite_path=None) -> None:
    engine = _engine_for(db_url, sqlite_path)
    table = _table()
    with engine.begin() as conn:
        conn.execute(update(table).where(table.c.job_id == job_id).values(
            status="success", completed_at=_now(), stats_json=dict(stats or {})))


def fail_job(db_url: str | None, job_id: str, error: str, sqlite_path=None) -> None:
    engine = _engine_for(db_url, sqlite_path)
    table = _table()
    with engine.begin() as conn:
        conn.execute(update(table).where(table.c.job_id == job_id).values(
            status="failed", completed_at=_now(), error_message=str(error)[:2048]))


def recent_jobs(db_url: str | None, limit: int = 20, sqlite_path=None) -> list[dict]:
    from sqlalchemy import desc
    engine = _engine_for(db_url, sqlite_path)
    table = _table()
    with engine.connect() as conn:
        rows = conn.execute(select(table).order_by(desc(table.c.started_at)).limit(limit))
        return [dict(r._mapping) for r in rows]
