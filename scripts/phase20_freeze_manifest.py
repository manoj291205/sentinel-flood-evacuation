"""Write tests/frozen_manifest.json: SHA-256 of every file in the frozen folders.

Run from the repo root. Existing entries are never silently rewritten: if a listed
file's hash differs from the manifest, the script aborts unless --force is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIRS = ("data/eval_v3", "data/eval_results", "models", "data/geospatial_v3")
MANIFEST = ROOT / "tests" / "frozen_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> dict[str, str]:
    out: dict[str, str] = {}
    for d in FROZEN_DIRS:
        for p in sorted((ROOT / d).rglob("*")):
            if p.is_file():
                out[p.relative_to(ROOT).as_posix()] = sha256(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite changed hashes")
    args = ap.parse_args()
    new = collect()
    if MANIFEST.exists() and not args.force:
        old = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
        changed = [k for k in old if k in new and old[k] != new[k]]
        if changed:
            print("Frozen files changed:", *changed[:10], sep="\n  ")
            return 1
    MANIFEST.write_text(
        json.dumps({"files": new}, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{len(new)} files hashed -> {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
