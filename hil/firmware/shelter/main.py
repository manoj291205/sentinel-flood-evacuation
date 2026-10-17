"""ESP32 shelter counter and certificate-gated admission lamps."""

import json
import time
from machine import Pin

from common.cert_verify import CertificateStore
from common.mqtt_client import NodeClient

BEAM_A = Pin(32, Pin.IN, Pin.PULL_UP)
BEAM_B = Pin(33, Pin.IN, Pin.PULL_UP)
ADMIT = Pin(26, Pin.OUT)
REJECT = Pin(27, Pin.OUT)


def utc_now():
    y, m, d, h, minute, s = time.gmtime()[:6]
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, h, minute, s)


class Counter:
    def __init__(self):
        import esp32

        self.nvs = esp32.NVS("sentinel")
        try:
            self.count = self.nvs.get_i32("count")
        except OSError:
            self.count = 0
        self.first = None
        self.last_change = time.ticks_ms()

    def update(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_change) < 50:
            return False
        a, b = BEAM_A.value() == 0, BEAM_B.value() == 0
        if not a and not b:
            self.first = None
        elif self.first is None:
            self.first = "A" if a else "B"
            self.last_change = now
        elif (self.first == "A" and b) or (self.first == "B" and a):
            self.count = max(0, self.count + (1 if self.first == "A" else -1))
            self.nvs.set_i32("count", self.count)
            self.nvs.commit()
            self.first = None
            self.last_change = now
            return True
        return False


def run(host, shelter_id="S-04", device_id="esp32-shelter-01"):
    bus = NodeClient(device_id, host)
    certs = CertificateStore()
    counter = Counter()

    def on_message(topic, body):
        payload = json.loads(body.decode())
        if topic.startswith(b"sentinel/v1/cert/"):
            certs.receive(payload)
            return
        reason = certs.verify(payload)
        ADMIT.value(reason == "OK")
        REJECT.value(reason != "OK")
        bus.publish("sentinel/v1/ack/%s" % device_id,
                    {"schema": "ack-v1", "device_id": device_id,
                     "cert_id": payload.get("cert_id", ""), "accepted": reason == "OK",
                     "reason": reason, "ts_utc": utc_now()})

    bus.connect()
    bus.subscribe("sentinel/v1/cert/+", on_message)
    bus.subscribe("sentinel/v1/command/shelter/%s/admission" % shelter_id, on_message)
    last_report = time.ticks_ms() - 5000
    while True:
        changed = counter.update()
        if changed or time.ticks_diff(time.ticks_ms(), last_report) >= 5000:
            bus.publish("sentinel/v1/shelter/%s/occupancy" % shelter_id,
                        {"schema": "occupancy-v1", "device_id": device_id,
                         "shelter_id": shelter_id, "count": counter.count,
                         "sigma": 0.5 + 0.02 * counter.count, "ts_utc": utc_now()})
            last_report = time.ticks_ms()
        bus.poll()
        time.sleep_ms(20)
