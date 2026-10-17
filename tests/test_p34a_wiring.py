"""Phase 34A acceptance tests (Lead) — API and console wired to the real gate. Do not edit; escalate instead.

Spec: specs/V4_WIRING_SPEC.md. The guided demo, certificates, replay and "why" come from a recorded run of the
merged Phase 25/26 engine (data/demo_v4/demo_trace.json, config v4-demo-trace-v1) that must rebuild byte-identically.
Rule tiers are read through from the P15T2 result file and never inferred. No network.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.milestone("P34A")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "contracts"
TRACE = ROOT / "data" / "demo_v4" / "demo_trace.json"
TIERS = ROOT / "data" / "constraints_v4" / "p15t2" / "tier_results.json"


def _schema(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _auth(password):
    return {"Authorization": "Basic " + base64.b64encode(f"sentinel:{password}".encode()).decode()}


@pytest.fixture(scope="module")
def graph():
    from src.geospatial import load_road_graph

    return load_road_graph()


@pytest.fixture(scope="module")
def trace():
    from src.api.demo_live import load_demo_trace

    return load_demo_trace()


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    mp = pytest.MonkeyPatch()
    mp.setenv("SENTINEL_DEMO_SOURCE", "RECORDED")
    mp.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    from src.api.app import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
    mp.undo()


def test_trace_rebuilds_byte_identically_and_validates(trace):
    from src.api.demo_live import build_demo_trace

    rebuilt = build_demo_trace()
    assert json.dumps(rebuilt, sort_keys=True) == json.dumps(trace, sort_keys=True)
    expected = json.dumps(trace, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert TRACE.read_bytes() == expected.encode("utf-8")
    jsonschema.validate(trace, _schema("demo_trace.schema.json"))
    step_schema = _schema("demo_step.schema.json")
    for index, step in enumerate(trace["steps"]):
        jsonschema.validate(step, step_schema)
        assert step["step_index"] == index
    kinds = {cert["kind"] for cert in trace["certificates"]}
    assert {"DISPATCH", "HOLD", "MIGRATION"} <= kinds  # the Lead pilot of this exact config produced all three


def test_every_trace_certificate_validates_chains_and_replays(trace, graph):
    from src.certify.certificate import CertificateInputs, validate_certificate, verify_chain
    from src.certify.replay import replay_certificate

    certs = trace["certificates"]
    assert [c["cert_id"] for c in certs] == [cid for ids in trace["step_certificates"] for cid in ids]
    assert verify_chain(certs) is None
    for cert in certs:
        validate_certificate(cert)
        report = replay_certificate(cert, CertificateInputs.from_dict(trace["inputs"][cert["cert_id"]]), graph=graph)
        assert report.result == "MATCH", (cert["cert_id"], report.mismatched_fields)


def test_steps_point_at_their_own_certificates(trace):
    issued = 0
    by_id = {c["cert_id"]: c for c in trace["certificates"]}
    for step, ids in zip(trace["steps"], trace["step_certificates"]):
        issued += len(ids)
        assert step["kpis"]["certificates_issued"] == issued
        kinds = {by_id[i]["kind"]: i for i in ids}
        if "DISPATCH" in kinds:
            assert step["kind"] == "NEW DISPATCH" and step["certificate_id"] == kinds["DISPATCH"]
        if "HOLD" in kinds:
            assert step["kind"].startswith("HOLD") and kinds["HOLD"] in (step["hold_record"] or "")
        if "MIGRATION" in kinds:
            assert kinds["MIGRATION"] in (step["auto_note"] or "")
        assert step["certificate_id"] is None or step["certificate_id"] in ids
        assert " ms" not in step["gate"]["meta"]  # no wall-clock values in a reproducible trace


def test_demo_endpoints_serve_the_recorded_trace(client, trace):
    start = client.post("/api/demo/start")
    assert start.status_code == 200
    assert start.headers["X-Sentinel-Source"] == "RECORDED"
    body = start.json()
    assert body["source"] == "RECORDED" and body["step_count"] == 6 and body["step"] == trace["steps"][0]
    for index in range(1, 6):
        body = client.post("/api/demo/step", json={"action": "next"}).json()
        assert body["step_index"] == index and body["step"] == trace["steps"][index]
    assert client.post("/api/demo/step", json={"action": "reset"}).json()["step_index"] == 0


def test_certificate_endpoints_and_real_replay(client, trace, graph):
    from src.certify.certificate import CertificateInputs
    from src.certify.replay import replay_certificate

    schema = _schema("certificate.schema.json")
    listing = client.get("/api/certificates").json()
    assert [c["cert_id"] for c in listing["certificates"]] == [c["cert_id"] for c in reversed(trace["certificates"])]
    dispatch = next(c for c in trace["certificates"] if c["kind"] == "DISPATCH")
    fetched = client.get(f"/api/certificates/{dispatch['cert_id']}")
    assert fetched.headers["X-Sentinel-Source"] == "RECORDED"
    assert fetched.json() == dispatch
    jsonschema.validate(fetched.json(), schema)
    inputs = CertificateInputs.from_dict(trace["inputs"][dispatch["cert_id"]])
    replay = client.post(f"/api/certificates/{dispatch['cert_id']}/replay", json={}).json()
    assert replay["result"] == "MATCH" and replay["mismatched_fields"] == []
    assert replay_certificate(dispatch, inputs, graph=graph).result == "MATCH"
    tampered = client.post(f"/api/certificates/{dispatch['cert_id']}/replay", json={"tamper": True}).json()
    assert tampered["result"] == "MISMATCH" and "forecast_hash" in tampered["mismatched_fields"]
    copy = {**dispatch, "forecast_hash": hashlib.sha256(b"tampered").hexdigest()}
    assert list(replay_certificate(copy, inputs, graph=graph).mismatched_fields) == tampered["mismatched_fields"]
    assert client.get("/api/certificates/CERT-999999").status_code == 404


def test_why_is_derived_from_each_certificate(client, trace):
    schema = _schema("decision_why.schema.json")
    for cert in trace["certificates"]:
        body = client.get(f"/api/decisions/{cert['cert_id']}/why").json()
        jsonschema.validate(body, schema)
        assert body["source"] == "RECORDED" and body["decision_id"] == cert["cert_id"]
        assert body["threshold"] == pytest.approx(1 - cert["params"]["eps_dispatch"])
        assert body["futures_used"] == cert["futures_used"]
        if cert["kind"] == "HOLD":
            assert body["certified_lower"] is None
        else:
            chosen = next(c for c in cert["candidates"] if c["action_key"] == cert["chosen"]["action_key"])
            assert body["certified_lower"] == chosen["lower"]
            assert f"{chosen['lower']:.3f}" in body["reasons"][0]
    assert client.get("/api/decisions/CERT-999999/why").status_code == 404


def test_fixture_mode_still_serves_wave_a_fixtures(monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.app import create_app

    monkeypatch.setenv("SENTINEL_DEMO_SOURCE", "FIXTURE")
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    with TestClient(create_app()) as fixture_client:
        assert fixture_client.post("/api/demo/start").json()["source"] == "FIXTURE"
        ids = [c["cert_id"] for c in fixture_client.get("/api/certificates").json()["certificates"]]
        assert "CERT-000127" in ids


def test_rule_tiers_are_read_from_the_p15t2_result(client):
    body = client.get("/api/constraints/tiers").json()
    jsonschema.validate(body, _schema("rule_tiers.schema.json"))
    records = json.loads(TIERS.read_text(encoding="utf-8"))["records"]
    assert body["status"] == "CURRENT" and body["t2_enabled"] is True
    assert body["results_sha256"] == hashlib.sha256(TIERS.read_bytes()).hexdigest()
    assert {r["rule_id"]: r["tier"] for r in body["rules"]} == {r["rule_id"]: r["tier"] for r in records}
    assert {r["rule_id"]: r["tier"] for r in body["rules"]} == {"NDMA-R01": "T1", "NDMA-R02": "T1"}
    assert {r["semantic_outcome"] for r in body["rules"]} == {"PARTIALLY_SUPPORTED"}
    assert body["evaluation_id"] == "v4-claim-support-eval-14d-v1"


def test_rule_tiers_never_infer_t2_and_go_stale(tmp_path, monkeypatch):
    import socket

    import src.constraints.claim_support_p14c as p14c

    def no_network(*args, **kwargs):
        raise AssertionError("the tiers path must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(p14c, "http_transport", no_network)
    from src.presentation.rule_tiers import rule_tiers

    original = json.loads(TIERS.read_text(encoding="utf-8"))
    as_t2 = json.loads(json.dumps(original))
    as_t2["records"][0]["tier"] = "T2"
    path = tmp_path / "t2.json"
    path.write_text(json.dumps(as_t2), encoding="utf-8")
    body = rule_tiers(results_path=path)
    assert body["status"] == "CURRENT"
    assert [r["tier"] for r in body["rules"]] == ["T2", "T1"]  # shown only because the file says so

    stale = json.loads(json.dumps(original))
    stale["approval_record_sha256"] = "0" * 64
    path.write_text(json.dumps(stale), encoding="utf-8")
    body = rule_tiers(results_path=path)
    assert body["status"] == "STALE" and body["status_reason"]
    assert all(r["tier"] is None for r in body["rules"])

    body = rule_tiers(results_path=TIERS, approval_path=tmp_path / "missing_approval.json")
    assert body["status"] == "STALE" and all(r["tier"] is None for r in body["rules"])

    body = rule_tiers(results_path=tmp_path / "absent.json")
    assert body["status"] == "MISSING" and body["rules"] == []


def test_new_manifest_items_render(client):
    items = {item["id"]: item for item in client.get("/api/evidence").json()["items"]}
    assert items["p10-nsu-lookahead-k3"]["display"] == "1.531"
    assert items["p10-nsu-random-valid"]["display"] == "0.000"
    assert items["p10-nsu-ppo-mean"]["display"] == "0.209"
    assert items["p13-bm25-direct-hit-at-5"]["display"] == "86.7 %"
    assert items["p27-bar1-r"]["display"] == "21.4 %"
    assert items["p25-replay-count"]["display"] == "1274"
    for key, item in items.items():
        if key.startswith(("p10-", "p13-")):
            assert item["value"] is not None, key


def test_static_console_and_basic_auth(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from src.api.app import create_app

    (tmp_path / "index.html").write_text('<!doctype html><div id="root"></div>', encoding="utf-8")
    monkeypatch.setenv("SENTINEL_WEB_DIST", str(tmp_path))
    monkeypatch.setenv("SENTINEL_DEMO_SOURCE", "FIXTURE")
    monkeypatch.setenv("SENTINEL_DEMO_PASSWORD", "test-only-password")
    with TestClient(create_app()) as guarded:
        assert guarded.get("/api/health").status_code == 200
        denied = guarded.get("/")
        assert denied.status_code == 401 and denied.headers["WWW-Authenticate"].startswith("Basic")
        assert guarded.post("/api/demo/start").status_code == 401
        assert guarded.post("/api/demo/start", headers=_auth("wrong")).status_code == 401
        assert guarded.post("/api/demo/start", headers=_auth("test-only-password")).status_code == 200
        page = guarded.get("/", headers=_auth("test-only-password"))
        assert page.status_code == 200 and '<div id="root">' in page.text
        assert '<div id="root">' in guarded.get("/decisions", headers=_auth("test-only-password")).text
    monkeypatch.delenv("SENTINEL_DEMO_PASSWORD")
    with TestClient(create_app()) as open_client:
        assert open_client.get("/").status_code == 200


def test_trace_and_reasons_make_no_outcome_claim(client, trace):
    policy = _schema("claims_policy.json")
    banned = [re.compile(p, re.IGNORECASE) for p in policy["banned_outcome_patterns"]]
    exempt = [re.compile(re.escape(p), re.IGNORECASE) for p in policy["negation_exemptions"]]
    texts = [trace["config"]["seed_note"]]
    for step in trace["steps"]:
        texts += [step["caption"], step["suggestion"]["title"], step["suggestion"]["meta"], *step["suggestion"]["why"],
                  step["auto_note"] or "", step["hold_record"] or "", *(e["text"] for e in step["events"])]
    for cert in trace["certificates"]:
        texts += client.get(f"/api/decisions/{cert['cert_id']}/why").json()["reasons"]
    for text in texts:
        if any(e.search(text) for e in exempt):
            continue
        assert not any(b.search(text) for b in banned), text
