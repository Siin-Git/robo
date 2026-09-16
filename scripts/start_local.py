"""One-command local launcher (cross-platform, Python).

Usage:
    python scripts/start_local.py [--no-browser]
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def check(cmd: list[str], label: str) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=10)
        return True
    except Exception:
        print(f"{label} not found. Install it and add to PATH.")
        return False


def wait(url: str, secs: int = 40) -> bool:
    for _ in range(secs):
        try:
            if urllib.request.urlopen(url, timeout=5).status in (200, 302):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def clean_next() -> None:
    """Remove web/.next so `next dev` never reuses a production build.

    A production `next build` leaves server chunks/manifests that `next dev`
    can reference as stale (e.g. Cannot find module './276.js').
    """
    import shutil
    nxt = WEB / ".next"
    if nxt.exists():
        print("Cleaning stale web/.next (prevents dev/prod chunk mismatch)...")
        shutil.rmtree(nxt, ignore_errors=True)


def main() -> int:
    print("========================================")
    print("ROBO ADVISOR — LOCAL PREVIEW")
    print("========================================\n")
    if not check([sys.executable, "--version"], "Python"):
        return 1
    if not check(["node", "--version"], "Node"):
        return 1

    local_db = ROOT / "data" / "forward_local.db"
    if not local_db.exists():
        print("Local DB not found.")
        ans = input("Initialize local DB now? [Y/n] ").strip().lower()
        if ans not in ("", "y", "yes"):
            return 0
        env = dict(os.environ, APP_PROFILE="local", DATABASE_BACKEND="sqlite")
        if subprocess.run([sys.executable, "-m", "src.local.init"], cwd=ROOT, env=env).returncode != 0:
            return 1

    # Ensure LOCAL test account (LOCAL only, env-driven, never LIVE).
    try:
        env_acct = dict(os.environ, APP_PROFILE="local", DATABASE_BACKEND="sqlite",
                        PYTHONPATH=str(ROOT))
        # Forward LOCAL_* env vars if present; otherwise fallback generates temp pw once.
        result = subprocess.run([sys.executable, "-m", "src.local.ensure_test_account"],
                                cwd=ROOT, env=env_acct)
        # ensure_test_account prints the banner itself; we don't fail launch on it.
        _ = result.returncode
    except Exception:
        pass

    print("Profile:\nLOCAL\n")
    print(f"Database:\ndata/forward_local.db\n")
    print("FastAPI:\nhttp://127.0.0.1:8000\n")
    print("Web:\nhttp://localhost:3000\n")
    print("Live DB:\nNOT USED\n")

    if not (WEB / "node_modules").exists():
        print("Frontend dependencies missing.")
        ans = input("Run npm install now? [Y/n] ").strip().lower()
        if ans in ("", "y", "yes"):
            subprocess.run(["npm", "install"], cwd=WEB, check=False)

    # Fail fast on stale servers: a lingering uvicorn (old code without new
    # routers) or a lingering `next dev` (old .next chunks) causes confusing
    # 404/chunk errors. Never auto-kill other projects' node processes.
    if is_port_in_use(8000):
        print("Port 8000 already in use (stale backend?).")
        print("Stop the old uvicorn for this project first, then retry.")
        return 1
    if is_port_in_use(3000):
        print("Port 3000 already in use (stale Next dev?).")
        print("Stop the old `next dev` for this project first, then retry.")
        return 1
    clean_next()

    env_api = dict(os.environ, APP_PROFILE="local", DATABASE_BACKEND="sqlite",
                   PYTHONPATH=str(ROOT))
    env_web = dict(os.environ, NEXT_PUBLIC_APP_PROFILE="local",
                   FASTAPI_INTERNAL_URL="http://127.0.0.1:8000")

    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
                            "--host", "127.0.0.1", "--port", "8000"],
                           cwd=ROOT, env=env_api)
    web = subprocess.Popen(["npm", "run", "dev"], cwd=WEB, env=env_web)
    try:
        print("Backend:", "READY" if wait("http://127.0.0.1:8000/health", 40) else "NOT YET READY")
        print("Frontend:", "READY" if wait("http://localhost:3000/login", 90) else "NOT YET READY")
        if "--no-browser" not in sys.argv:
            print("\nOpening browser...")
            import webbrowser
            webbrowser.open("http://localhost:3000/login")
        print("========================================")
        print("Close with Ctrl+C (both servers will stop).")
        print("========================================")
        api.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for p in (web, api):
            try:
                p.terminate()
            except Exception:
                pass
        try:
            api.wait(timeout=5)
        except Exception:
            api.kill()
        try:
            web.wait(timeout=5)
        except Exception:
            web.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
