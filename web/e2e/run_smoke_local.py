"""Local end-to-end smoke run: scratch backend + dev frontend + smoke script."""
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = "C:/Users/sind02/Desktop/valyuchain/robo-advisor"
WEB = ROOT + "/web"
DB = "C:/Users/sind02/AppData/Local/Temp/opencode/smoke.db"
EMAIL = "smoke@example.com"
PASSWORD = "smoke-test-passphrase-123"

if os.path.exists(DB):
    os.remove(DB)

# seed themes
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from datetime import date  # noqa: E402
from src.db.base import Base  # noqa: E402
from src.db.models.theme import Theme  # noqa: E402
from src.db.session import create_app_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

engine = create_app_engine(f"sqlite:///{DB}")
Base.metadata.create_all(engine)
S = sessionmaker(bind=engine, future=True)
with S() as s:
    for tid, name, ttype, ticker in [("ai", "AI", "theme", "AIQ")]:
        s.add(Theme(theme_id=tid, display_name=name, theme_type=ttype, ticker=ticker,
                    market="US", currency="USD", active=True,
                    valid_from=date(2026, 1, 1), valid_to=None,
                    universe_version="THEME_UNIVERSE_V0.1", inactive_reason=None))
    s.commit()

benv = dict(os.environ, APP_PROFILE="demo", DATABASE_BACKEND="sqlite",
            SQLITE_PATH=DB, ALLOW_PUBLIC_REGISTRATION="true")
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", "8000"],
    cwd=ROOT, env=benv, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
try:
    for _ in range(60):
        try:
            if urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).status == 200:
                break
        except Exception:
            time.sleep(2)
    else:
        print("backend never ready")
        sys.exit(2)
    # register smoke user directly on backend
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/register",
        data=json.dumps({"email": EMAIL, "password": PASSWORD,
                         "display_name": "Smoke"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    print("register:", urllib.request.urlopen(req, timeout=30).status)
    # frontend dev server
    npm = "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js"
    fenv = dict(os.environ, FASTAPI_INTERNAL_URL="http://127.0.0.1:8000")
    front = subprocess.Popen(["node", npm, "run", "dev", "--", "-p", "3000"],
                             cwd=WEB, env=fenv,
                             stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        for _ in range(90):
            try:
                if urllib.request.urlopen("http://localhost:3000/login", timeout=5).status == 200:
                    break
            except Exception:
                time.sleep(2)
        else:
            print("frontend never ready")
            sys.exit(2)
        print("frontend ready")
        senv = dict(os.environ, FRONTEND_URL="http://localhost:3000",
                    BACKEND_URL="http://127.0.0.1:8000",
                    SMOKE_EMAIL=EMAIL, SMOKE_PASSWORD=PASSWORD)
        r = subprocess.run([sys.executable, "scripts/deployment_smoke_test.py"],
                           cwd=ROOT, env=senv)
        sys.exit(r.returncode)
    finally:
        front.terminate()
finally:
    backend.terminate()
print("local smoke stack stopped")
