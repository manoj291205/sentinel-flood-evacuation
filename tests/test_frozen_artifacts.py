"""Frozen artifacts must stay bit-identical (SHA-256 manifest from Phase 20).

Only files listed in the manifest are checked, so new result folders added by later
phases do not fail this test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((Path(__file__).with_name("frozen_manifest.json")).read_text(encoding="utf-8"))["files"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_manifest_is_not_empty():
    assert len(MANIFEST) > 0


@pytest.mark.parametrize("rel", sorted(MANIFEST))
def test_frozen_file_unchanged(rel: str):
    path = ROOT / rel
    assert path.is_file(), f"frozen file missing: {rel}"
    assert _sha256(path) == MANIFEST[rel], f"frozen file modified: {rel}"
