"""Archive the prelaunch live DB (copy + checksum, never mutates the source).

Usage:
    python scripts/archive_prelaunch_live_db.py [--profile live]

After archiving, remove data/forward_test.db manually, then run:
    APP_PROFILE=live python -m src.forward.init_forward_test
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.forward.runtime import get_database_path


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="live")
    args = ap.parse_args()
    src = get_database_path(args.profile)
    if not src.exists():
        print(f"no DB at {src}; nothing to archive")
        return 0
    arch_dir = ROOT / "data" / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = arch_dir / f"forward_test_prelaunch_{stamp}.db"
    shutil.copy2(str(src), str(dst))
    sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    meta = {"archived_at": datetime.now(timezone.utc).isoformat(),
            "source_db": str(src.relative_to(ROOT)),
            "archive_db": str(dst.relative_to(ROOT)),
            "reason": "prelaunch demo contamination cleanup",
            "sha256": sha}
    (dst.with_suffix(".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"archived -> {dst.relative_to(ROOT)}")
    print(f"sha256: {sha}")
    print("source DB left untouched; delete it manually before clean init")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
