"""Operational evidence is authenticated independently of caller-supplied metadata."""

from dataclasses import replace
import hashlib
import json
import socket

import pytest

from src.constraints.claim_support import EvidenceChunk, finalize_semantic_result, safe_to_cite
from src.constraints.evidence import (
    authenticate_evidence, authenticate_evidence_reference, get_authenticated_evidence,
    operational_citation_eligible,
)
from src.constraints.runtime_rules import load_runtime_rules


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    def denied(*args, **kwargs):
        raise AssertionError("runtime evidence verification must stay offline")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture(scope="module")
def chunk():
    return get_authenticated_evidence("ndma-temporary-shelters-2019-p38-c1")


def test_canonical_reference_resolves_without_accepting_fabricated_metadata(chunk):
    metadata = authenticate_evidence_reference(chunk.source_id, chunk.page, chunk.chunk_id)
    assert metadata["passage_sha256"] == chunk.passage_sha256
    assert "text" not in metadata
    assert authenticate_evidence(chunk)
    for altered in (replace(chunk, chunk_id="invented"), replace(chunk, source_id="invented"),
                    replace(chunk, page=chunk.page + 1), replace(chunk, filename="invented.pdf")):
        assert not authenticate_evidence(altered)
    with pytest.raises(ValueError):
        authenticate_evidence_reference("invented", chunk.page, chunk.chunk_id)


def test_self_consistent_invented_chunk_is_not_an_authenticated_source():
    text = "An invented authoritative rule."
    invented = EvidenceChunk("fake", "fake", "fake.pdf", 1, text,
                             hashlib.sha256(text.encode("utf-8")).hexdigest())
    assert not authenticate_evidence(invented)


def test_runtime_citation_requires_supported_verdict_and_authentic_verbatim_spans(chunk):
    supported = finalize_semantic_result(evidence=chunk, verdict="SUPPORTED", confidence=.9,
                                        supporting_spans=[chunk.text[:80]], reason="fixture")
    assert operational_citation_eligible(supported, chunk)
    bad = finalize_semantic_result(evidence=chunk, verdict="SUPPORTED", confidence=.9,
                                  supporting_spans=["a span absent from the source"], reason="fixture")
    assert safe_to_cite(bad.verdict)  # Historical classifier metrics remain unchanged.
    assert not operational_citation_eligible(bad, chunk)
    assert not operational_citation_eligible(replace(supported, verdict="PARTIALLY_SUPPORTED"), chunk)


def test_recorded_partial_rules_are_visible_but_never_promoted_to_enforcement():
    loaded = load_runtime_rules()
    assert loaded.rules == ()
    assert loaded.metadata["status"] == "CURRENT"
    assert loaded.metadata["active_t2_count"] == 0
    assert {row["tier"] for row in loaded.metadata["configured_rules"]} == {"T1"}
    assert all(row["enforced"] is False for row in loaded.metadata["configured_rules"])


def test_tampered_result_identity_fails_closed(tmp_path):
    from src.constraints.runtime_rules import RESULTS_PATH
    result = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    result["rules_file_sha256"] = "0" * 64
    path = tmp_path / "tiers.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    loaded = load_runtime_rules(tier_results_path=path)
    assert loaded.rules == ()
    assert loaded.metadata["status"] == "STALE"


def test_live_session_refuses_an_untrusted_catalog_instead_of_dropping_rules():
    from src.constraints.runtime_rules import RuntimeRuleSet
    from src.simulation_session import SimulationSession
    stale = RuntimeRuleSet((), {"status": "STALE", "reason": "approval hash mismatch"})
    with pytest.raises(ValueError, match="runtime rule catalog"):
        SimulationSession(620003, "v4-medium-dt2-v1", certified=True,
                          params_id="v4-cert-test-v1", runtime_rules=stale)


def approved_fixture(tmp_path, chunk):
    """Synthetic authorization metadata; neither an actual NDMA rule nor a provider result."""
    from src.constraints.runtime_rules import ROOT
    from src.constraints.claim_support_p14d import split_sentences
    approval = json.loads((ROOT / "specs/approvals/t2_semantic_verifier.json").read_text(encoding="utf-8"))
    sentence = split_sentences(chunk.text)[0]
    rule = {"rule_id": "TEST-AUTHORIZED", "text": sentence, "predicate": "MAX_TRAVEL_MINUTES",
            "params": {"minutes": 0.0}, "strict_fallback": {"minutes": 0.0},
            "evidence": {"source_id": chunk.source_id, "filename": chunk.filename,
                         "page": chunk.page, "chunk_id": chunk.chunk_id,
                         "passage_sha256": chunk.passage_sha256, "span": sentence},
            "approved": True, "approved_by": "temporary integration fixture",
            "approved_utc": "2026-10-26T00:00:00Z"}
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(json.dumps({"schema": "ndma-constraints-v1", "rules": [rule]}), encoding="utf-8")
    score_path = tmp_path / "score.json"
    score_path.write_text(json.dumps({"evaluation_id": approval["evaluation_id"],
                                     "t2_verdict": approval["verdict"]}), encoding="utf-8")
    approval.update(score_path="score.json", score_sha256=hashlib.sha256(score_path.read_bytes()).hexdigest())
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    approval_sha = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    identity = {k: approval[k] for k in ("evaluation_id", "provider_id", "model_id", "prompt_version", "prompt_sha256")}
    result = {"schema": "p15t2-tier-results-v1", "rules_file": "rules.json",
              "rules_file_sha256": hashlib.sha256(rules_path.read_bytes()).hexdigest(),
              "approval_record_sha256": approval_sha, "t2_enabled": True,
              "records": [{**identity, "approval_record_sha256": approval_sha,
                           "rule_id": rule["rule_id"], "tier": "T2", "active_params": rule["params"],
                           "semantic_status": "CALLED", "semantic": {
                               "outcome": "SUPPORTED", "source_integrity_pass": True,
                               "supporting_sentence_ids": [1], "confidence": .99,
                               "http_status": 200, "response_model": approval["model_id"],
                               "finish_reason": "stop"}}]}
    result_path = tmp_path / "tiers.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return rules_path, result_path, approval_path


def test_authorized_fixture_flows_through_live_gate_and_enforces_its_predicate(tmp_path, chunk):
    from types import SimpleNamespace
    from src.simulation_session import SimulationSession
    from src.certify.rollout import Candidate, Outcome
    from src.certify.ledger_view import LedgerView
    rules, results, approval = approved_fixture(tmp_path, chunk)
    loaded = load_runtime_rules(root=tmp_path, rules_path=rules,
                                tier_results_path=results, approval_path=approval)
    assert loaded.metadata["enforced_count"] == 1
    session = SimulationSession(620003, "v4-medium-dt2-v1", certified=True,
                                params_id="v4-cert-test-v1", runtime_rules=loaded)
    assert session.gate.rules == loaded.rules
    assert "+rules-" in session.gate.params.params_id
    # Exercise the same gate rollout, with a simple future isolating the policy term.
    graph = SimpleNamespace(edges_by_id={"e1": SimpleNamespace(
        edge_id="e1", u="a", v="b", length_m=1000., assumed_speed_kph=30.)})
    class Future:
        k = 1
        start_timestep = 0
        steps = 20
        def edge_open(self, e, t): return True
        def edge_hazard(self, e, t): return 0.
        def shelter_severity(self, s, t): return .1
        def shelter_status(self, s, t): return "OPEN"
        def walk_ins(self, s, t): return 0
        def travel_normal(self, *key): return 0.
    candidate = Candidate("Z1", "S1", 10, ("e1",), 0)
    ledger = LedgerView(timestep=0, capacity_total={"S1": 100}, occupancy={"S1": 0},
                        reserved={"S1": 0}, pending=(), occupancy_sigma={"S1": 0.}, occupancy_age_s={"S1": 0.})
    from src.certify.rollout import rollout_joint
    base = rollout_joint(candidate, Future(), ledger, session.world, session.gate.params, graph)
    enforced = session.gate.rollout(candidate, Future(), ledger, session.world, session.gate.params, graph)
    assert base.outcome is Outcome.OK
    assert enforced.outcome is Outcome.POLICY and not enforced.z


@pytest.mark.parametrize("tamper", ["source", "hash", "verdict", "citation"])
def test_t2_record_cannot_bypass_membership_or_semantic_checks(tmp_path, chunk, tamper):
    rules, results, approval = approved_fixture(tmp_path, chunk)
    result = json.loads(results.read_text(encoding="utf-8"))
    if tamper in {"source", "hash"}:
        doc = json.loads(rules.read_text(encoding="utf-8"))
        doc["rules"][0]["evidence"]["source_id" if tamper == "source" else "passage_sha256"] = "fake"
        rules.write_text(json.dumps(doc), encoding="utf-8")
        result["rules_file_sha256"] = hashlib.sha256(rules.read_bytes()).hexdigest()
    else:
        result["records"][0]["semantic"]["outcome" if tamper == "verdict" else "supporting_sentence_ids"] = (
            "PARTIALLY_SUPPORTED" if tamper == "verdict" else [100000])
    results.write_text(json.dumps(result), encoding="utf-8")
    loaded = load_runtime_rules(root=tmp_path, rules_path=rules, tier_results_path=results, approval_path=approval)
    assert loaded.rules == () and loaded.metadata["status"] == "STALE"
