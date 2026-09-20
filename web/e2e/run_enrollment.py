"""Isolated, repeatable browser acceptance: python web/e2e/run_enrollment.py.

Creates a fresh scratch DB and invitations outside the repository. Existing
accounts and the presenter's running servers are never reset or stopped.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait(url, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Test server stopped. Inspect scratch log files.")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(.5)
    raise RuntimeError("Test server startup timed out.")


def main():
    scratch = Path(tempfile.mkdtemp(prefix="robo-enrollment-"))
    api_port, web_port = free_port(), free_port()
    env = dict(os.environ, APP_PROFILE="local", CAPSTONE_DEMO="1", DATABASE_BACKEND="sqlite",
        CAPSTONE_DATA_DIR=str(scratch), AUTH_COOKIE_SECURE="false", NEXT_PUBLIC_CAPSTONE_DEMO="1",
        NEXT_PUBLIC_APP_PROFILE="local", NEXT_DIST_DIR=".next-enrollment-e2e",
        FASTAPI_INTERNAL_URL=f"http://127.0.0.1:{api_port}", E2E_BASE_URL=f"http://127.0.0.1:{web_port}",
        E2E_INVITE_FILE=str(scratch / "invitations.json"), E2E_OUTPUT_DIR=str(scratch / "browser-results"))
    subprocess.run([sys.executable, "-m", "src.local.seed_capstone"], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "-m", "src.local.demo_cohort", "--name", "browser-check",
        "--email", "browser-first@example.com", "--email", "browser-second@example.com",
        "--out", env["E2E_INVITE_FILE"]], cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    processes = []
    print(f"Isolated browser validation · scratch logs: {scratch}", flush=True)
    with (scratch / "api.log").open("w") as api_log, (scratch / "web.log").open("w") as web_log:
        try:
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
                "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=api_log))
            processes.append(subprocess.Popen(["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(web_port)],
                cwd=ROOT / "web", env=env, stdout=web_log, stderr=web_log))
            wait(f"http://127.0.0.1:{api_port}/health", processes[0])
            wait(f"http://127.0.0.1:{web_port}/signup", processes[1])
            result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.enrollment.config.ts"], cwd=ROOT / "web", env=env)
            if result.returncode == 0:
                import httpx
                sys.path.insert(0, str(ROOT))
                from src.local.capstone import EMAILS, PASSWORD
                def snapshot():
                    with httpx.Client(base_url=f"http://127.0.0.1:{api_port}") as client:
                        response = client.post("/api/v1/auth/login", json={"email": EMAILS[0], "password": PASSWORD})
                        response.raise_for_status()
                        data = client.get("/api/v1/comparison/analytics")
                        data.raise_for_status()
                        return data.json()
                before = snapshot()
                processes[0].terminate()
                processes[0].wait(timeout=10)
                processes[0] = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
                    "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=api_log)
                wait(f"http://127.0.0.1:{api_port}/health", processes[0])
                after = snapshot()
                assert before == after and after["comparable"] == 13
                assert sum(r["data_source"] == "DEMO_SCENARIO_ASSIGNED" for r in after["reports"]) == 2
                print("API process restart: 13 reports including both new configurations preserved.", flush=True)
            return result.returncode
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            # No reusable invitation secrets left after automated tests.
            (scratch / "invitations.json").unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
