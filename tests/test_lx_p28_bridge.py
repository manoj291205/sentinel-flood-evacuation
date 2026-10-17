"""Additional Lane X HIL invariants."""

import copy
import json
import py_compile
from pathlib import Path

from src.hil.bridge import Actuator, InMemoryBus, certificate_hash, validate_message
from hil.sim.publisher import publish_sample
from hil.firmware.common.cert_verify import certificate_hash as firmware_hash

ROOT = Path(__file__).resolve().parents[1]


def test_firmware_syntax_compiles(tmp_path):
    for path in (ROOT / "hil" / "firmware").rglob("*.py"):
        py_compile.compile(str(path), cfile=str(tmp_path / (path.stem + path.parent.name + ".pyc")), doraise=True)


def test_publisher_is_deterministic_and_valid():
    readings = []
    bus = InMemoryBus()
    bus.subscribe("sentinel/v1/#", lambda topic, payload: (validate_message(topic, payload), readings.append((topic, payload))))
    publish_sample(bus, seed=19, step=3, timestamp=lambda: "2026-10-15T08:00:00Z")
    first = copy.deepcopy(readings)
    readings.clear()
    publish_sample(bus, seed=19, step=3, timestamp=lambda: "2026-10-15T08:00:00Z")
    assert readings == first


def test_hold_certificate_is_not_actuatable():
    fixture = json.loads((ROOT / "specs/contracts/certificates_fixture.json").read_text(encoding="utf-8"))
    hold = next(item for item in fixture["certificates"] if item["kind"] == "HOLD")
    hold = copy.deepcopy(hold)
    hold["cert_id"] = "CERT-000412"
    hold["cert_hash"] = certificate_hash(hold)
    bus = InMemoryBus()
    actuator = Actuator("vehicle-01", bus)
    bus.publish(f"sentinel/v1/cert/{hold['cert_id']}", hold)
    ack = actuator.handle_command("sentinel/v1/command/vehicle/V-01", {
        "schema": "vehicle-cmd-v1", "cert_id": hold["cert_id"], "cert_hash": hold["cert_hash"],
        "group_id": None, "zone_id": "Z-01", "shelter_id": "S-01", "people": 1,
        "edge_ids": [], "ts_utc": "2026-10-15T08:00:00Z",
    })
    assert ack["reason"] == "KIND_NOT_ACTUATABLE"


def test_firmware_canonical_hash_matches_fixture():
    fixture = json.loads((ROOT / "specs/contracts/certificates_fixture.json").read_text(encoding="utf-8"))
    assert all(firmware_hash(cert) == cert["cert_hash"] for cert in fixture["certificates"])
