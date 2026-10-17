"""ESP32 vehicle display: certified commands only."""

import json
import time
from machine import I2C, Pin

from common.cert_verify import CertificateStore
from common.mqtt_client import NodeClient


def utc_now():
    y, m, d, h, minute, s = time.gmtime()[:6]
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, m, d, h, minute, s)


def run(host, vehicle_id="V-01", device_id="esp32-vehicle-01"):
    import ssd1306

    display = ssd1306.SSD1306_I2C(128, 64, I2C(0, scl=Pin(22), sda=Pin(21)))
    bus = NodeClient(device_id, host)
    certs = CertificateStore()

    def on_message(topic, body):
        payload = json.loads(body.decode())
        if topic.startswith(b"sentinel/v1/cert/"):
            certs.receive(payload)
            return
        reason = certs.verify(payload)
        display.fill(0)
        if reason == "OK":
            display.text("CERTIFIED ROUTE", 0, 0)
            display.text(payload["zone_id"] + " -> " + payload["shelter_id"], 0, 18)
            display.text(str(payload["people"]) + " people", 0, 34)
        else:
            display.text("REJECTED", 0, 0)
            display.text(reason[:16], 0, 18)
        display.show()
        bus.publish("sentinel/v1/ack/%s" % device_id,
                    {"schema": "ack-v1", "device_id": device_id,
                     "cert_id": payload.get("cert_id", ""), "accepted": reason == "OK",
                     "reason": reason, "ts_utc": utc_now()})

    bus.connect()
    bus.subscribe("sentinel/v1/cert/+", on_message)
    bus.subscribe("sentinel/v1/command/vehicle/%s" % vehicle_id, on_message)
    while True:
        bus.poll()
        time.sleep_ms(20)
