"""Browser + concurrency + restart acceptance in a disposable lab database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_enrollment import ROOT, free_port, wait


def main():
    scratch = Path(tempfile.mkdtemp(prefix="robo-lab-qa-"))
    api_port, web_port = free_port(), free_port()
    while web_port == api_port:
        web_port = free_port()
    env = dict(os.environ, APP_PROFILE="local", CAPSTONE_DEMO="1", CAPSTONE_MARKET_COMPARISON="1",
        DATABASE_BACKEND="sqlite", CAPSTONE_DATA_DIR=str(scratch), AUTH_COOKIE_SECURE="false",
        NEXT_PUBLIC_CAPSTONE_DEMO="1", NEXT_PUBLIC_APP_PROFILE="local", NEXT_PUBLIC_LAB_MEETING="1",
        NEXT_DIST_DIR=".next-capstone-lab", FASTAPI_INTERNAL_URL=f"http://127.0.0.1:{api_port}",
        E2E_BASE_URL=f"http://127.0.0.1:{web_port}", E2E_LAB_ACCOUNTS=str(scratch / "accounts.json"),
        E2E_OUTPUT_DIR=str(scratch / "browser-results"))
    subprocess.run([sys.executable, "-m", "src.local.lab_meeting", "--out", env["E2E_LAB_ACCOUNTS"]],
        cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    print(f"Isolated lab validation: {scratch}", flush=True)
    processes = []
    with (scratch / "api.log").open("w") as api_log, (scratch / "web.log").open("w") as web_log:
        api_cmd = [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", str(api_port)]
        try:
            processes.append(subprocess.Popen(api_cmd, cwd=ROOT, env=env, stdout=api_log, stderr=api_log))
            processes.append(subprocess.Popen(["npm", "run", "start", "--", "--hostname", "127.0.0.1", "--port", str(web_port)],
                cwd=ROOT / "web", env=env, stdout=web_log, stderr=web_log))
            wait(f"http://127.0.0.1:{api_port}/health", processes[0])
            wait(f"http://127.0.0.1:{web_port}/login", processes[1])
            result = subprocess.run(["npx", "playwright", "test", "--config", "playwright.lab.config.ts"], cwd=ROOT / "web", env=env)
            if result.returncode:
                return result.returncode
            import httpx
            account = json.loads((scratch / "accounts.json").read_text())["accounts"][0]
            def snapshot():
                with httpx.Client(base_url=env["E2E_BASE_URL"], timeout=60) as client:
                    client.post("/api/v1/auth/login", json=account).raise_for_status()
                    response = client.get("/api/v1/comparison/analytics")
                    response.raise_for_status()
                    return response.json()
            before = snapshot()
            processes[0].terminate()
            processes[0].wait(timeout=10)
            processes[0] = subprocess.Popen(api_cmd, cwd=ROOT, env=env, stdout=api_log, stderr=api_log)
            wait(f"http://127.0.0.1:{api_port}/health", processes[0])
            assert snapshot() == before and before["comparable"] == 13
            print("Backend restart: all 13 saved configurations and comparisons preserved.", flush=True)
            return 0
        finally:
            for p in processes:
                p.terminate()
            for p in processes:
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
            (scratch / "accounts.json").unlink(missing_ok=True)
            (scratch / "accounts.md").unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
