# V4_HIL_SPEC — Phase 28: hardware-in-the-loop rig (India s.3(k) anchor)

Lane X · branch `lane-x/m28-hil` · tests `tests/test_p28_hil.py` · contracts
`specs/contracts/mqtt_topics.json`, `specs/contracts/hil_messages.schema.json`. The human buys and
assembles the parts; the Lane X agent builds firmware and the bridge against a **simulated publisher**
until the hardware arrives. Confidential: no photos or videos outside the team before P0 is filed.

## Goal
Real sensors feed the ledger (occupancy with its counting error and age) and the hazard observation
(water level); real actuators (vehicle terminal, shelter admission relay/SMS) **reject any command whose
certificate does not verify**. Measure end-to-end latency sensor → certificate → actuator.

## Parts list (give this to the user first; prices approximate, Oct 2026, verify at purchase)
| # | Part | Qty | Approx. ₹ each | Indian suppliers |
|---|---|---|---|---|
| 1 | Raspberry Pi 5 (4 GB) + 27 W USB-C PSU + 32 GB A2 microSD + case with fan | 1 | 7,500–9,000 (kit) | robu.in, robocraze.com, thingbits.in |
| 2 | ESP32-DevKitC (ESP32-WROOM-32) | 3 | 450–650 | robu.in, robocraze.com, electronicscomp.com |
| 3 | JSN-SR04T waterproof ultrasonic sensor (water level) | 1 | 450–700 | robu.in, electronicscomp.com |
| 4 | IR break-beam pair 5 mm (people counter, in/out) or 2× E18-D80NK | 2 sets | 150–400 | robu.in, robocraze.com |
| 5 | 2-channel 5 V relay module (opto-isolated) — shelter admission indicator | 1 | 120–200 | robu.in, electronicscomp.com |
| 6 | SIM800L/SIM800C GSM module + antenna (SMS to vehicle terminal; optional) | 1 | 450–800 | robu.in, robocraze.com |
| 7 | 0.96" SSD1306 OLED (vehicle terminal display) | 1 | 180–300 | robu.in, electronicscomp.com |
| 8 | Breadboards, jumper wires, 1 kΩ/2 kΩ resistors (level shifting), 5 V 2 A adapters ×3 | set | 600–900 | any of the above |
| 9 | USB power meter (UM25C or similar) for energy per decision | 1 | 900–1,400 | robu.in, amazon.in |
| 10 | Bucket / clear container + ruler for the water-level bench test | 1 | 200 | local |
Total ≈ ₹13,000–17,000. Nothing here needs a licence; GSM is optional (use the OLED terminal if no SIM).

## Wiring (summary; full pin tables in `hil/README.md`)
- **Water-level node (ESP32 #1):** JSN-SR04T TRIG → GPIO5, ECHO → GPIO18 through a 1 kΩ/2 kΩ divider (5 V →
  3.3 V), VCC 5 V, GND common. Mounted 50 cm above the container floor; level = mount height − distance.
- **Shelter node (ESP32 #2):** beam A → GPIO32, beam B → GPIO33 (order A→B = entry, B→A = exit); relay IN1 →
  GPIO26 (green "ADMIT" lamp), IN2 → GPIO27 (red "FULL/REJECT" lamp).
- **Vehicle terminal (ESP32 #3):** SSD1306 on I²C SDA GPIO21 / SCL GPIO22; optional SIM800L on UART2
  (GPIO16/17) with its own 2 A supply.
- **Raspberry Pi 5:** Mosquitto broker (`mosquitto` package, local network only, username/password from a
  local file that is git-ignored), runs `src/hil/bridge.py` and the certified session.

## Firmware outline (`hil/firmware/`, MicroPython ≥ 1.23)
`common/mqtt_client.py` (umqtt.simple, reconnect with back-off, monotonic `seq`), `water_level/main.py`
(median of 5 pings every 2 s → `water_level` message), `shelter/main.py` (debounced beam state machine,
count persisted in NVS, `occupancy` every 5 s and on change, `sigma = 0.5 + 0.02·count` documented as a
counting-error model, admission handler), `vehicle/main.py` (shows route + shelter on OLED, optional SMS),
`common/cert_verify.py` (canonical-JSON SHA-256 per `V4_GATE_SPEC.md` "Canonical JSON"; keeps the last 64
certificates received on `cert` topic). Every actuator handler: verify → act → publish `ack`.

## MQTT contract
Topics (`specs/contracts/mqtt_topics.json`) — all under `sentinel/v1/`, QoS 1, JSON bodies validated by
`hil_messages.schema.json` (`schema` field selects the message type):
`shelter/{shelter_id}/occupancy`, `zone/{zone_id}/water_level`, `cert/{cert_id}` (full certificate, retained
false), `command/vehicle/{vehicle_id}`, `command/shelter/{shelter_id}/admission`, `ack/{device_id}`,
`status/{device_id}` (heartbeat every 10 s).

## Python (Lane X): `src/hil/`
```python
class Bus(Protocol):
    def publish(self, topic: str, payload: dict) -> None
    def subscribe(self, pattern: str, handler: Callable[[str, dict], None]) -> None
class InMemoryBus(Bus): ...          # tests; MQTT '+' and '#' wildcard matching
class MqttBus(Bus): ...              # paho-mqtt 2.x, imported lazily (requirements-hil.txt)
def validate_message(topic: str, payload: dict) -> None   # topic pattern + schema; ValueError
class OccupancyTracker:
    def __init__(self, bus, *, default_sigma: float = 5.0, clock=time.monotonic): ...
    def ledger_fields(self, shelter_ids) -> tuple[dict[str, float], dict[str, float]]
        # (occupancy_sigma, occupancy_age_s); never-seen shelter -> (default_sigma, 3600.0)
def apply_to_ledger_view(view: LedgerView, tracker: OccupancyTracker) -> LedgerView   # dataclasses.replace
def canonical_json(obj) -> bytes; def certificate_hash(cert) -> str   # same rule as V4_GATE_SPEC
class Actuator:                      # Python reference of the firmware logic
    def __init__(self, device_id: str, bus: Bus): ...
    def handle_command(self, topic: str, payload: dict) -> dict   # returns the ack payload it published
        # accept iff cert_id known (received on cert/), certificate_hash(cert) == cert["cert_hash"]
        # == payload["cert_hash"], kind in {DISPATCH, MIGRATION, OVERRIDE}, chosen action_key ==
        # f"{zone_id}->{shelter_id}" (vehicle) / shelter matches (admission), people equal
        # reject reasons: UNKNOWN_CERT, HASH_MISMATCH, KIND_NOT_ACTUATABLE, ACTION_MISMATCH
def measure_latency(bus, n: int = 100) -> dict   # p50/p95 publish -> ack, ms
```
`hil/sim/publisher.py`: simulated sensor nodes publishing the same messages (seeded, deterministic) so
the bridge and the System page run without hardware. `src/hil/` may import merged Lane S code
(`src.certify.ledger_view`, `src.certify.rollout`), never unmerged branches.

## Acceptance (tests/test_p28_hil.py; no network, no broker)
Every example message in `mqtt_topics.json` validates; malformed ones raise; `InMemoryBus` wildcard
delivery; tracker gives sigma/age from readings, and after a 60 s simulated dropout the age grows so the
rollout margin `k_sigma · sigma · (1 + age/age_scale)` is larger than before; actuator accepts the fixture
certificate CERT-000127 command and rejects unknown id, tampered certificate, wrong shelter, HOLD kind;
`certificate_hash` reproduces every fixture hash. Bench (human, after parts arrive): 100 publish→ack
round trips, results in `data/eval_results/phase28/latency.json` (recorded only from a real run).

## Out of scope
Field deployment, LoRa (mask deltas are only sized), cameras, any cloud broker.
