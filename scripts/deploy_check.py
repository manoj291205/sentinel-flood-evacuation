"""Post-deploy check of a running Sentinel demo (Phase 34B).

Runs the checks of ``specs/contracts/deploy_check.json`` in order against a base URL, stdlib HTTP only.
The demo password (``--password`` or ``SENTINEL_DEMO_PASSWORD``) is sent as HTTP basic auth and is never printed
or written. Exit code 0 only if every check that ran passed.

    python scripts/deploy_check.py https://host.example --password ...
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "contracts"


class CheckFailed(Exception):
    pass


def _load(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


class _Client:
    def __init__(self, base_url: str, user: str, password: str | None, timeout: float):
        self.base, self.timeout = base_url.rstrip("/"), timeout
        self.auth = None
        if password:
            token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
            self.auth = f"Basic {token}"

    def request(self, method: str, path: str, *, body=None, auth: bool = False):
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if auth and self.auth:
            req.add_header("Authorization", self.auth)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()
        except (urllib.error.URLError, OSError) as err:
            raise CheckFailed(f"request failed: {type(err).__name__}") from None

    def json(self, method: str, path: str, *, body=None, auth: bool = False):
        status, headers, raw = self.request(method, path, body=body, auth=auth)
        if status != 200:
            raise CheckFailed(f"{method} {path} -> HTTP {status}")
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise CheckFailed(f"{method} {path} did not return JSON") from None


def _validate(instance, schema_name: str, what: str) -> None:
    import jsonschema

    try:
        jsonschema.validate(instance, _load(schema_name))
    except jsonschema.ValidationError as err:
        raise CheckFailed(f"{what} does not validate {schema_name}: {err.message[:120]}") from None


def _health(c, state):
    body = c.json("GET", "/api/health")
    if body.get("status") != "ok" or body.get("simulated") is not True:
        raise CheckFailed("status must be 'ok' and simulated true")


def _auth_required(c, state):
    status, headers, _ = c.request("GET", "/", auth=False)
    if status != 401:
        raise CheckFailed(f"expected HTTP 401 without credentials, got {status}")
    if not (headers.get("WWW-Authenticate") or "").startswith("Basic"):
        raise CheckFailed("401 without a 'Basic' WWW-Authenticate header")


def _index(c, state):
    status, headers, raw = c.request("GET", "/", auth=True)
    if status != 200:
        raise CheckFailed(f"HTTP {status}")
    if "text/html" not in (headers.get("Content-Type") or ""):
        raise CheckFailed("Content-Type is not text/html")
    if '<div id="root">' not in raw.decode("utf-8", "replace"):
        raise CheckFailed("body has no root element")


def _demo_response(body, expected_index):
    if body.get("step_index") != expected_index:
        raise CheckFailed(f"step_index {body.get('step_index')} != {expected_index}")
    _validate(body.get("step"), "demo_step.schema.json", "step")


def _demo_start(c, state):
    body = c.json("POST", "/api/demo/start", body={}, auth=True)
    if body.get("step_count") != 6:
        raise CheckFailed(f"step_count {body.get('step_count')} != 6")
    if body.get("source") not in {"RECORDED", "FIXTURE"}:
        raise CheckFailed(f"unexpected source {body.get('source')!r}")
    _demo_response(body, 0)


def _demo_walk(c, state):
    for expected in range(1, 6):
        _demo_response(c.json("POST", "/api/demo/step", body={"action": "next"}, auth=True), expected)


def _certificates(c, state):
    listing = c.json("GET", "/api/certificates", auth=True)
    certs = listing.get("certificates") or []
    if not certs:
        raise CheckFailed("no certificates listed")
    cert_id = certs[0]["cert_id"]
    _validate(c.json("GET", f"/api/certificates/{cert_id}", auth=True), "certificate.schema.json", "certificate")
    state["cert_id"] = cert_id


def _replay_match(c, state):
    body = c.json("POST", f"/api/certificates/{state['cert_id']}/replay", body={}, auth=True)
    if body.get("result") != "MATCH":
        raise CheckFailed(f"result {body.get('result')!r}, expected 'MATCH'")


def _replay_tamper(c, state):
    body = c.json("POST", f"/api/certificates/{state['cert_id']}/replay", body={"tamper": True}, auth=True)
    if body.get("result") != "MISMATCH" or "forecast_hash" not in (body.get("mismatched_fields") or []):
        raise CheckFailed("tampered replay was not reported as a MISMATCH on forecast_hash")


def _evidence(c, state):
    _validate(c.json("GET", "/api/evidence", auth=True), "evidence.schema.json", "evidence")


CHECKS = {
    "health": _health, "auth-required": _auth_required, "index": _index, "demo-start": _demo_start,
    "demo-walk": _demo_walk, "certificates": _certificates, "replay-match": _replay_match,
    "replay-tamper": _replay_tamper, "evidence": _evidence,
}


def run(base_url: str, password: str | None, timeout: float = 30.0) -> list[dict]:
    contract = _load("deploy_check.json")
    client = _Client(base_url, contract["basic_auth_user"], password, timeout)
    state: dict = {}
    results = []
    for spec in contract["checks"]:
        cid = spec["id"]
        if spec.get("only_with_password") and not password:
            results.append({"id": cid, "status": "SKIP", "reason": "no password given"})
            continue
        try:
            CHECKS[cid](client, state)
            results.append({"id": cid, "status": "PASS"})
        except CheckFailed as err:
            results.append({"id": cid, "status": "FAIL", "reason": str(err)})
        except (KeyError, TypeError, AttributeError) as err:
            results.append({"id": cid, "status": "FAIL", "reason": f"unexpected response shape ({type(err).__name__})"})
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check a running Sentinel demo against deploy_check.json.")
    parser.add_argument("base_url")
    parser.add_argument("--password", default=None, help="demo password (or SENTINEL_DEMO_PASSWORD)")
    parser.add_argument("--json", dest="json_path", default=None, help="also write the results to this file")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    password = args.password or os.environ.get("SENTINEL_DEMO_PASSWORD") or None
    results = run(args.base_url, password, args.timeout)
    for row in results:
        if row["status"] == "PASS":
            print(f"PASS {row['id']}")
        elif row["status"] == "SKIP":
            print(f"SKIP {row['id']}: {row['reason']}")
        else:
            print(f"FAIL {row['id']}: {row['reason']}")
    ran = [r for r in results if r["status"] != "SKIP"]
    passed = sum(r["status"] == "PASS" for r in ran)
    print(f"deploy_check: {passed}/{len(ran)} passed")
    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps({"base_url": args.base_url, "results": results}, indent=2), encoding="utf-8")
    return 0 if passed == len(ran) else 1


if __name__ == "__main__":
    sys.exit(main())
