"""Dump the OpenAPI contract for frontend development (Phase 3D input)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.main import app  # noqa: E402


def main() -> int:
    out = ROOT / "outputs" / "api" / "openapi_v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    paths = sorted(app.openapi()["paths"])
    print(f"wrote {out.relative_to(ROOT)} ({len(paths)} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
