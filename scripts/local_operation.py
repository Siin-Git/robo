"""Initialize/start/restart/run/status the persistent real-date local paper ledger."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.local.operation import environment, initialize, read_settings, run_daily, ledger_summary, exclusive
from start_local import is_port_in_use, npm_cmd, wait


def serve(directory):
    settings = read_settings(directory)
    if any(is_port_in_use(p) for p in (settings['web_port'],settings['api_port'])):
        raise ValueError('An operation port is busy; existing servers are preserved.')
    env = environment(directory, settings['api_port'])
    processes = []
    with exclusive(directory, 'servers'):
        pidfile = directory/'servers.json'
        try:
            for command,cwd,log in [
                ([sys.executable,'-m','uvicorn','src.api.main:app','--host','127.0.0.1','--port',str(settings['api_port'])],ROOT,'api.log'),
                ([npm_cmd(),'run','dev','--','--hostname','127.0.0.1','--port',str(settings['web_port'])],ROOT/'web','web.log')]:
                with (directory/'logs'/log).open('a') as output:
                    processes.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=output,stderr=output,start_new_session=True))
            pidfile.write_text(json.dumps({'controller':os.getpid(),'groups':[p.pid for p in processes]}))
            if not wait(f'http://127.0.0.1:{settings["api_port"]}/health',30) or not wait(f'http://127.0.0.1:{settings["web_port"]}/login',45):
                raise RuntimeError('Operation startup failed; inspect logs/api.log and logs/web.log.')
            print(f'REAL CLOCK / REAL MARKET PAPER READY: http://localhost:{settings["web_port"]}/login',flush=True)
            print('Persistent SQLite data: '+str(directory),flush=True)
            print('No decisions/market returns fabricated. Ctrl+C stops only these servers.',flush=True)
            processes[0].wait()
        except KeyboardInterrupt:
            pass
        finally:
            for p in processes:
                if p.poll() is None:
                    os.killpg(p.pid,signal.SIGTERM)
            for p in processes:
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
            pidfile.unlink(missing_ok=True)


def stop(directory):
    pidfile = directory/'servers.json'
    if not pidfile.exists():
        print('Operation servers already stopped.');return
    pid = json.loads(pidfile.read_text())['controller']
    command = subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
    paths = (str(directory), os.path.relpath(directory, ROOT))
    if 'local_operation.py serve' not in command or not any('--data-dir '+p in command for p in paths):
        raise RuntimeError('Server PID identity differs; no process was stopped.')
    os.kill(pid,signal.SIGINT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','serve','stop','daily','status'])
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--web-port',type=int,default=3073)
    parser.add_argument('--api-port',type=int,default=8073)
    args=parser.parse_args();directory=args.data_dir.resolve()
    if args.action=='init':print(json.dumps(initialize(directory,args.web_port,args.api_port),indent=2))
    elif args.action=='serve':serve(directory)
    elif args.action=='stop':stop(directory)
    elif args.action=='daily':return run_daily(directory)
    else:
        read_settings(directory);print(json.dumps(ledger_summary(directory),indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
