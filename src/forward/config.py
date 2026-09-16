"""Forward test configuration loader."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_forward_config(path=None) -> dict:
    p = Path(path) if path else ROOT / "config" / "forward_v0.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(p, root=ROOT) -> Path:
    q = Path(p)
    return q if q.is_absolute() else root / q
