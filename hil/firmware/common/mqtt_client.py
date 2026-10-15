"""MicroPython MQTT connection with reconnect back-off and monotonic sequence."""

import json
import time

from umqtt.simple import MQTTClient


class NodeClient:
    def __init__(self, client_id, host, *, user=None, password=None):
        self.client = MQTTClient(client_id, host, user=user, password=password)
        self.seq = 0
        self._callback = None
        self._topics = []

    def connect(self):
        delay = 1
        while True:
            try:
                self.client.connect()
                if self._callback:
                    self.client.set_callback(self._callback)
                for topic in self._topics:
                    self.client.subscribe(topic.encode())
                return
            except OSError:
                time.sleep(delay)
                delay = min(delay * 2, 30)

    def subscribe(self, topic, callback):
        self._callback = callback
        self._topics.append(topic)
        self.client.set_callback(callback)
        self.client.subscribe(topic.encode())

    def publish(self, topic, payload):
        if payload.get("schema") in ("water-level-v1", "occupancy-v1"):
            self.seq += 1
            payload["seq"] = self.seq
        body = json.dumps(payload).encode()
        try:
            self.client.publish(topic.encode(), body, qos=1)
        except OSError:
            self.connect()
            self.client.publish(topic.encode(), body, qos=1)

    def poll(self):
        try:
            self.client.check_msg()
        except OSError:
            self.connect()
