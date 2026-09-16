import json, sys
sys.path.insert(0, '.')
from pathlib import Path
import numpy as np
import pandas as pd, yaml
from src.portfolio.constraints import ASSET_ORDER, get_bounds
from src.portfolio.constraints import project_box_simplex, random_feasible
from src.portfolio.optimizer import portfolio_stats
ROOT = Path('.')
cfg = yaml.safe_load(open(ROOT/'config/optimizer_v0.yaml'))
er_cfg = yaml.safe_load(open(ROOT/'config/expected_returns_v0.yaml'))
# Load cov and mu via same helpers
from src.api.services.frontier_service import _load_bl_bundle
mu_bl9, cov5, cfg2 = _load_bl_bundle()
order = list(ASSET_ORDER)
m = mu_bl9.loc[order].to_numpy(float)
C = cov5.loc[order, order].to_numpy(float)
lb, ub = get_bounds(order, cfg["weight_bounds"])
groups = cfg["group_constraints"]
rng = np.random.default_rng(42)
candidates = []
# random only, no optimizer anchors
for _ in range(20000):
    w = random_feasible(rng, lb, ub)
    # group check
    ok=True
    idx={a:i for i,a in enumerate(order)}
    for g in groups:
        if sum(float(w[idx[a]]) for a in g["assets"]) > float(g["max"])+1e-9:
            ok=False; break
    if not ok: continue
    # quick weight sum check
    if abs(w.sum()-1)>1e-9: continue
    candidates.append(w)
print(f"candidates {len(candidates)}")
pts=[]
for w in candidates:
    ret, vol, sh = portfolio_stats(w, m, C, 0.03)
    pts.append((vol, ret, sh, w))
pts.sort(key=lambda x: (x[0], -x[1]))
efficient=[]
max_ret=-1e9
for vol, ret, sh, w in pts:
    if ret > max_ret+1e-9:
        efficient.append((vol, ret, sh, w))
        max_ret=ret
print(f"efficient {len(efficient)}")
# sample 50
idxs = np.linspace(0, len(efficient)-1, 50).astype(int)
idxs = sorted(set(int(i) for i in idxs))
sampled=[efficient[i] for i in idxs]
sampled.sort(key=lambda x: x[1])
points=[]
for i,(vol,ret,sh,w) in enumerate(sampled):
    fid=f"F{i+1:03d}"
    weights=[{"asset_id":a,"weight":float(w[j])} for j,a in enumerate(order)]
    points.append({"frontier_id":fid,"index":int(i),"expected_return":float(ret),"volatility":float(vol),"sharpe":float(sh),"weights":weights})
# find bench closest
import json as _j
frozen = _j.loads(Path("outputs/frozen/CORE_V0.3/weights.json").read_text())
frozen_9={k:float(v) for k,v in frozen.items() if k!="cash"}
def l1(p):
    return sum(abs(next((w["weight"] for w in p["weights"] if w["asset_id"]==k),0)-v) for k,v in frozen_9.items())
bench=min(points, key=l1)
min_var=min(points, key=lambda p:p["volatility"])
tang=max(points, key=lambda p:p["sharpe"])
result={
    "frontier_version":"CORE_FRONTIER_V0.3",
    "model_version":cfg.get("model_version","CORE_V0.3"),
    "risk_model_version":"RISK_5Y_LW_FROZEN_V0",
    "expected_return_model":cfg.get("expected_return_model","black_litterman_v0"),
    "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    "min_volatility": float(min(p["volatility"] for p in points)),
    "max_volatility": float(max(p["volatility"] for p in points)),
    "benchmark_frontier_id": bench["frontier_id"],
    "min_variance_frontier_id": min_var["frontier_id"],
    "tangency_frontier_id": tang["frontier_id"],
    "points": points,
    "assets": [],
}
# assets
from src.risk.covariance import vols_from_cov
vols=vols_from_cov(cov5)
asset_info={"us_equity":"미국주식","developed_ex_us":"선진국 ex-US","emerging_markets":"신흥국","korea_equity":"한국주식","us_treasury":"미국국채","korea_treasury":"한국국채","tips":"TIPS","gold":"금","global_reit":"글로벌 REIT"}
assets=[]
for aid in order:
    assets.append({"asset_id":aid,"display_name":asset_info.get(aid,aid),"expected_return":float(mu_bl9.loc[aid]),"volatility":float(vols.loc[aid])})
result["assets"]=assets
Path("outputs/api").mkdir(parents=True, exist_ok=True)
Path("outputs/api/frontier.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("saved", len(points), bench["frontier_id"])
