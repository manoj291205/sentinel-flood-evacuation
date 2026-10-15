"""Validated sensor and certificate-gated actuator bridge."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol

from jsonschema import Draft202012Validator

_CONTRACTS = Path(__file__).resolve().parents[2] / "specs" / "contracts"
_TOPICS = json.loads((_CONTRACTS / "mqtt_topics.json").read_text(encoding="utf-8"))["topics"]
_MESSAGE_SCHEMA = json.loads((_CONTRACTS / "hil_messages.schema.json").read_text(encoding="utf-8"))
_CERT_SCHEMA = json.loads((_CONTRACTS / "certificate.schema.json").read_text(encoding="utf-8"))


def canonical_json(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def certificate_hash(cert: Mapping) -> str:
    return hashlib.sha256(canonical_json({key: value for key, value in cert.items() if key != "cert_hash"})).hexdigest()


def _topic_matches(pattern: str, topic: str) -> bool:
    parts, actual = pattern.split("/"), topic.split("/")
    for index, part in enumerate(parts):
        if part == "#":
            return index == len(parts) - 1
        if index >= len(actual) or (part != "+" and part != actual[index]):
            return False
    return len(parts) == len(actual)


def validate_message(topic: str, payload: dict) -> None:
    entry = next((item for item in _TOPICS if _topic_matches(item["pattern"], topic)), None)
    if entry is None:
        raise ValueError(f"Unknown topic: {topic}")
    schema = _CERT_SCHEMA if entry["schema"] == "certificate" else _MESSAGE_SCHEMA
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors or (entry["schema"] != "certificate" and payload.get("schema") != entry["schema"]):
        raise ValueError(f"Invalid {entry['schema']} message on {topic}: {errors[:1]}")
    topic_id = topic.split("/")[-2] if topic.endswith("/occupancy") or topic.endswith("/water_level") or topic.endswith("/admission") else topic.split("/")[-1]
    field = {"occupancy-v1": "shelter_id", "water-level-v1": "zone_id", "certificate": "cert_id", "ack-v1": "device_id", "status-v1": "device_id"}.get(entry["schema"])
    if field and payload.get(field) != topic_id:
        raise ValueError(f"Topic id differs from {field}")
    if entry["schema"] == "admission-cmd-v1" and payload["shelter_id"] != topic_id:
        raise ValueError("Topic shelter differs from command")


class Bus(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...
    def subscribe(self, pattern: str, handler: Callable[[str, dict], None]) -> None: ...


class InMemoryBus:
    def __init__(self) -> None:
        self._subscriptions: list[tuple[str, Callable[[str, dict], None]]] = []

    def publish(self, topic: str, payload: dict) -> None:
        for pattern, handler in tuple(self._subscriptions):
            if _topic_matches(pattern, topic):
                handler(topic, payload)

    def subscribe(self, pattern: str, handler: Callable[[str, dict], None]) -> None:
        self._subscriptions.append((pattern, handler))


class MqttBus:
    def __init__(self, host: str = "localhost", port: int = 1883, *, username: str | None = None,
                 password: str | None = None, client_id: str = "sentinel-bridge") -> None:
        import paho.mqtt.client as mqtt

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username is not None:
            self._client.username_pw_set(username, password)
        self._handlers: list[tuple[str, Callable[[str, dict], None]]] = []

        def on_message(_client, _userdata, message):
            try:
                payload = json.loads(message.payload.decode("utf-8"))
                validate_message(message.topic, payload)
            except (UnicodeError, json.JSONDecodeError, ValueError):
                return
            for pattern, handler in tuple(self._handlers):
                if _topic_matches(pattern, message.topic):
                    handler(message.topic, payload)

        self._client.on_message = on_message
        self._client.connect(host, port)
        self._client.loop_start()

    def publish(self, topic: str, payload: dict) -> None:
        validate_message(topic, payload)
        self._client.publish(topic, canonical_json(payload), qos=1, retain=False)

    def subscribe(self, pattern: str, handler: Callable[[str, dict], None]) -> None:
        self._handlers.append((pattern, handler))
        self._client.subscribe(pattern, qos=1)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()


class OccupancyTracker:
    def __init__(self, bus: Bus, *, default_sigma: float = 5.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.default_sigma, self.clock = default_sigma, clock
        self._seen: dict[str, tuple[float, float, int]] = {}
        bus.subscribe("sentinel/v1/shelter/+/occupancy", self._on_occupancy)

    def _on_occupancy(self, topic: str, payload: dict) -> None:
        validate_message(topic, payload)
        shelter_id = payload["shelter_id"]
        last = self._seen.get(shelter_id)
        if last is None or payload["seq"] > last[2]:
            self._seen[shelter_id] = (float(payload["sigma"]), self.clock(), payload["seq"])

    def ledger_fields(self, shelter_ids) -> tuple[dict[str, float], dict[str, float]]:
        now = self.clock()
        sigmas, ages = {}, {}
        for shelter_id in shelter_ids:
            if shelter_id in self._seen:
                sigmas[shelter_id], seen_at, _ = self._seen[shelter_id]
                ages[shelter_id] = max(0.0, now - seen_at)
            else:
                sigmas[shelter_id], ages[shelter_id] = self.default_sigma, 3600.0
        return sigmas, ages


def apply_to_ledger_view(view, tracker: OccupancyTracker):
    sigma, age = tracker.ledger_fields(view.capacity_total)
    return replace(view, occupancy_sigma=sigma, occupancy_age_s=age)


class Actuator:
    def __init__(self, device_id: str, bus: Bus) -> None:
        self.device_id, self.bus = device_id, bus
        self._certificates: dict[str, dict] = {}
        bus.subscribe("sentinel/v1/cert/+", self._on_certificate)

    def _on_certificate(self, topic: str, payload: dict) -> None:
        if payload.get("cert_id") == topic.split("/")[-1]:
            self._certificates[payload["cert_id"]] = payload
            if len(self._certificates) > 64:
                self._certificates.pop(next(iter(self._certificates)))

    def handle_command(self, topic: str, payload: dict) -> dict:
        cert_id = payload.get("cert_id", "")
        cert = self._certificates.get(cert_id)
        try:
            validate_message(topic, payload)
        except ValueError:
            reason = "MALFORMED"
        else:
            if cert is None:
                reason = "UNKNOWN_CERT"
            elif certificate_hash(cert) != cert.get("cert_hash") or cert.get("cert_hash") != payload.get("cert_hash"):
                reason = "HASH_MISMATCH"
            elif cert.get("kind") not in {"DISPATCH", "MIGRATION", "OVERRIDE"}:
                reason = "KIND_NOT_ACTUATABLE"
            else:
                chosen = cert.get("chosen", {})
                action = chosen.get("action_key", "")
                expected = f"{payload.get('zone_id')}->{payload.get('shelter_id')}" if payload.get("schema") == "vehicle-cmd-v1" else action
                shelter = action.split("->")[-1]
                if (action != expected or shelter != payload.get("shelter_id") or
                        chosen.get("people") != payload.get("people") or
                        chosen.get("group_id") != payload.get("group_id")):
                    reason = "ACTION_MISMATCH"
                else:
                    reason = "OK"
        ack = {"schema": "ack-v1", "device_id": self.device_id, "cert_id": cert_id,
               "accepted": reason == "OK", "reason": reason,
               "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.bus.publish(f"sentinel/v1/ack/{self.device_id}", ack)
        return ack


def measure_latency(bus: Bus, n: int = 100) -> dict:
    """Measure only actual bus publish-to-ack round trips; caller supplies a responding actuator."""
    if n <= 0:
        raise ValueError("n must be positive")
    import statistics

    observations: list[float] = []
    pending: list[float] = []

    def on_ack(_topic: str, _payload: dict) -> None:
        if pending:
            observations.append((time.perf_counter() - pending.pop(0)) * 1000)

    bus.subscribe("sentinel/v1/ack/+", on_ack)
    for index in range(n):
        pending.append(time.perf_counter())
        bus.publish("sentinel/v1/status/latency-probe", {"schema": "status-v1", "device_id": "latency-probe",
                    "kind": "simulated", "uptime_s": index, "rssi_dbm": None,
                    "firmware": "latency-probe", "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if len(observations) != n:
        raise RuntimeError("No one-to-one ack response; cannot report latency")
    ordered = sorted(observations)
    return {"n": n, "p50_ms": statistics.median(ordered), "p95_ms": ordered[max(0, int(n * 0.95 + 0.999999) - 1)]}
