"""Diagnostic plots (analysis/validation only, no web UI)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_frontier(frontier: pd.DataFrame, er: pd.DataFrame, bench: dict,
                  comparators: dict, path) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(frontier["volatility"], frontier["expected_return"], lw=2, label="Efficient frontier")
    ax.scatter([bench["vol"]], [bench["ret"]], s=120, marker="*",
               label="Tangency (Core Benchmark V0)")
    for a in er.index:
        ax.scatter([er.loc[a, "annual_vol"]], [er.loc[a, "arith_er"]], s=40)
        ax.annotate(a, (er.loc[a, "annual_vol"], er.loc[a, "arith_er"]), fontsize=8)
    for name, pt in comparators.items():
        ax.scatter([pt["vol"]], [pt["ret"]], s=80, marker="D", label=name)
    ax.set_xlabel("Annualized volatility")
    ax.set_ylabel("Expected arithmetic return")
    ax.set_title("Constrained Efficient Frontier (KRW)")
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_correlation(corr: pd.DataFrame, title: str, path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr.to_numpy(float), vmin=-1, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels(list(corr.columns), rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(list(corr.index), fontsize=8)
    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=7)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_weights(weights: pd.Series, title: str, path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    vals = weights.to_numpy(float)
    ax.bar(list(weights.index), vals)
    ax.set_ylim(0, max(0.4, float(vals.max()) * 1.25))
    ax.set_ylabel("Weight")
    ax.set_title(title)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.005, f"{v:.2%}", ha="center", fontsize=8)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_nav(nav: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in nav.columns:
        ax.plot(nav.index, nav[col], label=col)
    ax.set_title("Historical NAV, static weights (diagnostic) — NOT A WALK-FORWARD BACKTEST")
    ax.set_ylabel("Growth of 1 KRW")
    ax.legend(fontsize=9)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)
