"""Prepare/run the marked local competition; never accepts PostgreSQL targets."""
import argparse
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def initialize(directory, web_port=3097, api_port=8097):
    """Create new private local stores; refuse existing directories."""
    import tempfile
    if not directory.is_relative_to(Path(tempfile.gettempdir()).resolve()) or directory.exists():
        raise ValueError("Initialize requires a NEW disposable temporary directory")
    directory.mkdir(mode=0o700)
    (directory / "local-replay.json").write_text(json.dumps({"kind":"LOCAL_COMPETITION_REPLAY",
        "source":str(ROOT), "web_port":web_port, "api_port":api_port}))
    env={"APP_PROFILE":"local", "CAPSTONE_DEMO":"1", "CAPSTONE_MARKET_COMPARISON":"1",
         "DATABASE_BACKEND":"sqlite", "DATABASE_URL":"", "CAPSTONE_DESIGN_DATABASE_URL":"",
         "CAPSTONE_DATA_DIR":str(directory), "DESIGN_PRICE_SOURCE":"", "CAPSTONE_LAB_ACCOUNTS_JSON":"",
         "CAPSTONE_INVITATIONS_JSON":"", "AUTH_COOKIE_SECURE":"false", "ALLOW_PUBLIC_REGISTRATION":"false",
         "FORWARD_EXECUTOR":"notebook", "TZ":"Asia/Seoul", "NEXT_PUBLIC_APP_PROFILE":"local",
         "NEXT_PUBLIC_CAPSTONE_DEMO":"1", "NEXT_PUBLIC_LAB_MEETING":"1",
         "NEXT_DIST_DIR":".next-competition-replay", "FASTAPI_INTERNAL_URL":f"http://127.0.0.1:{api_port}"}
    (directory / "environment.json").write_text(json.dumps(env))
    environment(directory)
    from alembic import command
    from alembic.config import Config
    for name in ("capstone_demo.db", "portfolio_design.db"):
        cfg=Config(str(ROOT/'alembic.ini'));cfg.set_main_option('script_location',str(ROOT/'migrations'))
        cfg.attributes['database_url']=f"sqlite:///{directory/name}"
        command.upgrade(cfg,'head')
    import subprocess
    subprocess.run([sys.executable,'-m','src.local.lab_meeting','--name','local-competition-replay',
        '--out',str(directory/'accounts.json')],cwd=ROOT,env=os.environ.copy(),check=True)


def fetch_prices(directory):
    """Capture raw provider observations. No fallback, fill, or sealed-run refresh."""
    from src.data.provider import get_default_provider
    from src.forward.config import load_forward_config,resolve
    from src.forward.frozen import load_frozen_benchmark
    import yaml
    if (directory/'run.json').exists():
        raise ValueError("Sealed run prices are preserved; use a new replay directory")
    cfg=load_forward_config();_,meta=load_frozen_benchmark(resolve(cfg['frozen_dir']))
    tickers={('__FX__' if a=='FX_USDKRW' else a):t for a,t in meta['tickers'].items()}
    chosen={t for s in prepare_participants(directory) for t in s['theme_ids']}
    themes=yaml.safe_load((ROOT/'config/themes_v01.yaml').read_text())['themes']
    tickers.update({'theme:'+t['theme_id']:t['ticker'] for t in themes if t['theme_id'] in chosen})
    provider=get_default_provider();end=date.today()-timedelta(days=1);start=end-timedelta(days=60)
    prices={};failures=[]
    for asset,ticker in tickers.items():
        try:
            series=provider.get_price_history(ticker,start,end)
            prices[asset]={stamp.date().isoformat():float(value) for stamp,value in series.items()}
        except Exception:
            failures.append({'asset':asset,'ticker':ticker,'reason':'PROVIDER_FETCH_FAILED'})
    if failures:
        (directory/'price-failures.json').write_text(json.dumps(failures,indent=2))
        raise RuntimeError("Real source fetch failed: "+', '.join(f["asset"] for f in failures))
    data={'kind':'REAL_MARKET_PRICES','provider':type(provider).__name__,
          'retrieved_at':datetime.now(timezone.utc).isoformat(),'request_start':str(start),'request_end':str(end),
          'prices':prices,'tickers':tickers}
    (directory/'market-prices.json').write_text(json.dumps(data,indent=2))
    return {'assets':len(prices),'provider':data['provider'],'request_start':str(start),'request_end':str(end)}


def servers(directory, action):
    """Manage only this launcher's process groups, leaving all other ports alone."""
    import signal
    import subprocess
    from scripts.start_local import is_port_in_use, wait
    marker=json.loads((directory/'local-replay.json').read_text())
    if Path(marker['source']).resolve()!=ROOT:
        raise ValueError("Use the original replay worktree launcher")
    pidfile=directory/'servers.json'
    previous=json.loads(pidfile.read_text()) if pidfile.exists() else []
    def ours(item):
        try:
            if os.getpgid(item['pid'])!=item['pid']:return False
            cwd=subprocess.check_output(['lsof','-a','-p',str(item['pid']),'-d','cwd','-Fn'],text=True)
            return 'n'+str(ROOT if item['name']=='api' else ROOT/'web') in cwd.splitlines()
        except (ProcessLookupError,subprocess.CalledProcessError):return False
    owned=[item for item in previous if ours(item)]
    if action=='stop':
        for item in owned:os.killpg(item['pid'],signal.SIGTERM)
        return {'stopped':len(owned),'data_preserved':True}
    url=f"http://127.0.0.1:{marker['web_port']}"
    if len(owned)==2 and wait(url+'/login',5):return {'url':url,'reused':True}
    if owned:raise RuntimeError("Partial server state; stop this run's servers before restarting")
    if any(is_port_in_use(marker[k]) for k in ('api_port','web_port')):
        raise RuntimeError("Port occupied; no existing server will be stopped")
    logs=directory/'logs';logs.mkdir(exist_ok=True)
    commands=[('api',[sys.executable,'-m','uvicorn','src.api.main:app','--host','127.0.0.1',
                    '--port',str(marker['api_port']),'--reload','--reload-dir','src'],ROOT),
              ('web',['node',str(ROOT/'web/node_modules/next/dist/bin/next'),'dev','--hostname','127.0.0.1',
                      '--port',str(marker['web_port'])],ROOT/'web')]
    started=[]
    for name,cmd,cwd in commands:
        with (logs/(name+'.log')).open('a') as log:
            child=subprocess.Popen(cmd,cwd=cwd,env=os.environ.copy(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        started.append({'name':name,'pid':child.pid})
        pidfile.write_text(json.dumps(started))
    if not wait(f"http://127.0.0.1:{marker['api_port']}/health",40) or not wait(url+'/login',40):
        raise RuntimeError("Server startup incomplete; inspect this run's logs")
    return {'url':url,'reused':False}


def environment(directory):
    directory = Path(directory).resolve()
    from src.forward.replay import local_directory
    local_directory(directory)
    env = json.loads((directory / "environment.json").read_text())
    if env["DATABASE_BACKEND"] != "sqlite" or Path(env["CAPSTONE_DATA_DIR"]).resolve() != directory:
        raise ValueError("Only this separate local SQLite environment is accepted")
    env.update(DATABASE_URL="", CAPSTONE_DESIGN_DATABASE_URL="", COMPETITION_REPLAY_DIR=str(directory))
    os.environ.update(env)
    return env


def prepare_participants(directory):
    """Use login, draft, preview and final-confirmation HTTP routes, at real time."""
    from fastapi.testclient import TestClient
    from src.api.main import app
    accounts = json.loads((directory / "accounts.json").read_text())["accounts"]
    options = [[], ["ai"], ["robotics"], ["nuclear"], ["power_grid"],
               ["cybersecurity"], ["cloud_data_center"], ["ai", "robotics"],
               ["nuclear", "power_grid"], ["cybersecurity", "cloud_data_center"]]
    selections = []
    with TestClient(app) as client:
        for index, account in enumerate(accounts):
            client.cookies.clear()
            result = client.post("/api/v1/auth/login", json={k:account[k] for k in ("email", "password")})
            if result.status_code != 200:
                raise RuntimeError(f"Local participant {index + 1} login failed")
            info = client.get("/api/v1/me").json()
            frontier = client.get("/api/v1/me/frontier").json()
            point = frontier["points"][round(index * (len(frontier["points"]) - 1) / 14)]
            settings = {"frontier_id": point["frontier_id"], "theme_ids": options[index % len(options)],
                        "reason": "LOCAL DEMO CONFIGURATION — historical counterfactual only",
                        "rebalance_frequency": "monthly" if index % 2 == 0 else "quarterly"}
            headers = {"X-CSRF-Token": client.cookies["ra_csrf"]}
            prior = client.get("/api/v1/me/decisions").json()["items"]
            if not prior:
                for method, path, body in [(client.put, "draft", {**settings, "current_step":"risk"}),
                                          (client.post, "preview", {k:settings[k] for k in ("frontier_id", "theme_ids")}),
                                          (client.post, "complete", settings)]:
                    response = method("/api/v1/me/onboarding/" + path, headers=headers, json=body)
                    if response.status_code != 200:
                        raise RuntimeError(f"Local participant {index + 1} {path} failed: HTTP {response.status_code}")
            selections.append({"user_id": info["user_id"], "participant_id": info["participant_id"],
                               "configuration_kind":"LOCAL_DEMO", **settings})
    return selections


def prepare(directory):
    from src.forward import competition as gate
    from src.forward.replay import manifest, local_directory, save_state, exclusive
    from src.forward.config import load_forward_config, resolve
    from src.forward.frozen import load_frozen_benchmark
    from src.forward.prices import align_daily_krw, upsert_prices, HEDGED
    import pandas as pd
    directory = local_directory(directory)
    if (directory / "run.json").exists():
        return manifest(directory)
    with exclusive(directory):
        selections = prepare_participants(directory)
        raw = json.loads((directory / "market-prices.json").read_text())
        if raw.get("kind") != "REAL_MARKET_PRICES":
            raise ValueError("Require prices fetched from the real configured provider")
        target = directory / "replay_ledger.db"
        building = directory / "preparing.json"
        if target.exists() and not building.exists():
            raise ValueError("Unmarked existing replay ledger is preserved")
        if building.exists() and json.loads(building.read_text()) != {"kind":"LOCAL_REPLAY_PREPARATION", "directory":str(directory)}:
            raise ValueError("Preparation journal does not belong to this run")
        if target.exists():
            with sqlite3.connect(target) as previous:
                if any(previous.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("orders", "trades", "nav_daily")):
                    raise ValueError("Incomplete preparation contains history; preserve it for inspection")
        building.write_text(json.dumps({"kind":"LOCAL_REPLAY_PREPARATION", "directory":str(directory)}))
        with sqlite3.connect(directory / "portfolio_design.db") as source:
            if any(source.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("orders", "trades", "nav_daily")):
                raise ValueError("Require a fresh demo design store, without operating history")
            with sqlite3.connect(target) as dest:
                source.backup(dest)
        with sqlite3.connect(target) as con:
            con.row_factory = sqlite3.Row
            cohort = gate.read_cohort()
            members, ready, all_ready = gate.readiness(con, cohort)
            if not all_ready or ready != 15:
                raise RuntimeError("The local demo must have all 15 confirmed participants")
            cfg = load_forward_config(); ft = cfg["forward_test"]
            core, _ = load_frozen_benchmark(resolve(cfg["frozen_dir"]))
            weights = {}
            for member in members:
                decision = con.execute("SELECT weights_json FROM portfolio_decisions WHERE decision_id=?", (member["decision_id"],)).fetchone()
                for aid in member["account_ids"]:
                    weights[aid] = json.loads(decision[0]) if aid == member["personal_account_id"] else core
            assets = {asset for w in weights.values() for asset, weight in w.items() if asset != "cash" and weight > 0} | {"__FX__"}
            missing = sorted(assets - raw["prices"].keys())
            if missing:
                raise RuntimeError("Missing provider assets: " + ", ".join(missing))
            common = sorted(set.intersection(*[set(raw["prices"][asset]) for asset in assets]))
            common = [d for d in common if d < date.today().isoformat() and date.fromisoformat(d).weekday() < 5]
            if len(common) < 10:
                raise RuntimeError("Fewer than 10 complete common trading observations")
            dates = common[-10:]
            union = set.union(*[set(raw["prices"][asset]) for asset in assets])
            excluded = [{"date":d, "missing_assets":[a for a in sorted(assets) if d not in raw["prices"][a]],
                         "reason":"SOURCE_OBSERVATION_MISSING; not filled or interpolated"}
                        for d in sorted(union) if dates[0] <= d <= dates[-1] and d not in dates and date.fromisoformat(d).weekday() < 5]
            index = pd.to_datetime(dates)
            panels = {a:pd.Series(raw["prices"][a], dtype=float).rename_axis("date") for a in assets}
            panels = {a:pd.Series([float(s[d]) for d in dates], index=index) for a,s in panels.items()}
            fx = panels.pop("__FX__")
            # All dates are complete before calling the existing currency rule;
            # its forward-fill therefore does not replace a missing observation.
            panel = align_daily_krw(panels, fx, HEDGED)
            panel["__FX__"] = fx
            if len(panel) != 10 or not all(float(v) > 0 for v in panel.to_numpy().ravel()):
                raise RuntimeError("Invalid real price/FX coverage")
            upsert_prices(con, panel, "HISTORICAL_REPLAY_REAL_PRICES")
            latest_effective = max(date.fromisoformat(m["effective_date"]) for m in members)
            forward_start = max(date.today(), latest_effective) + timedelta(days=1)
            # Only this new local run is armed. The original design DB and any
            # operating T0 remain unchanged. This is not a production start.
            gate.schedule_start(con, forward_start.isoformat())
            run = {"kind":"HISTORICAL_REPLAY", "run_id":str(uuid4()), "required":15,
                   "created_at":datetime.now(timezone.utc).isoformat(),
                   "configuration_kind":"LOCAL_DEMO", "members":members, "weights":weights,
                   "start":dates[0], "end":dates[-1], "dates":dates,
                   "forward_start":forward_start.isoformat(), "excluded_dates":excluded,
                   "initial_capital_krw":float(ft["initial_capital_krw"]),
                   "price_basis":{"provider":raw["provider"], "retrieved_at":raw["retrieved_at"],
                       "raw_sha256":sha256((directory / "market-prices.json").read_bytes()).hexdigest(),
                       "tickers":{a:raw["tickers"][a] for a in sorted(assets)},
                       "calendar":"last 10 complete common source sessions; exclusions explicit",
                       "prices":"existing provider adjusted close when available, otherwise close",
                       "currency_rule":"existing align_daily_krw: unhedged USD multiplied by FX; KR/native and HEDGED levels unchanged",
                       "hedged_assets":sorted(HEDGED), "cost_bps":ft["costs"]["trading_cost_bps"],
                       "execution":"existing engine next available close at replay start; equal seed capital"},
                   "selections":selections}
            encoded = json.dumps(run, ensure_ascii=False, indent=2)
            save_state(con, "replay_run_id", run["run_id"])
            save_state(con, "replay_manifest_sha256", sha256(encoded.encode()).hexdigest())
            save_state(con, "replay_status", "PREPARED")
            temporary = directory / "run.json.preparing"
            temporary.write_text(encoded)
            temporary.replace(directory / "run.json")
            building.unlink()
            return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "fetch", "prepare", "run", "status", "serve", "stop"])
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port",type=int,default=3097)
    parser.add_argument("--api-port",type=int,default=8097)
    args = parser.parse_args(); directory = args.directory.resolve()
    if args.action=="init":
        initialize(directory,args.port,args.api_port)
        return 0
    environment(directory)
    if args.action in ("serve","stop"):
        print(json.dumps(servers(directory,args.action)))
    elif args.action=="fetch":
        print(json.dumps(fetch_prices(directory)))
    elif args.action == "prepare":
        value = prepare(directory)
        print(json.dumps({k:value[k] for k in ("run_id", "kind", "required", "start", "end", "forward_start", "excluded_dates")}, ensure_ascii=False))
    elif args.action == "run":
        from src.forward.replay import execute
        print(json.dumps(execute(directory)))
    else:
        from src.db.session import create_app_engine, session_factory
        from src.forward.replay import read_metadata
        with session_factory(create_app_engine(f"sqlite:///{directory/'replay_ledger.db'}"))() as db:
            print(json.dumps(read_metadata(db), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
