"""Strategic Expected Return V0 loader (no forecasting model)."""
from __future__ import annotations

import pandas as pd

from .conversions import geometric_to_arithmetic


def load_strategic_returns(er_cfg: dict) -> pd.DataFrame:
    rows = []
    geo = er_cfg.get("expected_returns_geometric", {})
    if not geo:
        raise ValueError("expected_returns_geometric is empty")
    for aid, node in geo.items():
        if "expected_return" not in node:
            raise ValueError(f"Missing expected_return for {aid}")
        rows.append(
            {
                "asset_id": aid,
                "geo_er": float(node["expected_return"]),
                "return_type": node.get("return_type", "geometric"),
                "model_version": node.get("model_version", ""),
                "effective_date": str(node.get("effective_date", "")),
            }
        )
    df = pd.DataFrame(rows).set_index("asset_id")
    return df


def build_optimizer_mu(er_cfg: dict, order) -> pd.Series:
    """V0.2 optimizer expected return: strategic values used DIRECTLY.

    Deliberately takes no volatility input: the V0.1 geo->arith realized-vol
    conversion must not enter the benchmark path (see conversions module,
    retained for diagnostics only).
    """
    geo_df = load_strategic_returns(er_cfg)
    missing = [a for a in order if a not in geo_df.index]
    if missing:
        raise ValueError(f"Expected Return missing for assets: {missing}")
    return pd.Series({a: float(geo_df.loc[a, "geo_er"]) for a in order}).loc[list(order)]


def build_expected_return_table(er_cfg: dict, vols: pd.Series) -> pd.DataFrame:
    geo_df = load_strategic_returns(er_cfg)
    missing = [a for a in vols.index if a not in geo_df.index]
    if missing:
        raise ValueError(f"Expected Return missing for assets: {missing}")
    rows = []
    for aid in vols.index:
        mu_geo = float(geo_df.loc[aid, "geo_er"])
        vol = float(vols.loc[aid])
        rows.append(
            {
                "asset_id": aid,
                "geo_er": mu_geo,
                "annual_vol": vol,
                "arith_er": geometric_to_arithmetic(mu_geo, vol),
            }
        )
    return pd.DataFrame(rows).set_index("asset_id")
