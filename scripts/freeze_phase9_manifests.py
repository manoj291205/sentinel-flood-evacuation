"""Materialize the pre-training Phase 9 validation and permutation manifests."""

from __future__ import annotations

import json
from pathlib import Path

from src.training_v3 import permutation_manifest, validation_manifest


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "eval_v3" / "training"


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "validation_manifest.json": validation_manifest(),
        "permutation_manifest.json": permutation_manifest(),
    }
    for name, payload in artifacts.items():
        path = OUTPUT / name
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
