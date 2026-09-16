"""V0.2 diagnostic plots."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _save(fig, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_frontier_v02(frontier, minvar_pt, tangency_pt, neutral_pt, v02_pt, path) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(frontier["volatility"], frontier["expected_return"], lw=2, label="Efficient frontier (9 risky)")
    ax.scatter([minvar_pt["vol"]], [minvar_pt["ret"]], s=80, marker="o", label="Minimum variance")
    ax.scatter([tangency_pt["vol"]], [tangency_pt["ret"]], s=100, marker="^", label="Tangency (diagnostic)")
    ax.scatter([neutral_pt["vol"]], [neutral_pt["ret"]], s=100, marker="s", label="Neutral 60/40 (risk anchor)")
    ax.scatter([v02_pt["vol"]], [v02_pt["ret"]], s=160, marker="*", label="Core Benchmark V0.2")
    ax.set_xlabel("Annualized volatility")
    ax.set_ylabel("Expected return (strategic ER)")
    ax.set_title("Constrained Frontier + Core V0.2 (KRW, 5Y primary risk)")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    _save(fig, path)


def plot_weights_compare(portfolios: dict, path) -> None:
    from src.portfolio.reference import FULL_ORDER

    names = [k for k, v in portfolios.items() if v is not None]
    x = np.arange(len(FULL_ORDER))
    width = min(0.8 / max(len(names), 1), 0.2)
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, name in enumerate(names):
        w = portfolios[name]
        vals = np.array([float(w.loc[a]) if a in w.index else 0.0 for a in FULL_ORDER])
        ax.bar(x + (i - (len(names) - 1) / 2) * width, vals, width=width, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(FULL_ORDER, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Weight")
    ax.set_title("Weight comparison (cash=0 for 9-asset portfolios)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, path)


def plot_horizon_sensitivity(w5: pd.Series, w3: pd.Series, path) -> None:
    from src.portfolio.reference import FULL_ORDER

    x = np.arange(len(FULL_ORDER))
    v5 = np.array([float(w5.loc[a]) for a in FULL_ORDER])
    v3 = np.array([float(w3.loc[a]) for a in FULL_ORDER])
    l1 = float(np.abs(v5 - v3).sum())
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(x - 0.2, v5, width=0.4, label="5Y primary")
    ax.bar(x + 0.2, v3, width=0.4, label="3Y sensitivity")
    ax.set_xticks(x)
    ax.set_xticklabels(FULL_ORDER, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Weight")
    ax.set_title(f"3Y vs 5Y benchmark weights (L1 diff = {l1:.3f})")
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, path)


def plot_er_sensitivity(own_delta_05: dict, path) -> None:
    assets = list(own_delta_05.keys())
    deltas = np.array([own_delta_05[a] for a in assets]) * 100.0
    colors = ["tab:red" if d < 0 else "tab:blue" for d in deltas]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(assets, deltas, color=colors)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_ylabel("Own-weight change (pp)")
    ax.set_title("ER +0.5pp shock -> own-asset weight change (pp)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8)
    fig.tight_layout()
    _save(fig, path)
