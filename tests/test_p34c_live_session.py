"""Phase 34C acceptance tests (Lead) — live certified session over the API. Do not edit; escalate instead.

Spec: specs/V4_WIRING_SPEC.md section 10. One scripted run (module fixture) drives an API session and a direct
SimulationSession(certified=True) twin through the same decisions and records both; the tests compare them.
World v4-medium-dt2-v1, seed 620003, params v4-cert-test-v1 (Lead pilot: step 0 is a HOLD with every option UNDECIDED,
and with ACCEPT at every step a group is re-routed at step 4). Live sessions re-check groups on the road (P34R).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest

pytestmark = pytest.mark.milestone("P34C")

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "specs" / "contracts"
EVIDENCE = {"source_id": "ndma-flood-guidelines-2008", "page": 64, "chunk_id": "ndma-flood-guidelines-2008-p64-c0"}
SEED, WORLD, PARAMS = 620003, "v4-medium-dt2-v1", "v4-cert-test-v1"
VOLATILE = {"timestamp", "audit_id", "timestamp_utc"}


def _schema(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _stable(row):
    return {k: v for k, v in row.items() if k not in VOLATILE}


def _pending(session):
    """The twin's pending CertificationResult for the current step (P34R accessor)."""
    return session.certification()[0]


@pytest.fixture(scope="module")
def run():
    from fastapi.testclient import TestClient

    from src.api.app import create_app
    from src.geospatial import load_road_graph
    from src.human_decision import EvidenceReference, action_key
    from src.simulation_session import SimulationSession

    mp = pytest.MonkeyPatch()
    mp.setenv("SENTINEL_DEMO_SOURCE", "FIXTURE")
    mp.delenv("SENTINEL_DEMO_PASSWORD", raising=False)
    graph = load_road_graph()
    twin = SimulationSession(SEED, WORLD, graph=graph, certified=True, params_id=PARAMS, recertify=True)
    evidence = EvidenceReference(**EVIDENCE)
    out = {"contexts": [], "twin_pending": [], "api_records": [], "twin_records": [], "responses": []}
    with TestClient(create_app()) as client:
        created = client.post("/api/sessions", json={"seed": SEED, "regime": WORLD, "certified": True,
                                                      "params_id": PARAMS})
        assert created.status_code == 200, created.text
        out["session"] = created.json()
        sid = out["session"]["session_id"]

        def context():
            body = client.get(f"/api/sessions/{sid}/context")
            assert body.status_code == 200, body.text
            out["contexts"].append(body.json())
            out["twin_pending"].append(_pending(twin))
            return body.json()

        def decide(decision, selected=None, reason=""):
            payload = {"decision": decision, "reason": reason, "evidence": EVIDENCE}
            if selected is not None:
                payload["selected_action"] = selected
            response = client.post(f"/api/sessions/{sid}/decisions", json=payload)
            assert response.status_code == 200, response.text
            out["responses"].append(response.json())
            out["api_records"].append(response.json()["audit_record"])
            action = None
            if selected is not None:
                action = next(a for a in twin.context().snapshot.canonical_actions if action_key(a) == selected)
            record, _ = twin.decide(decision, evidence, selected_action=action, reason=reason)
            out["twin_records"].append(record)

        # step 0: HOLD recommended; an uncertified override is refused, then ACCEPT commits the HOLD
        ctx = context()
        uncertified = next(a for a in ctx["certified"]["alternatives"] if not a["certified"])
        refused = client.post(f"/api/sessions/{sid}/decisions", json={
            "decision": "OVERRIDE", "selected_action": uncertified["action_key"], "reason": "operator insists",
            "evidence": EVIDENCE})
        out["refused"] = (refused.status_code, refused.json(), uncertified)
        out["after_refusal"] = client.get(f"/api/sessions/{sid}/state").json()
        out["certs_after_refusal"] = client.get(f"/api/sessions/{sid}/certificates").json()["certificates"]
        decide("ACCEPT")
        # step 1: OVERRIDE to a certified alternative (a dispatch if one is offered, else HOLD)
        ctx = context()
        keys = [a["action_key"] for a in ctx["allowed_override_actions"]]
        choice = next((k for k in keys if k != "WAIT"), keys[0])
        decide("OVERRIDE", choice, "field team reports the preferred road is busy")
        # step 2: REJECT with a reason, watched over the WebSocket
        context()
        with client.websocket_connect(f"/ws/sessions/{sid}") as ws:
            messages = [ws.receive_json()]
            decide("REJECT", reason="waiting for a fresh water-level reading")
            while True:
                messages.append(ws.receive_json())
                if messages[-1]["type"] == "state":
                    break
        out["ws"] = messages
        out["audit"] = client.get(f"/api/sessions/{sid}/audit").json()
        out["certificates"] = client.get(f"/api/sessions/{sid}/certificates").json()["certificates"]
        out["replays"] = [client.post(f"/api/sessions/{sid}/certificates/{c['cert_id']}/replay", json={}).json()
                          for c in out["certificates"]]
        # a second session: ACCEPT at every step until the step-4 re-route
        second = client.post("/api/sessions", json={"seed": SEED, "regime": WORLD, "certified": True}).json()
        twin2 = SimulationSession(SEED, WORLD, graph=graph, certified=True, params_id=PARAMS, recertify=True)
        out["accept_run"], out["accept_contexts"] = [], []
        for _ in range(5):
            out["accept_contexts"].append(client.get(f"/api/sessions/{second['session_id']}/context").json())
            response = client.post(f"/api/sessions/{second['session_id']}/decisions",
                                   json={"decision": "ACCEPT", "reason": "", "evidence": EVIDENCE})
            assert response.status_code == 200, response.text
            out["accept_run"].append(response.json())
            twin2.decide("ACCEPT", evidence)
        out["accept_certificates"] = client.get(f"/api/sessions/{second['session_id']}/certificates").json()["certificates"]
        out["accept_context"] = client.get(f"/api/sessions/{second['session_id']}/context").json()
        out["twin2"] = twin2
        out["bad_regime"] = client.post("/api/sessions", json={"seed": SEED, "regime": "v3-medium-v1",
                                                               "certified": True}).status_code
        out["bad_params"] = client.post("/api/sessions", json={"seed": SEED, "regime": WORLD, "certified": True,
                                                               "params_id": "v4-cert-v1"}).status_code
        legacy = client.post("/api/sessions", json={"seed": 620000, "regime": "v3-medium-v1"}).json()
        out["legacy_context"] = client.get(f"/api/sessions/{legacy['session_id']}/context").json()
    out["twin"] = twin
    yield out
    mp.undo()


def test_request_validation_and_legacy_sessions_unchanged(run):
    assert run["session"]["certified"] is True and run["session"]["params_id"] == PARAMS
    assert run["bad_regime"] == 422 and run["bad_params"] == 422
    assert "certified" not in run["legacy_context"]


def test_certified_context_matches_the_twin(run):
    schema = _schema("live_context.schema.json")
    for ctx, pending in zip(run["contexts"], run["twin_pending"]):
        jsonschema.validate(ctx, schema)
        cert = ctx["certified"]
        assert cert["recommendation"]["action_key"] == pending.chosen_key
        assert ctx["recommendation"]["action_key"] in (pending.chosen_key, "WAIT")
        assert cert["futures_used"] == pending.n_final and cert["looks"] == pending.looks
        assert cert["threshold"] == pytest.approx(0.70)
        assert {c["action_key"]: c["verdict"] for c in cert["candidates"] if c["action_key"] != "WAIT"} == {
            c.action_key: c.verdict.value for c in pending.candidates}
        by_key = {c.action_key: c for c in pending.candidates}
        for alt in cert["alternatives"]:
            assert alt["action_key"] != cert["recommendation"]["action_key"]
            assert alt["certified"] == (by_key[alt["action_key"]].verdict.value == "FEASIBLE")
            assert alt["lower"] == pytest.approx(by_key[alt["action_key"]].lower)
            if not alt["certified"]:
                assert "not certified" in alt["comparison"]
    first = run["contexts"][0]["certified"]
    assert first["recommendation"]["action_key"] == "WAIT"  # pilot: step 0 has no certified dispatch
    assert first["why"][0].startswith("No dispatch option reached the threshold")
    later = run["contexts"][1]["certified"]
    if later["recommendation"]["action_key"] != "WAIT":
        pending = {c.action_key: c for c in run["twin_pending"][1].candidates}
        assert f"{pending[later['recommendation']['action_key']].lower:.3f}" in later["why"][0]


def test_decisions_match_the_twin_and_advance(run):
    twin = run["twin"]
    assert len(run["api_records"]) == 3
    for api_row, twin_row in zip(run["api_records"], run["twin_records"]):
        assert _stable(api_row) == _stable(twin_row)
    assert [r["decision"] for r in run["api_records"]] == ["ACCEPT", "OVERRIDE", "REJECT"]
    assert run["certificates"] == twin.certificates()
    committed = [c for response in run["responses"] for c in response["certificates"]]
    assert [c["cert_id"] for c in committed] == [c["cert_id"] for c in twin.certificates()]
    kinds = [c["kind"] for c in twin.certificates()]
    assert kinds[0] == "HOLD" and kinds[2] == "HOLD"
    assert kinds[1] in ("OVERRIDE", "HOLD")
    assert run["responses"][-1]["state"]["current_timestep"] == twin.state.current_timestep == 3


def test_uncertified_override_is_refused_flagged_and_recorded(run):
    status, body, alt = run["refused"]
    assert status == 422
    assert body["flag"] == "UNCERTIFIED_OVERRIDE_REFUSED" and body["action_key"] == alt["action_key"]
    assert body["verdict"] == alt["verdict"]
    assert run["after_refusal"]["current_timestep"] == 0 and run["certs_after_refusal"] == []
    refusals = run["audit"]["refusals"]
    assert len(refusals) == 1
    row = refusals[0]
    assert (row["timestep"], row["decision"], row["action_key"], row["flag"], row["reason"]) == (
        0, "OVERRIDE", alt["action_key"], "UNCERTIFIED_OVERRIDE_REFUSED", "operator insists")
    assert all(r.get("decision") != "OVERRIDE" or r["timestep"] != 0 for r in run["audit"]["audit"])


def test_session_certificates_validate_and_replay(run):
    from src.certify.certificate import validate_certificate, verify_chain

    assert verify_chain(run["certificates"]) is None
    for cert in run["certificates"]:
        validate_certificate(cert)
    assert [r["result"] for r in run["replays"]] == ["MATCH"] * len(run["certificates"])


def test_websocket_pushes_decision_certificate_events_state(run):
    schema = _schema("live_ws_message.schema.json")
    cert_schema = _schema("certificate.schema.json")
    messages = run["ws"]
    for message in messages:
        jsonschema.validate(message, schema)
    seqs = [m["seq"] for m in messages]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    types = [m["type"] for m in messages]
    assert types[0] == "state" and types[1] == "decision" and types[-1] == "state"
    certs = [m["payload"] for m in messages if m["type"] == "certificate"]
    assert certs and certs[-1] == run["certificates"][-1]
    for cert in certs:
        jsonschema.validate(cert, cert_schema)
    assert types.index("certificate") < min([i for i, t in enumerate(types) if t == "event"] or [len(types)])
    assert types.count("recheck") == len(run["responses"][-1]["rechecks"])


def test_live_session_re_checks_groups_on_the_road(run):
    twin2 = run["twin2"]
    assert run["accept_certificates"] == twin2.certificates()
    assert "MIGRATION" in [c["kind"] for c in twin2.certificates()]  # Lead pilot: re-route at step 4
    # The re-check is lazy (V4_RELEASE_SPEC Amendment 2026-10-17): it runs on the first call that consults a step, so here
    # (context fetched before each decision) a step's rows arrive with its context; a decision response carries only the
    # rows written during that call. Context rows then decision rows, step by step, equal the twin's log.
    rows = [row for ctx_body, response in zip(run["accept_contexts"], run["accept_run"])
            for row in [*ctx_body["certified"]["rechecks"], *response["rechecks"]]]
    keys = ("timestep", "group_id", "action", "verdict", "cert_id")
    assert [{k: r[k] for k in keys} for r in rows] == [{k: r[k] for k in keys} for r in twin2.recert_log]
    for ctx_body in run["accept_contexts"]:
        assert all(r["timestep"] == ctx_body["certified"]["timestep"] for r in ctx_body["certified"]["rechecks"])
    migrate = next(r for r in rows if r["action"] == "MIGRATE")
    assert migrate["cert_id"] in [c["cert_id"] for c in run["accept_certificates"] if c["kind"] == "MIGRATION"]
    ctx = run["accept_context"]["certified"]
    jsonschema.validate(run["accept_context"], _schema("live_context.schema.json"))
    assert all(r["timestep"] == ctx["timestep"] for r in ctx["rechecks"])


def test_live_text_makes_no_outcome_claim(run):
    policy = _schema("claims_policy.json")
    banned = [re.compile(p, re.I) for p in policy["banned_outcome_patterns"]]
    exempt = [re.compile(re.escape(p), re.I) for p in policy["negation_exemptions"]]
    for ctx in run["contexts"]:
        cert = ctx["certified"]
        for text in [*cert["why"], cert["note"], *(a["comparison"] for a in cert["alternatives"]),
                     *(r["route"] for r in cert["rechecks"])]:
            if any(e.search(text) for e in exempt):
                continue
            assert not any(b.search(text) for b in banned), text
