"""Validate v1 and capstone in independent scratch DBs; never reset user data."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from run_enrollment import ROOT, free_port, wait


def main():
    result = subprocess.run([sys.executable, str(ROOT / "web/e2e/run_enrollment.py")],
        env=dict(os.environ, E2E_CONFIG="playwright.integration.config.ts"))
    if result.returncode:
        return result.returncode
    scratch = Path(tempfile.mkdtemp(prefix="robo-v1-regression-"))
    api_port, web_port = free_port(), free_port()
    env = dict(os.environ, APP_PROFILE="demo", CAPSTONE_DEMO="0", DATABASE_BACKEND="sqlite",
        SQLITE_PATH=str(scratch / "v1.db"), AUTH_COOKIE_SECURE="false", ALLOW_PUBLIC_REGISTRATION="true",
        NEXT_PUBLIC_CAPSTONE_DEMO="0", NEXT_PUBLIC_APP_PROFILE="demo", NEXT_DIST_DIR=".next-integration-v1",
        FASTAPI_INTERNAL_URL=f"http://127.0.0.1:{api_port}", E2E_BASE_URL=f"http://127.0.0.1:{web_port}",
        E2E_OUTPUT_DIR=str(scratch / "browser-results"), DESIGN_PRICE_SOURCE=str(ROOT / "data/forward_local.db"))
    seed_code = """
from datetime import date
import yaml
from src.db.base import Base
from src.db.session import create_app_engine, session_factory
from src.db.models.theme import Theme
from src.api.design_prices import load_reference_prices
engine=create_app_engine()
Base.metadata.create_all(engine)
with session_factory(engine)() as s:
    for entry in yaml.safe_load(open('config/themes_v01.yaml'))['themes']:
        data={k:v for k,v in entry.items() if k in Theme.__table__.columns.keys()}
        for key in ('valid_from','valid_to'):
            if isinstance(data.get(key),str): data[key]=date.fromisoformat(data[key])
        s.add(Theme(**data))
    load_reference_prices(s)
    s.commit()
"""
    subprocess.run([sys.executable, "-c", seed_code], cwd=ROOT, env=env, check=True)
    processes = []
    print(f"Original v1 browser regression · scratch logs: {scratch}", flush=True)
    with (scratch / "api.log").open("w") as api_log, (scratch / "web.log").open("w") as web_log:
        try:
            processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
                "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=api_log))
            processes.append(subprocess.Popen(["npm", "run", "dev", "--", "--hostname", "127.0.0.1", "--port", str(web_port)],
                cwd=ROOT / "web", env=env, stdout=web_log, stderr=web_log))
            wait(f"http://127.0.0.1:{api_port}/health", processes[0])
            wait(f"http://127.0.0.1:{web_port}/signup", processes[1])
            return subprocess.run(["npx", "playwright", "test", "--config", "playwright.integration.config.ts"],
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
