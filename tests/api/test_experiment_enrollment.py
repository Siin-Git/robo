"""Real auth + reserved enrollment + frozen report acceptance."""
import secrets
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, func
from src.local.seed_capstone import seed
from src.local.demo_cohort import prepare
from src.local.capstone import COHORT_SIZE, EMAILS, PASSWORD
from src.db.models.user import User
from src.db.models.demo_cohort import DemoSlot
from src.db.models.nav import NavDaily
from src.db.models.portfolio import PortfolioTarget
from src.api.services import enrollment_service as svc
from src.api.errors import ApiError


def setup(env, monkeypatch, count=1):
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("CAPSTONE_DEMO", "1")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    with env.factory() as s:
        seed(s)
        invitations = prepare(s, "rehearsal", [f"new{i}@example.com" for i in range(count)])
        s.commit()
    return invitations["invitations"]


def signup(c, invite):
    password = secrets.token_urlsafe(22)
    response = c.post("/api/v1/auth/register", json={**invite, "display_name": "새 참가자", "password": password})
    assert response.status_code == 201, response.text
    assert c.post("/api/v1/auth/login", json={"email": invite["email"], "password": password}).status_code == 200
    return response.json(), password


def csrf(c):
    return {"X-CSRF-Token": c.cookies["ra_csrf"]}


def config(ids=None):
    return {"core_id":"CORE_V0.3", "theme_ids": ids if ids is not None else ["semiconductor", "ai"], "reason":"나의 선택 근거", "current_step":"review"}


def test_signup_save_freeze_compare_restart_and_seed(env, monkeypatch):
    invite=setup(env, monkeypatch)[0]
    c=env.client
    assert c.post("/api/v1/auth/register",json={**invite,"invitation_code":"wrong","display_name":"x","password":secrets.token_urlsafe(22)}).status_code==403
    info,password=signup(c,invite)
    uid,pid=info["user_id"],info["participant_id"]
    assert c.post("/api/v1/auth/register",json={"email":"extra@example.com","invitation_code":"invalid","display_name":"extra","password":password}).json()["error"]["code"]=="COHORT_FULL"
    assert c.post("/api/v1/auth/register",json={**invite,"display_name":"x","password":password}).status_code==409
    assert c.get("/api/v1/me/experiment").json()["status"]=="setup_required"
    assert c.get("/api/v1/comparison/rankings").json()["registered"]==COHORT_SIZE-1
    body=config()
    assert c.put("/api/v1/me/experiment/draft",json=body).status_code==403
    assert c.put("/api/v1/me/experiment/draft",json=body,headers=csrf(c)).status_code==200
    c.post("/api/v1/auth/logout",headers=csrf(c))
    c.post("/api/v1/auth/login",json={"email":invite["email"],"password":password})
    assert c.get("/api/v1/me/experiment").json()["draft"]=={**body, "frontier_id": None}
    assert c.post("/api/v1/me/experiment/complete",json={**body,"core_id":"other"},headers=csrf(c)).status_code==422
    assert c.post("/api/v1/me/experiment/complete",json={**body,"reason":" "},headers=csrf(c)).status_code==422
    assert c.post("/api/v1/me/experiment/complete",json={**body,"theme_ids":["ai","ai"]},headers=csrf(c)).status_code==422
    completed=c.post("/api/v1/me/experiment/complete",json=body,headers=csrf(c))
    assert completed.status_code==200,completed.text
    assert completed.json()["registered"]==COHORT_SIZE
    report=c.get("/api/v1/me/comparison").json()
    assert report["data_source"]=="DEMO_SCENARIO_ASSIGNED"
    assert report["participant_id"]==pid
    assert report["forward_started_at"] is None
    assert c.get(f"/api/v1/participants/{pid}/comparison").json()==report
    for _ in range(2):
        assert c.post("/api/v1/me/experiment/complete",json=body,headers=csrf(c)).status_code==200
    assert c.post("/api/v1/me/experiment/complete",json=config(["defense","nuclear"]),headers=csrf(c)).status_code==409
    rankings=c.get("/api/v1/comparison/rankings").json()
    assert rankings["total"]==COHORT_SIZE and rankings["reserved"]==0
    assert c.get("/api/v1/comparison/analytics").json()["comparable"]==COHORT_SIZE
    # Free design writes remain independent from experiment snapshot.
    fid=c.get("/api/v1/me/frontier").json()["min_variance_frontier_id"]
    assert c.post("/api/v1/me/onboarding/complete",json={"frontier_id":fid,"theme_ids":["nuclear"],"reason":"자유 설계"},headers=csrf(c)).status_code==200
    assert c.get("/api/v1/me/comparison").json()==report
    with env.factory() as s:
        assert s.scalar(select(func.count()).select_from(NavDaily).where(NavDaily.account_id.like(f"A-{pid}-%")))==0
        assert s.scalar(select(func.count()).select_from(PortfolioTarget).where(PortfolioTarget.account_id==f"A-{pid}-PERSONAL"))==2
        before=s.get(DemoSlot,"rehearsal:1").report_json
        seed(s);s.commit()
    # Dispose engine to prove fresh database connection, not in-memory state.
    env.factory.kw["bind"].dispose()
    with env.factory() as s:
        assert s.get(DemoSlot,"rehearsal:1").report_json==before
        assert s.get(User,uid).email_normalized==invite["email"]
        assert s.scalar(select(func.count()).select_from(User))==COHORT_SIZE+1
    # Preserved legacy accounts still access their own original report.
    assert c.post("/api/v1/auth/login",json={"email":EMAILS[-1],"password":PASSWORD}).status_code==200
    assert c.get("/api/v1/me/comparison").json()["data_source"]=="DEMO_SYNTHETIC"
    assert c.get("/api/v1/me/experiment").json()["status"]=="not_required"


def test_two_slots_pending_performance_and_no_cross_user_data(env, monkeypatch):
    invitations=setup(env, monkeypatch,2);c=env.client
    a,_=signup(c,invitations[0])
    assert c.post("/api/v1/me/experiment/complete",json=config(),headers=csrf(c)).status_code==200
    b,_=signup(c,invitations[1])
    assert c.get("/api/v1/me/experiment").json()["draft"]=={}
    # A non-catalog combination is real saved configuration, no fake performance.
    result=c.post("/api/v1/me/experiment/complete",json=config(["ai"]),headers=csrf(c))
    assert result.status_code==200,result.text
    assert result.json()["registered"]==COHORT_SIZE
    assert c.get("/api/v1/me/comparison").json()["metrics"] is None
    ranks=c.get("/api/v1/comparison/rankings").json()
    assert ranks["total"]==COHORT_SIZE-1 and len(ranks["pending"])==1
    assert ranks["pending"][0]["participant_id"]==b["participant_id"]
    assert a["participant_id"]!=b["participant_id"]
    assert c.get(f"/api/v1/participants/{a['participant_id']}").status_code==403


def test_concurrent_reservation_and_confirmation(env, monkeypatch):
    invitation=setup(env, monkeypatch)[0]
    password=secrets.token_urlsafe(22)
    def claim(_):
        with env.factory() as s:
            # Same transaction boundary as the deployed demo dependency.
            s.connection().exec_driver_sql("BEGIN IMMEDIATE")
            try:
                r=svc.register(s,invitation["email"],password,"simultaneous",invitation["invitation_code"])
                s.commit();return r["user_id"]
            except ApiError as e:
                s.rollback();return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(claim,range(2)))
    assert results.count("EMAIL_ALREADY_EXISTS")==1
    uid=next(r for r in results if r!="EMAIL_ALREADY_EXISTS")
    def finish(_):
        with env.factory() as s:
            s.connection().exec_driver_sql("BEGIN IMMEDIATE")
            r=svc.complete(s,s.get(User,uid),config());s.commit();return r["status"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(finish,range(2)))==["completed","completed"]
    with env.factory() as s:
        assert s.scalar(select(func.count()).select_from(User))==COHORT_SIZE+1
        pid=s.get(User,uid).participant_id
        assert s.scalar(select(func.count()).select_from(PortfolioTarget).where(PortfolioTarget.account_id==f"A-{pid}-PERSONAL"))==2
