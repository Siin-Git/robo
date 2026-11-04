"""Production-build acceptance using only fresh disposable local databases.

Build first: NEXT_PUBLIC_CAPSTONE_DEMO=1 NEXT_PUBLIC_LAB_MEETING=1 npm run build
Run from repository root: .venv/bin/python web/e2e/run_rehearsal.py
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_enrollment import ROOT, free_port, wait


def main():
    scratch = Path(tempfile.mkdtemp(prefix="robo-rehearsal-", dir="/private/tmp"))
    fixture = scratch / "fixture"
    subprocess.run([sys.executable, "scripts/seed_verification_ui_fixture.py", "--directory", str(fixture)],
                   cwd=ROOT, check=True)
    api_port, web_port = free_port(), free_port()
    env = dict(os.environ, APP_PROFILE="local", CAPSTONE_DEMO="1", CAPSTONE_MARKET_COMPARISON="1",
        DATABASE_BACKEND="sqlite", DATABASE_URL="", CAPSTONE_DESIGN_DATABASE_URL="",
        CAPSTONE_DATA_DIR=str(fixture), AUTH_COOKIE_SECURE="false", ALLOW_PUBLIC_REGISTRATION="false",
        NEXT_PUBLIC_CAPSTONE_DEMO="1", NEXT_PUBLIC_LAB_MEETING="1",
        FASTAPI_INTERNAL_URL=f"http://127.0.0.1:{api_port}", E2E_BASE_URL=f"http://127.0.0.1:{web_port}",
        E2E_OPERATIONS_DATA_DIR=str(fixture), E2E_OUTPUT_DIR=str(scratch / "browser-results"))
    processes = []
    print(f"Isolated rehearsal acceptance · logs: {scratch}", flush=True)
    with (scratch / "api.log").open("w") as api_log, (scratch / "web.log").open("w") as web_log:
        try:
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
                "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=api_log))
            processes.append(subprocess.Popen(["npm", "run", "start", "--", "--hostname", "127.0.0.1", "--port", str(web_port)],
                cwd=ROOT / "web", env=env, stdout=web_log, stderr=web_log))
            wait(f"http://127.0.0.1:{api_port}/health", processes[0])
            wait(f"http://127.0.0.1:{web_port}/login", processes[1])
            return subprocess.run(["npx", "playwright", "test", "--config", "playwright.rehearsal.config.ts"],
                                  cwd=ROOT / "web", env=env).returncode
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
