"""Scheduler job registry tests: idempotency, locking, failure, dry-run purity."""
import sqlite3

from src.forward import jobs as J


def _db(tmp_path):
    p = tmp_path / "jobs.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE t (a TEXT)")
    con.commit()
    con.close()
    return p


def test_claim_complete_then_skipped(tmp_path):
    db = _db(tmp_path)
    jid, d = J.claim_job(None, "daily", "2026-09-14", sqlite_path=db)
    assert (jid, d) == (jid, "run") and jid
    assert J.claim_job(None, "daily", "2026-09-14", sqlite_path=db)[1] == "locked"
    J.complete_job(None, jid, {"n": 1}, sqlite_path=db)
    assert J.claim_job(None, "daily", "2026-09-14", sqlite_path=db) == (None, "skipped")
    rows = J.recent_jobs(None, sqlite_path=db)
    assert {r["status"] for r in rows} == {"success", "skipped"}
    assert any(r["status"] == "success" for r in rows)


def test_fail_and_reclaim(tmp_path):
    db = _db(tmp_path)
    jid, _ = J.claim_job(None, "weekly", "2026-09-11", sqlite_path=db)
    J.fail_job(None, jid, "boom", sqlite_path=db)
    jid2, d2 = J.claim_job(None, "weekly", "2026-09-11", sqlite_path=db)
    assert d2 == "run" and jid2 != jid
    rows = J.recent_jobs(None, sqlite_path=db)
    assert {r["status"] for r in rows} == {"failed", "running"}


def test_daily_dry_run_writes_nothing(tmp_path, monkeypatch):
    import src.forward.run_daily as _rd
    import src.forward.runtime as runtime
    from src.forward.db import connect, init_db
    dbp = tmp_path / "fwd.db"
    con = connect(dbp)
    init_db(con)
    con.close()
    # main imports this resolver inside the function; patch its actual source.
    # Patching only _rd.get_database_path accidentally reads a developer DB.
    monkeypatch.setattr(runtime, "get_database_path", lambda profile=None: dbp)
    def scratch_connect(path):
        assert path == dbp, "dry-run test must only open its scratch database"
        return connect(path)
    monkeypatch.setattr(_rd, "connect", scratch_connect)
    before = {t: _count(dbp, t) for t in ("orders", "trades", "nav_daily", "events")}
    assert _rd.main(["--dry-run"]) == 0
    after = {t: _count(dbp, t) for t in ("orders", "trades", "nav_daily", "events")}
    assert before == after


def _count(dbp, table):
    con = sqlite3.connect(dbp)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return -1
    finally:
        con.close()


def test_concurrent_duplicate_claim_blocked(tmp_path):
    import threading
    from src.forward.db import connect, init_db
    db = tmp_path / "conc.db"
    con = connect(db)
    init_db(con)
    con.close()
    results = []

    def worker():
        try:
            results.append(J.claim_job(None, "daily", "2026-09-14", sqlite_path=db))
        except Exception as e:  # noqa: BLE001
            results.append(("error", str(e)))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    runs = [r for r in results if r[1] == "run"]
    assert len(runs) == 1, results
    assert all(r[1] == "locked" for r in results if r not in runs)


def test_double_daily_execution_creates_no_duplicates(tmp_path):
    import pandas as pd
    from src.forward.accounts import record_target, versions_from_cfg
    from src.forward.db import connect, init_db
    from src.forward.execution import create_orders, execute_pending
    from src.forward.ledger import valuate
    from src.forward.participants import add_participant
    from src.forward.prices import upsert_prices
    versions = {"benchmark_version": "V", "theme_universe_version": "T",
                "risk_model_version": "R", "execution_rule_version": "E"}
    dbp = tmp_path / "idem.db"
    con = connect(dbp)
    init_db(con)
    idx = pd.bdate_range("2026-09-01", periods=10)
    panel = pd.DataFrame({"us_equity": 100.0, "cash": 1.0}, index=idx)
    upsert_prices(con, panel, "synthetic")
    pid = add_participant(con, "A", "2026-09-01", "V")
    con.execute("INSERT INTO accounts (account_id, participant_id, account_type, shadow_name,"
                " benchmark_version, inception_date, initial_capital_krw, status, created_at)"
                " VALUES ('A-1', ?, 'core', NULL, 'V', '2026-09-01', 100.0, 'active', 'x')", (pid,))
    record_target(con, "A-1", {"us_equity": 0.0, "cash": 1.0}, "2026-09-01", "core",
                  versions, "V", pid)
    record_target(con, "A-1", {"us_equity": 0.5, "cash": 0.5}, "2026-09-08", "core",
                  versions, "V", pid)
    create_orders(con, "A-1", {"us_equity": 0.5, "cash": 0.5},
                  "2026-09-08T00:00:00+00:00", "2026-09-08", "V", pid)
    for _ in range(2):  # same daily job twice
        execute_pending(con, "A-1", "2026-09-14", 5, "V", pid)
        valuate(con, "A-1", "2026-09-14", versions, 100.0)
    con.commit()
    assert _count(dbp, "trades") == 1
    assert _count(dbp, "nav_daily") == 1
    n1 = con.execute("SELECT nav FROM nav_daily").fetchone()[0]
    valuate(con, "A-1", "2026-09-14", versions, 100.0)
    assert con.execute("SELECT nav FROM nav_daily").fetchone()[0] == n1


def test_세_번째_시도도_건너뛴다(tmp_path):
    """건너뛴 기록이 남아도 성공 판정이 흔들리면 안 된다.

    (2026-09-29) 건너뛸 때 status='skipped' 행을 넣는데, 판정이 '가장 최근 행'
    기준이라 두 번째 건너뜀 뒤 세 번째 시도가 통과했다. 실제로 같은 날 배치가
    세 번 돌았고, 세 번째가 장이 열린 시각이라 장중 가격이 저장됐다.
    """
    db = _db(tmp_path)
    jid, d = J.claim_job(None, "daily", "2026-09-29", sqlite_path=db)
    assert d == "run"
    J.complete_job(None, jid, {}, sqlite_path=db)
    for attempt in range(2, 6):
        assert J.claim_job(None, "daily", "2026-09-29", sqlite_path=db) == (None, "skipped"), \
            f"{attempt}번째 시도가 통과했다"


def test_실패한_날은_여전히_재시도된다(tmp_path):
    """성공 존재 여부로 판정하되, 실패 뒤 재시도는 막지 않아야 한다."""
    db = _db(tmp_path)
    jid, _ = J.claim_job(None, "daily", "2026-09-29", sqlite_path=db)
    J.fail_job(None, jid, "boom", sqlite_path=db)
    jid2, d2 = J.claim_job(None, "daily", "2026-09-29", sqlite_path=db)
    assert d2 == "run", "실패한 날의 재시도를 막으면 안 된다"
    J.complete_job(None, jid2, {}, sqlite_path=db)
    assert J.claim_job(None, "daily", "2026-09-29", sqlite_path=db) == (None, "skipped")


def test_건너뜀_기록이_진행중_판정을_가리지_않는다(tmp_path):
    """건너뜀 행이 최근이어도 진행 중인 시도는 잠금으로 잡혀야 한다."""
    db = _db(tmp_path)
    jid, _ = J.claim_job(None, "daily", "2026-09-30", sqlite_path=db)   # running
    J.complete_job(None, jid, {}, sqlite_path=db)
    assert J.claim_job(None, "daily", "2026-09-30", sqlite_path=db)[1] == "skipped"
    # 다른 날짜는 서로 영향을 주지 않는다
    jid2, d2 = J.claim_job(None, "daily", "2026-10-01", sqlite_path=db)
    assert d2 == "run"
    assert J.claim_job(None, "daily", "2026-10-01", sqlite_path=db)[1] == "locked"


def test_다른_작업_종류는_서로_막지_않는다(tmp_path):
    db = _db(tmp_path)
    jid, _ = J.claim_job(None, "daily", "2026-10-01", sqlite_path=db)
    J.complete_job(None, jid, {}, sqlite_path=db)
    assert J.claim_job(None, "daily", "2026-10-01", sqlite_path=db)[1] == "skipped"
    assert J.claim_job(None, "monthly", "2026-10-01", sqlite_path=db)[1] == "run"
