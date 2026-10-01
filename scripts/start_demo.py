"""Start the isolated capstone demo: python scripts/start_demo.py [--no-browser]."""
import os
from pathlib import Path
import subprocess
import sys
import webbrowser

from start_local import check, is_port_in_use, npm_cmd, wait

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not check(["node", "--version"], "Node"):
        return 1
    npm = npm_cmd()
    if npm is None:
        print("npm not found. Install Node.js and add it to PATH.")
        return 1
    if not (ROOT / "web/node_modules").exists():
        print("Run cd web && npm ci first.")
        return 1
    for port in (8001, 3001):
        if is_port_in_use(port):
            print(f"Port {port} is already in use. Stop that server before starting the demo.")
            return 1
    # DATABASE_BACKEND 는 여기서 정하지 않는다. .env.local 한 곳이
    # SQLite/PostgreSQL 을 정하고, 없으면 기본값 sqlite 다.
    env = dict(os.environ, APP_PROFILE="local", CAPSTONE_DEMO="1",
               AUTH_COOKIE_SECURE="false", ALLOW_PUBLIC_REGISTRATION="false")
    price_source = ROOT / "data" / "forward_local.db"
    if price_source.is_file():
        env.setdefault("DESIGN_PRICE_SOURCE", str(price_source))
    subprocess.run([sys.executable, "-m", "src.local.seed_capstone"], cwd=ROOT, env=env, check=True)
    web_env = dict(env, NEXT_PUBLIC_APP_PROFILE="local", NEXT_PUBLIC_CAPSTONE_DEMO="1",
                   FASTAPI_INTERNAL_URL="http://127.0.0.1:8001", NEXT_DIST_DIR=".next-capstone")
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
            "--host", "127.0.0.1", "--port", "8001"], cwd=ROOT, env=env))
        processes.append(subprocess.Popen([npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", "3001"], cwd=ROOT / "web", env=web_env))
        if not wait("http://127.0.0.1:8001/health", 30) or not wait("http://127.0.0.1:3001/login", 45):
            print("Demo startup failed. Check the server output above.")
            return 1
        print("DEMO READY: http://127.0.0.1:3001/login · Ctrl+C stops both demo servers", flush=True)
        if "--no-browser" not in sys.argv: webbrowser.open("http://127.0.0.1:3001/login")
        processes[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
