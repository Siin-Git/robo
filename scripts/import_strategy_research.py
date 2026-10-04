"""Explicit, file-only research import. Never writes a price store or an account."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.strategies.sources import extract

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = extract(args.downloads)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Each reviewed source version has its own artifact; no implicit overwrite.
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    print(json.dumps({"output": str(args.output), "version": data["version"],
                      "series": {k: v["quality"] for k, v in data["series"].items()}}, ensure_ascii=False))
