"""Disposable API/browser fixture. Never point at an existing or production DB."""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--mode", choices=["prepare", "nav", "counts"], default="prepare")
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_relative_to(Path("/private/tmp")):
        parser.error("Only a new disposable /private/tmp fixture is allowed")
    os.environ.update(APP_PROFILE="local", CAPSTONE_DEMO="1", CAPSTONE_MARKET_COMPARISON="1",
        DATABASE_BACKEND="sqlite", DATABASE_URL="", CAPSTONE_DESIGN_DATABASE_URL="",
        CAPSTONE_DATA_DIR=str(directory), AUTH_COOKIE_SECURE="false", ALLOW_PUBLIC_REGISTRATION="false")
    if args.mode == "prepare":
        if directory.exists():
            parser.error("Fixture directory must not exist")
        subprocess.run([sys.executable,"-m","src.local.lab_meeting","--name","verification-ui",
            "--out",str(directory/"accounts.json")],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        (directory/"verification-ui-marker").write_text("TEST_FIXTURE; NOT OPERATING PERFORMANCE")
    if not (directory/"verification-ui-marker").exists():
        parser.error("Not a verification UI fixture")
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session
    from src.db.models import Account, NavDaily, PriceDaily, User, Participant
    from src.db.models.scheduled_job import ScheduledJob
    engine = create_engine(f"sqlite:///{directory / 'portfolio_design.db'}")
    now = datetime.now(timezone.utc)
    if args.mode == "prepare":
        from fastapi.testclient import TestClient
        from src.api.main import app
        from src.api.services import _common as C
        account=json.loads((directory/"accounts.json").read_text())["accounts"][0]
        with TestClient(app) as client:
            assert client.post("/api/v1/auth/login",json={"email":account["email"],"password":account["password"]}).status_code==200
            frontier=client.get("/api/v1/me/frontier").json()
            # A NEW fixture confirmation, never an update/backfill of real history.
            C.now_utc=lambda: datetime(2026,10,1,3,tzinfo=timezone.utc)
            response=client.post("/api/v1/me/onboarding/complete",headers={"X-CSRF-Token":client.cookies["ra_csrf"]},json={
                "frontier_id":frontier["benchmark_frontier_id"],"theme_ids":["ai"],
                "reason":"격리 테스트용 판단 · 운영 투자 판단이나 실적이 아닙니다."})
            assert response.status_code==200,response.text
            original=client.get("/api/v1/me/decisions").json()["items"][0]
            (directory/"original.json").write_text(json.dumps(original,ensure_ascii=False,indent=2))
        auth_engine=create_engine(f"sqlite:///{directory / 'capstone_demo.db'}")
        with Session(auth_engine) as db:
            user=db.scalar(select(User).where(User.email_normalized==account["email"]))
            db.get(Participant,user.participant_id).display_name="검증용 계정 · 운영 실적 아님"
            db.commit()
        with Session(engine) as db:
            db.add(ScheduledJob(job_id="daily-ui-fixture-wait",job_type="daily",scheduled_for=now.date(),started_at=now,completed_at=now,status="success",
                stats_json={"status":"COMPETITION_WAIT","reason":"START_NOT_SCHEDULED","outcome":"PARTIAL","valuated":0,"ready":15,"required":15,"fixture":True}))
            db.commit()
        print("TEST_FIXTURE prepared; no operating start, orders, trades or NAV.")
    elif args.mode == "nav":
        original=json.loads((directory/"original.json").read_text())
        with Session(engine) as db:
            core=db.scalar(select(Account).where(Account.participant_id==original["participant_id"],Account.account_type=="core"))
            ids=[original["account_id"],core.account_id]
            for index,aid in enumerate(ids):
                for day,value in [(date(2026,10,22),100000000),(date(2026,10,23),101000000-index*500000)]:
                    if not db.get(NavDaily,(aid,day)):
                        db.add(NavDaily(account_id=aid,date=day,nav=value,cash_balance=value,nav_base100=value/1000000,daily_return=0,cumulative_return=value/100000000-1,
                            stale_price_flag=False,nav_status="OK",benchmark_version="CORE_V0.3",theme_universe_version="THEME_UNIVERSE_V0.1",risk_model_version="TEST_FIXTURE",execution_rule_version="TEST_FIXTURE"))
            if not db.get(PriceDaily,("us_equity",date(2026,10,23))):
                db.add(PriceDaily(asset_id="us_equity",date=date(2026,10,23),price=100,source="SYNTHETIC_TEST_UI"))
            if not db.get(ScheduledJob,"daily-ui-fixture-nav"):
                db.add(ScheduledJob(job_id="daily-ui-fixture-nav",job_type="daily",scheduled_for=now.date(),started_at=now,completed_at=now,status="success",
                    stats_json={"status":"PASS","outcome":"SUCCESS","asof":"2026-10-23","valuated":2,"account_results":{aid:{"status":"OK"} for aid in ids},"fixture":True}))
            db.commit()
        print("TEST_FIXTURE NAV inserted; verification must exclude it from actual performance.")
    else:
        with Session(engine) as db:
            print(json.dumps({table:db.scalar(text("SELECT COUNT(*) FROM "+table)) for table in
                ("orders","trades","nav_daily","scheduled_jobs","portfolio_decisions","portfolio_choices")}))


if __name__ == "__main__":
    main()
