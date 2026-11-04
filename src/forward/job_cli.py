"""Shared job-arg parsing + claim/complete wrapper for scheduled CLIs."""
from __future__ import annotations

import argparse
import os


def add_job_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scheduled-for", default=None,
                        help="YYYY-MM-DD the run is scheduled for (default: derived)")
    parser.add_argument("--job-run-id", default=None,
                        help="GitHub run id (default: GITHUB_RUN_ID env or None)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would happen; perform zero writes")
    parser.add_argument("--jobs-db-url", default=None,
                        help="job-registry database URL (default: same sqlite file as data). "
                             "Job records always live with the data they describe.")


def job_context(args, default_scheduled_for: str) -> dict:
    return {
        "scheduled_for": args.scheduled_for or default_scheduled_for,
        "github_run_id": args.job_run_id or os.environ.get("GITHUB_RUN_ID"),
        "dry_run": bool(args.dry_run),
        "jobs_db_url": args.jobs_db_url,
    }


def enter_job(sqlite_path, job_type: str, ctx: dict):
    """Claim a job run. Returns (job_id, decision). dry-run returns (None, 'dry')."""
    # dry-run 은 아무것도 기록하지 않는다. 작업 레지스트리를 import 하지도 않는다
    # (읽기 전용 미리보기가 그 의존성 때문에 실패하면 안 된다).
    if ctx["dry_run"]:
        return None, "dry"
    from src.forward import jobs as _jobs
    return _jobs.claim_job(ctx["jobs_db_url"], job_type, ctx["scheduled_for"],
                           ctx["github_run_id"], sqlite_path=sqlite_path)


def finish_job(sqlite_path, job_id: str | None, decision: str,
               code: int, stats: dict | None, ctx: dict,
               error: str | None = None) -> int:
    if decision == "dry":
        return code            # dry-run 은 작업 기록을 남기지 않는다
    from src.forward import jobs as _jobs
    if decision in ("skipped", "locked"):
        print(f"job {decision}; nothing to do.")
        return 0
    if error is not None or code != 0:
        # Record failure loudly; never silently succeed.
        try:
            _jobs.fail_job(ctx["jobs_db_url"], job_id, error or f"exit code {code}",
                           sqlite_path=sqlite_path, stats=stats)
        except Exception as e:  # noqa: BLE001
            print(f"WARNING: could not record job failure: {e}")
        return code if code != 0 else 1
    from .job_outcome import incomplete_daily
    is_daily = bool(job_id and job_id.startswith("daily-"))
    if ((is_daily and incomplete_daily(stats or {}))
            or (stats or {}).get("status") == "COMPETITION_WAIT" or (stats or {}).get("retryable")):
        # Financial work is incomplete: same-day attempts remain retryable.
        _jobs.wait_job(ctx["jobs_db_url"], job_id, stats, sqlite_path=sqlite_path)
    else:
        _jobs.complete_job(ctx["jobs_db_url"], job_id, stats or {}, sqlite_path=sqlite_path)
    return code
