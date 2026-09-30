"""Start the lab meeting: python scripts/start_lab.py [--lan]."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from start_local import is_port_in_use, npm_cmd, wait

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lan", action="store_true", help="Allow devices on the same network to reach the web server")
    parser.add_argument("--dev", action="store_true", help="Use Next dev instead of a production build")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--port", type=int, default=3002)
    parser.add_argument("--api-port", type=int, default=8002)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".work/lab-meeting")
    args = parser.parse_args()
    if args.port == args.api_port or any(is_port_in_use(p) for p in (args.port, args.api_port)):
        parser.error("Choose two unused ports. Existing servers are never stopped automatically.")
    npm = npm_cmd()
    if npm is None:
        parser.error("npm not found. Install Node.js and add it to PATH.")
    directory = args.data_dir.resolve()
    env = dict(os.environ, APP_PROFILE="local", DATABASE_BACKEND="sqlite", CAPSTONE_DEMO="1",
        CAPSTONE_MARKET_COMPARISON="1", CAPSTONE_DATA_DIR=str(directory),
        AUTH_COOKIE_SECURE="false", ALLOW_PUBLIC_REGISTRATION="false",
        NEXT_PUBLIC_APP_PROFILE="local", NEXT_PUBLIC_CAPSTONE_DEMO="1", NEXT_PUBLIC_LAB_MEETING="1",
        NEXT_DIST_DIR=".next-capstone-lab-dev" if args.dev else ".next-capstone-lab",
        FASTAPI_INTERNAL_URL=f"http://127.0.0.1:{args.api_port}")
    subprocess.run([sys.executable, "-m", "src.local.lab_meeting", "--out", str(directory / "accounts.json")],
        cwd=ROOT, env=env, check=True)
    if not args.dev and (args.rebuild or not (ROOT / "web" / env["NEXT_DIST_DIR"] / "BUILD_ID").is_file()):
        subprocess.run([npm, "run", "build"], cwd=ROOT / "web", env=env, check=True)
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app",
            "--host", "127.0.0.1", "--port", str(args.api_port)], cwd=ROOT, env=env))
        processes.append(subprocess.Popen([npm, "run", "dev" if args.dev else "start", "--",
            "--hostname", "0.0.0.0" if args.lan else "127.0.0.1", "--port", str(args.port)],
            cwd=ROOT / "web", env=env))
        if not wait(f"http://127.0.0.1:{args.api_port}/health", 30) or not wait(f"http://127.0.0.1:{args.port}/login", 45):
            raise RuntimeError("Lab server startup failed; inspect server output.")
        print(f"LAB READY: http://127.0.0.1:{args.port}/login", flush=True)
        if args.lan:
            print(f"Same-network participants: http://<this computer's LAN IP>:{args.port}/login", flush=True)
        print("Ctrl+C stops both lab servers. Accounts and portfolios stay on disk.", flush=True)
        processes[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
