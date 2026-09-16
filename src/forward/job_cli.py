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
    from src.forward import jobs as _jobs
    if ctx["dry_run"]:
        return None, "dry"
    return _jobs.claim_job(ctx["jobs_db_url"], job_type, ctx["scheduled_for"],
                           ctx["github_run_id"], sqlite_path=sqlite_path)


def finish_job(sqlite_path, job_id: str | None, decision: str,
               code: int, stats: dict | None, ctx: dict,
               error: str | None = None) -> int:
    from src.forward import jobs as _jobs
    if decision == "dry":
        return code
    if decision in ("skipped", "locked"):
        print(f"job {decision}; nothing to do.")
        return 0
    if error is not None or code != 0:
        # Record failure loudly; never silently succeed.
        try:
            _jobs.fail_job(ctx["jobs_db_url"], job_id, error or f"exit code {code}",
                           sqlite_path=sqlite_path)
        except Exception as e:  # noqa: BLE001
            print(f"WARNING: could not record job failure: {e}")
        return code if code != 0 else 1
    _jobs.complete_job(ctx["jobs_db_url"], job_id, stats or {}, sqlite_path=sqlite_path)
    return code
