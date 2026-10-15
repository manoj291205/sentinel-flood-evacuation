"""Phase 33 acceptance tests (Lead) — evidence and system endpoints. Do not edit; escalate instead.

Numbers on the console must come from frozen artifacts: every non-null value must equal the value at the
manifest's JSON pointer in the named file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.milestone("P33")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "contracts"


def _contract(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _pointer(document, pointer):
    for part in pointer.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from src.api.app import create_app

    return TestClient(create_app())


def test_evidence_matches_frozen_artifacts(client):
    response = client.get("/api/evidence")
    assert response.status_code == 200
    body = response.json()
    jsonschema.validate(body, _contract("evidence.schema.json"))
    manifest = {item["id"]: item for item in _contract("evidence_manifest.json")["items"]}
    assert [item["id"] for item in body["items"]] == list(manifest)
    for item in body["items"]:
        entry = manifest[item["id"]]
        path = ROOT / entry["path"]
        assert item["source_path"] == entry["path"]
        if item["value"] is None:
            assert item["display"] == "-" and item["note"]
            continue
        raw = path.read_bytes()
        assert item["source_sha256"] == hashlib.sha256(raw).hexdigest()
        assert item["value"] == _pointer(json.loads(raw.decode("utf-8")), entry["json_pointer"])


def test_known_artifacts_render_and_missing_ones_show_a_dash(client):
    items = {item["id"]: item for item in client.get("/api/evidence").json()["items"]}
    assert items["g21-passed"]["value"] is True
    assert items["g21-high-failure"]["display"] == "30.1 %"
    if not (ROOT / "data/eval_results/phase27/analysis.json").exists():
        assert items["p27-analysis"]["value"] is None and items["p27-analysis"]["display"] == "-"


def test_system_status_and_acks_validate(client):
    status = client.get("/api/system/status")
    assert status.status_code == 200
    jsonschema.validate(status.json(), _contract("system_status.schema.json"))
    acks = client.get("/api/system/acks")
    assert acks.status_code == 200
    ack_schema = _contract("hil_messages.schema.json")
    for ack in acks.json()["items"]:
        jsonschema.validate(ack, ack_schema)
        assert ack["schema"] == "ack-v1"


def test_openapi_lists_wave_b_paths(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/api/evidence", "/api/system/status", "/api/system/acks"):
        assert path in paths
