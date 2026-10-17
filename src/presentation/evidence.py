"""Read-only evidence manifest projection; never estimates missing results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.presentation.artifacts import load_contract_fixture

ROOT = Path(__file__).resolve().parents[2]


def _pointer(document: object, pointer: str) -> object:
    if not pointer:
        return document
    if not pointer.startswith("/"):
        raise ValueError("invalid JSON pointer")
    value = document
    for raw in pointer[1:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _display(value: object, fmt: str) -> str:
    if fmt == "fixed3":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("fixed3 requires a number")
        return f"{value:.3f}"
    if fmt == "percent1":
        return f"{float(value) * 100:.1f} %"
    if fmt == "percent2":
        return f"{float(value) * 100:.2f} %"
    if fmt == "signed4":
        return f"{float(value):+.4f}"
    if fmt == "integer":
        return str(int(value))
    if fmt == "number":
        return str(value)
    if fmt == "ms0":
        return f"{float(value):.0f} ms"
    if fmt == "bool":
        return "yes" if value else "no"
    if fmt == "text":
        return str(value)
    if fmt == "bars":
        if isinstance(value, dict):
            return ", ".join(f"{name}: {row.get('verdict', row.get('status', '—')) if isinstance(row, dict) else row}" for name, row in value.items()) or "—"
        if isinstance(value, list):
            return ", ".join(str(row.get("name", row.get("id", "—"))) if isinstance(row, dict) else str(row) for row in value) or "—"
    raise ValueError(f"unsupported evidence format: {fmt}")


def evidence_items() -> list[dict]:
    items = []
    for entry in load_contract_fixture("evidence_manifest.json")["items"]:
        relative = Path(entry["path"])
        artifact = (ROOT / relative).resolve()
        if not artifact.is_relative_to(ROOT) or relative.parts[:2] not in {("data", "eval_results"), ("data", "eval_v3")}:
            raise ValueError("evidence path outside frozen result allowlist")
        value, display, note, digest = None, "-", "not produced yet", None
        if artifact.is_file():
            raw = artifact.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            try:
                value = _pointer(json.loads(raw.decode("utf-8")), entry["json_pointer"])
                display = _display(value, entry["format"])
                note = None
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
                value, display, note = None, "-", "field not in artifact"
        items.append({"id": entry["id"], "group": entry["group"], "label": entry["label"],
                      "value": value, "display": display, "unit": entry["unit"],
                      "source_path": entry["path"], "source_sha256": digest, "note": note})
    return items
