"""Small MicroPython certificate verifier shared by actuator nodes."""

import hashlib
import json


def canonical_json(value):
    def encode(item):
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(key) + ":" + encode(item[key]) for key in sorted(item)) + "}"
        if isinstance(item, (list, tuple)):
            return "[" + ",".join(encode(member) for member in item) + "]"
        return json.dumps(item)

    return encode(value).encode("utf-8")


def certificate_hash(cert):
    return hashlib.sha256(canonical_json({k: v for k, v in cert.items() if k != "cert_hash"})).hexdigest()


class CertificateStore:
    def __init__(self, limit=64):
        self.limit = limit
        self.certs = {}

    def receive(self, cert):
        cert_id = cert.get("cert_id")
        if cert_id and certificate_hash(cert) == cert.get("cert_hash"):
            self.certs[cert_id] = cert
            if len(self.certs) > self.limit:
                self.certs.pop(next(iter(self.certs)))

    def verify(self, command):
        cert = self.certs.get(command.get("cert_id"))
        if cert is None:
            return "UNKNOWN_CERT"
        if certificate_hash(cert) != cert.get("cert_hash") or cert["cert_hash"] != command.get("cert_hash"):
            return "HASH_MISMATCH"
        if cert.get("kind") not in ("DISPATCH", "MIGRATION", "OVERRIDE"):
            return "KIND_NOT_ACTUATABLE"
        chosen = cert.get("chosen", {})
        action = chosen.get("action_key", "")
        shelter_id = command.get("shelter_id")
        if (not action.endswith("->" + str(shelter_id)) or
                ("zone_id" in command and action != str(command["zone_id"]) + "->" + str(shelter_id)) or
                chosen.get("people") != command.get("people") or
                chosen.get("group_id") != command.get("group_id")):
            return "ACTION_MISMATCH"
        return "OK"
