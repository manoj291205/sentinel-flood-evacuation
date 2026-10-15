"""Phase 28 acceptance tests (Lead) — HIL bridge, message contract, certificate-gated actuators.

Do not edit; escalate instead. No network, no MQTT broker.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P28")

CONTRACTS = Path(__file__).resolve().parents[1] / "specs" / "contracts"


def _contract(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _cert(cert_id="CERT-000127"):
    return next(c for c in _contract("certificates_fixture.json")["certificates"] if c["cert_id"] == cert_id)


def test_certificate_hash_matches_gate_rule():
    from src.hil.bridge import certificate_hash

    for cert in _contract("certificates_fixture.json")["certificates"]:
        assert certificate_hash(cert) == cert["cert_hash"]


def test_contract_examples_validate_and_bad_messages_fail():
    from src.hil.bridge import validate_message

    for topic in _contract("mqtt_topics.json")["topics"]:
        if topic["example"] is not None:
            validate_message(topic["example_topic"], topic["example"])
    example = _contract("mqtt_topics.json")["topics"][0]
    with pytest.raises(ValueError):
        validate_message(example["example_topic"], {**example["example"], "count": -1})
    with pytest.raises(ValueError):
        validate_message("sentinel/v1/unknown/topic", example["example"])


def test_in_memory_bus_wildcards():
    from src.hil.bridge import InMemoryBus

    bus, seen = InMemoryBus(), []
    bus.subscribe("sentinel/v1/shelter/+/occupancy", lambda t, p: seen.append(("plus", t)))
    bus.subscribe("sentinel/v1/#", lambda t, p: seen.append(("hash", t)))
    bus.publish("sentinel/v1/shelter/S-04/occupancy", {"x": 1})
    bus.publish("sentinel/v1/zone/Z-01/water_level", {"x": 2})
    assert ("plus", "sentinel/v1/shelter/S-04/occupancy") in seen
    assert [t for k, t in seen if k == "hash"] == ["sentinel/v1/shelter/S-04/occupancy",
                                                   "sentinel/v1/zone/Z-01/water_level"]
    assert not any(k == "plus" and "zone" in t for k, t in seen)


def test_occupancy_tracker_feeds_ledger_and_dropout_widens_margin():
    from src.certify.ledger_view import LedgerView
    from src.certify.params import CertParams
    from src.hil.bridge import InMemoryBus, OccupancyTracker, apply_to_ledger_view

    now = [1000.0]
    bus = InMemoryBus()
    tracker = OccupancyTracker(bus, clock=lambda: now[0])
    message = copy.deepcopy(_contract("mqtt_topics.json")["topics"][0]["example"])
    bus.publish("sentinel/v1/shelter/S-04/occupancy", message)
    view = LedgerView(timestep=3, capacity_total={"S-04": 200, "S-05": 200}, occupancy={"S-04": 0, "S-05": 0},
                      reserved={"S-04": 0, "S-05": 0}, pending=(), occupancy_sigma={"S-04": 0.0, "S-05": 0.0},
                      occupancy_age_s={"S-04": 0.0, "S-05": 0.0})
    fresh = apply_to_ledger_view(view, tracker)
    assert fresh.occupancy_sigma["S-04"] == message["sigma"] and fresh.occupancy_age_s["S-04"] == 0.0
    assert fresh.occupancy_sigma["S-05"] == 5.0 and fresh.occupancy_age_s["S-05"] == 3600.0
    now[0] += 60.0
    stale = apply_to_ledger_view(view, tracker)
    assert stale.occupancy_age_s["S-04"] == 60.0
    p = CertParams()
    margin = lambda v: p.k_sigma * v.occupancy_sigma["S-04"] * (1 + v.occupancy_age_s["S-04"] / p.age_scale_s)  # noqa: E731
    assert margin(stale) > margin(fresh)


def _command(**over):
    cert = _cert()
    zone, shelter = cert["chosen"]["action_key"].split("->")
    payload = {"schema": "vehicle-cmd-v1", "cert_id": cert["cert_id"], "cert_hash": cert["cert_hash"],
               "group_id": cert["chosen"]["group_id"], "zone_id": zone, "shelter_id": shelter,
               "people": cert["chosen"]["people"], "edge_ids": [], "ts_utc": "2026-10-15T08:00:00Z"}
    payload.update(over)
    return payload


def _actuator(*certs):
    from src.hil.bridge import Actuator, InMemoryBus

    bus = InMemoryBus()
    actuator = Actuator("esp32-vehicle-01", bus)
    acks = []
    bus.subscribe("sentinel/v1/ack/+", lambda t, p: acks.append(p))
    for cert in certs:
        bus.publish(f"sentinel/v1/cert/{cert['cert_id']}", cert)
    return actuator, acks


def test_actuator_accepts_only_verified_certificates():
    topic = "sentinel/v1/command/vehicle/V-01"
    actuator, acks = _actuator(_cert())
    assert actuator.handle_command(topic, _command())["accepted"] is True
    assert actuator.handle_command(topic, _command(cert_id="CERT-999999"))["reason"] == "UNKNOWN_CERT"
    assert actuator.handle_command(topic, _command(shelter_id="S-01"))["reason"] == "ACTION_MISMATCH"
    assert actuator.handle_command(topic, _command(cert_hash="0" * 64))["reason"] == "HASH_MISMATCH"
    assert [a["accepted"] for a in acks] == [True, False, False, False]

    tampered = copy.deepcopy(_cert())
    tampered["chosen"]["people"] = 41
    actuator, _ = _actuator(tampered)
    assert actuator.handle_command(topic, _command(people=41))["reason"] == "HASH_MISMATCH"

    hold = _cert("AUD-000412")
    actuator, _ = _actuator(hold)
    ack = actuator.handle_command(topic, _command(cert_id="CERT-000127"))
    assert ack["reason"] == "UNKNOWN_CERT"
