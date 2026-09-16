"""V0.3 (Black-Litterman) diagnostic plots."""
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


def plot_bl_er_compare(cma: pd.Series, prior: pd.Series, posterior: pd.Series, path) -> None:
    assets = list(cma.index)
    x = np.arange(len(assets))
    w = 0.25
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - w, [cma.loc[a] * 100 for a in assets], width=w, label="Strategic CMA")
    ax.bar(x, [prior.loc[a] * 100 for a in assets], width=w, label="Implied prior")
    ax.bar(x + w, [posterior.loc[a] * 100 for a in assets], width=w, label="BL posterior (c=25%)")
    ax.set_xticks(x)
    ax.set_xticklabels(assets, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Expected return (%)")
    ax.set_title("Expected returns: CMA vs equilibrium prior vs BL posterior")
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, path)


def plot_weights_v03(w_neutral: pd.Series, w_v02: pd.Series, w_v03: pd.Series, path) -> None:
    from src.portfolio.reference import FULL_ORDER

    x = np.arange(len(FULL_ORDER))
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (name, w) in enumerate([("Neutral 60/40", w_neutral), ("CORE V0.2", w_v02),
                                   ("CORE V0.3", w_v03)]):
        vals = np.array([float(w.loc[a]) for a in FULL_ORDER])
        ax.bar(x + (i - 1) * 0.25, vals, width=0.25, label=name)
    ax.set_xticks(x)
    ax.set_xticklabels(FULL_ORDER, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Weight")
    ax.set_title("Neutral vs V0.2 vs V0.3 weights")
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, path)


def plot_confidence_path(conf_df: pd.DataFrame, path) -> None:
    from src.portfolio.reference import FULL_ORDER

    fig, ax = plt.subplots(figsize=(10, 6))
    for a in FULL_ORDER:
        ax.plot(conf_df["confidence"] * 100, conf_df[f"w_{a}"] * 100, marker="o", label=a)
    ax.set_xlabel("BL confidence (%)")
    ax.set_ylabel("Weight (%)")
    ax.set_title("Weight paths across BL confidence grid")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    _save(fig, path)


def plot_sensitivity_compare(d02: dict, d03: dict, path) -> None:
    assets = list(d02.keys())
    x = np.arange(len(assets))
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - 0.2, [d02[a] * 100 for a in assets], width=0.4, label="V0.2")
    ax.bar(x + 0.2, [d03[a] * 100 for a in assets], width=0.4, label="V0.3")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(assets, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Own-weight change (pp)")
    ax.set_title("ER +0.5pp shock -> own-weight change: V0.2 vs V0.3")
    ax.legend(fontsize=9)
    fig.tight_layout()
    _save(fig, path)
