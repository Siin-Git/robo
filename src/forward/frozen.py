"""Frozen benchmark artifact: written once at forward-test start, read-only after.

The forward engine NEVER recomputes or overwrites these weights; methodology
upgrades create a new frozen version tracked as a shadow.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from .config import ROOT


def freeze_benchmark(frozen_dir, phase16_weights_csv, run_metadata_json,
                     bl_methodology_json, optimizer_config, force: bool = False) -> Path:
    """Create outputs/frozen/CORE_V0.3/ from Phase 1.6 outputs (once)."""
    frozen_dir = Path(frozen_dir)
    if frozen_dir.exists() and not force and (frozen_dir / "weights.json").exists():
        raise RuntimeError(f"Frozen benchmark already exists at {frozen_dir} (refusing to overwrite)")
    frozen_dir.mkdir(parents=True, exist_ok=True)
    w = pd.read_csv(phase16_weights_csv, index_col=0)["weight"]
    weights = {k: float(v) for k, v in w.items()}
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("frozen weights do not sum to 1")
    meta = json.loads(Path(run_metadata_json).read_text(encoding="utf-8"))
    blm = json.loads(Path(bl_methodology_json).read_text(encoding="utf-8"))
    (frozen_dir / "weights.json").write_text(
        json.dumps(weights, indent=2), encoding="utf-8")
    (frozen_dir / "metadata.json").write_text(json.dumps({
        "benchmark_version": "CORE_V0.3",
        "frozen_from": str(phase16_weights_csv),
        "run_timestamp": meta.get("run_timestamp"),
        "data_start": meta.get("data_start"),
        "data_end": meta.get("data_end"),
        "tickers": meta.get("tickers"),
        "target_volatility": meta.get("target_volatility"),
        "expected_return_model": "black_litterman_v0",
        "bl": blm,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.copy2(str(optimizer_config), str(frozen_dir / "optimizer_config_snapshot.yaml"))
    return frozen_dir


def load_frozen_benchmark(frozen_dir) -> tuple[dict, dict]:
    frozen_dir = Path(frozen_dir)
    weights = json.loads((frozen_dir / "weights.json").read_text(encoding="utf-8"))
    meta = json.loads((frozen_dir / "metadata.json").read_text(encoding="utf-8"))
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError("frozen weights do not sum to 1")
    return weights, meta
