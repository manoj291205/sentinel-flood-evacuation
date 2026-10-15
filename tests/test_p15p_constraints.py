"""Phase 15' acceptance tests (Lead) — tier-verified NDMA constraints. Do not edit; escalate instead."""

from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.milestone("P15P")

TEXT = "Evacuees should not be moved over routes that take longer than forty minutes during flooding."
SPAN = "longer than forty minutes"


def _chunk(text=TEXT, digest=None):
    from src.constraints.claim_support import EvidenceChunk

    return EvidenceChunk("ndma-c1", "ndma-src", "ndma.pdf", 12, text,
                         digest or hashlib.sha256(TEXT.encode("utf-8")).hexdigest())


def _rule(**over):
    rule = {
        "rule_id": "NDMA-T01", "text": "Routes should take at most forty minutes during flooding.",
        "predicate": "MAX_TRAVEL_MINUTES", "params": {"minutes": 40}, "strict_fallback": {"minutes": 5},
        "evidence": {"source_id": "ndma-src", "filename": "ndma.pdf", "page": 12, "chunk_id": "ndma-c1",
                     "passage_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(), "span": SPAN},
        "approved": True, "approved_by": "test", "approved_utc": "2026-10-15T00:00:00Z",
    }
    rule.update(over)
    return rule


def _load(tmp_path, *rules):
    from src.constraints.ndma_rules import load_rules

    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"schema": "ndma-constraints-v1", "rules": list(rules)}), encoding="utf-8")
    return load_rules(path)


def _tier(tmp_path, chunk, **kwargs):
    from src.constraints.tiering import assign_tier

    (rule,) = _load(tmp_path, _rule())
    return assign_tier(rule, lambda r: chunk, **kwargs)


def test_verified_rule_is_t1_with_normal_params(tmp_path):
    from src.constraints.tiering import Tier

    tiered = _tier(tmp_path, _chunk())
    assert tiered.tier is Tier.T1 and dict(tiered.active_params) == {"minutes": 40}


def test_tampered_chunk_drops_to_t0_strict_fallback(tmp_path):
    from src.constraints.tiering import Tier

    tiered = _tier(tmp_path, _chunk(text=TEXT.replace("forty", "fifty")))
    assert tiered.tier is Tier.T0 and "CHUNK_HASH_MISMATCH" in tiered.reasons
    assert dict(tiered.active_params) == {"minutes": 5}


def test_missing_chunk_and_non_verbatim_span_are_t0(tmp_path):
    from src.constraints.tiering import Tier, assign_tier

    assert "CHUNK_MISSING" in _tier(tmp_path, None).reasons
    (rule,) = _load(tmp_path, _rule(evidence={**_rule()["evidence"], "span": "invented span"}))
    tiered = assign_tier(rule, lambda r: _chunk())
    assert tiered.tier is Tier.T0 and "SPAN_NOT_VERBATIM" in tiered.reasons


def test_t2_only_with_useful_verdict(tmp_path):
    from src.constraints.claim_support import ClaimSupportResult
    from src.constraints.tiering import Tier

    calls = []

    def semantic(claim, evidence):
        calls.append(claim)
        return ClaimSupportResult(verdict="SUPPORTED", confidence=0.9, supporting_spans=[SPAN],
                                  reason="ok", source_integrity_pass=True)

    useful = _tier(tmp_path, _chunk(), semantic=semantic, semantic_verdict="CLAIM_SUPPORT_VERIFIER_USEFUL")
    assert useful.tier is Tier.T2 and len(calls) == 1
    calls.clear()
    weak = _tier(tmp_path, _chunk(), semantic=semantic,
                 semantic_verdict="CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE")
    assert weak.tier is Tier.T1 and calls == []


def test_loader_skips_unapproved_and_rejects_looser_fallback(tmp_path):
    assert _load(tmp_path, _rule(approved=False)) == ()
    with pytest.raises(ValueError):
        _load(tmp_path, _rule(strict_fallback={"minutes": 90}))


class StubFuture:
    k = 1
    start_timestep = 0
    steps = 20

    def edge_open(self, e, t): return True
    def edge_hazard(self, e, t): return 0.0
    def shelter_severity(self, s, t): return 0.1
    def shelter_status(self, s, t): return "OPEN"
    def walk_ins(self, s, t): return 0
    def travel_normal(self, *key): return 0.0


GRAPH = SimpleNamespace(edges_by_id={"e1": SimpleNamespace(edge_id="e1", u="a", v="b", length_m=1000.0,
                                                          assumed_speed_kph=30.0)})


def _setup():
    from src.certify.ledger_view import LedgerView
    from src.certify.params import CertParams
    from src.certify.rollout import Candidate
    from src.sim.world import get_world_config

    c = Candidate("Z1", "S1", 10, ("e1",), 0)
    ledger = LedgerView(timestep=0, capacity_total={"S1": 100}, occupancy={"S1": 0}, reserved={"S1": 0},
                        pending=(), occupancy_sigma={"S1": 0.0}, occupancy_age_s={"S1": 0.0})
    return c, ledger, get_world_config("v4-medium-dt2-v1"), CertParams()


def test_extra_terms_default_is_unchanged_and_policy_outcome(tmp_path):
    from src.certify.rollout import Outcome, rollout_joint
    from src.constraints.tiering import predicates_for

    c, ledger, world, params = _setup()
    base = rollout_joint(c, StubFuture(), ledger, world, params, GRAPH)
    assert base.outcome is Outcome.OK
    assert rollout_joint(c, StubFuture(), ledger, world, params, GRAPH, extra_terms=()) == base
    ok_terms = predicates_for([_tier(tmp_path, _chunk())])                  # 40 min allowed, trip is 8 min
    assert rollout_joint(c, StubFuture(), ledger, world, params, GRAPH, extra_terms=ok_terms).outcome is Outcome.OK
    strict = predicates_for([_tier(tmp_path, _chunk(text="tampered"))])       # T0: 5 min allowed
    result = rollout_joint(c, StubFuture(), ledger, world, params, GRAPH, extra_terms=strict)
    assert result.outcome is Outcome.POLICY and result.z is False


def test_tampering_changes_the_certified_mask_and_is_audited(tmp_path):
    from src.certify.certifier import certify
    from src.certify.rollout import rollout_joint
    from src.constraints.tiering import predicates_for, tier_audit_records
    from src.sim.events import AuditEventType

    c, ledger, world, params = _setup()
    futures = SimpleNamespace(A_MAX=21, root="0" * 64, future=lambda k: StubFuture())
    good = _tier(tmp_path, _chunk())
    bad = _tier(tmp_path, _chunk(text="tampered"))
    run = lambda tiered: certify([c], futures, ledger, world, params, GRAPH,  # noqa: E731
                                 rollout=functools.partial(rollout_joint, extra_terms=predicates_for([tiered])))
    assert "Z1->S1" in run(good).allowed_keys()
    assert "Z1->S1" not in run(bad).allowed_keys()
    assert tier_audit_records([good], 0) == ()
    (record,) = tier_audit_records([bad], 3)
    assert record.event_type is AuditEventType.RULE_STRICT_FALLBACK and record.timestep == 3
