"""Reliable E2E runner: backend lifecycle + playwright in one process."""
import os
import subprocess
import sys
import time
import urllib.request

ROOT = "C:/Users/sind02/Desktop/valyuchain/robo-advisor"
WEB = ROOT + "/web"
DB = "C:/Users/sind02/AppData/Local/Temp/opencode/e2e.db"

if os.name == "nt":
    # A stale dev server on :3000 would be reused with old code; clear it.
    subprocess.run(["taskkill", "/F", "/IM", "node.exe"],
                   capture_output=True)

backend_env = dict(os.environ, APP_PROFILE="demo", DATABASE_BACKEND="sqlite",
                   SQLITE_PATH=DB, ALLOW_PUBLIC_REGISTRATION="true")
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", "8000"],
    cwd=ROOT, env=backend_env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            if urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).status == 200:
                break
        except Exception:
            time.sleep(2)
    else:
        print("backend never became ready")
        sys.exit(2)
    print("backend ready")
    npm = "C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js"
    env = dict(os.environ, FASTAPI_INTERNAL_URL="http://127.0.0.1:8000")
    cmd = ["node", npm, "exec", "playwright", "--", "test", "--reporter=line"] + sys.argv[1:]
    r = subprocess.run(cmd, cwd=WEB, env=env)
    sys.exit(r.returncode)
finally:
    backend.terminate()
    print("backend stopped")
