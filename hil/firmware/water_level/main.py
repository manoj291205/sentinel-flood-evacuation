"""ESP32 water-level sensor. Configure Wi-Fi and broker locally before boot."""

import time
from machine import Pin, time_pulse_us

from common.mqtt_client import NodeClient

TRIG = Pin(5, Pin.OUT)
ECHO = Pin(18, Pin.IN)
MOUNT_HEIGHT_CM = 50.0


def distance_cm():
    TRIG.off()
    time.sleep_us(2)
    TRIG.on()
    time.sleep_us(10)
    TRIG.off()
    duration = time_pulse_us(ECHO, 1, 30000)
    if duration < 0:
        raise OSError("ultrasonic echo timeout")
    return duration * 0.0343 / 2


def sample_level_cm():
    readings = []
    for _ in range(5):
        readings.append(max(0.0, MOUNT_HEIGHT_CM - distance_cm()))
        time.sleep_ms(60)
    readings.sort()
    return readings[2]


def run(host, zone_id="Z-03", device_id="esp32-level-01"):
    client = NodeClient(device_id, host)
    client.connect()
    while True:
        try:
            level = sample_level_cm()
            client.publish("sentinel/v1/zone/%s/water_level" % zone_id,
                           {"schema": "water-level-v1", "device_id": device_id,
                            "zone_id": zone_id, "level_cm": level,
                            "ts_utc": utc_now()})
        except OSError:
            pass
        time.sleep(2)


def utc_now():
    year, month, day, hour, minute, second = time.gmtime()[:6]
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, hour, minute, second)
