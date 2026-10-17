"""P15T2 acceptance tests (Lead) — T2 wiring from the 14D approval record. Do not edit; escalate instead.

Spec: specs/V4_CONSTRAINT_TIERS_SPEC.md, Amendment 2026-10-17. Fake transports only: no test may reach the network.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P15T2")

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "specs" / "approvals" / "t2_semantic_verifier.json"
SCORE_REL = "data/eval_results/phase14d/test/score.json"
TEXT = "Evacuees should not be moved over routes that take longer than forty minutes during flooding."
SPAN = "longer than forty minutes"
RULE_TEXT = "Routes should take at most forty minutes during flooding."
FAKE_KEY = "gsk_FAKE_TEST_KEY_never_sent_0123456789"
MODEL_REASON = "MODEL-REASON-TEXT-must-not-be-stored"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import httpx

    def refuse(*args, **kwargs):
        raise AssertionError("a P15T2 test tried to open a network client")

    monkeypatch.setattr(httpx, "Client", refuse)
    monkeypatch.setattr(httpx, "post", refuse)
    monkeypatch.setattr(httpx, "get", refuse)


def _chunk(text=TEXT):
    from src.constraints.claim_support import EvidenceChunk

    return EvidenceChunk("ndma-c1", "ndma-src", "ndma.pdf", 12, text,
                         hashlib.sha256(TEXT.encode("utf-8")).hexdigest())


def _rule(rule_id="NDMA-T01", **over):
    rule = {
        "rule_id": rule_id, "text": RULE_TEXT,
        "predicate": "MAX_TRAVEL_MINUTES", "params": {"minutes": 40}, "strict_fallback": {"minutes": 5},
        "evidence": {"source_id": "ndma-src", "filename": "ndma.pdf", "page": 12, "chunk_id": "ndma-c1",
                     "passage_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(), "span": SPAN},
        "approved": True, "approved_by": "test", "approved_utc": "2026-10-17T00:00:00Z",
    }
    rule.update(over)
    return rule


def _rules_file(tmp_path, *rules):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"schema": "ndma-constraints-v1", "rules": list(rules or [_rule()])}),
                    encoding="utf-8")
    return path


class FakeTransport:
    def __init__(self, verdict="SUPPORTED", ids=(1,), status=200):
        self.verdict, self.ids, self.status, self.calls = verdict, list(ids), status, []

    def __call__(self, body):
        from src.constraints.claim_support_p14c import ProviderResponse

        self.calls.append(body)
        if self.status != 200:
            return ProviderResponse(status=self.status, body={}, headers={})
        content = json.dumps({"verdict": self.verdict, "confidence": 0.9,
                              "supporting_sentence_ids": self.ids, "reason": MODEL_REASON})
        return ProviderResponse(
            status=200,
            body={"model": "openai/gpt-oss-120b", "system_fingerprint": "fp_test",
                  "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                  "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
            headers={},
        )


def _load(tmp_path, transport, *, approval_path=RECORD, attest=True, env=None, chunk=None, rules=None):
    from src.constraints.t2_wiring import load_tiered_rules

    return load_tiered_rules(
        _rules_file(tmp_path, *(rules or [])), lambda r: chunk or _chunk(), approval_path=approval_path,
        attest_zdr=attest, transport=transport, env={"GROQ_API_KEY": FAKE_KEY} if env is None else env,
        sleep=lambda s: None,
    )


def _tmp_record(tmp_path, *, score_bytes=None, **over):
    """A copy of the real record and score under ``tmp_path`` (the root), with overrides."""
    score = tmp_path / SCORE_REL
    score.parent.mkdir(parents=True, exist_ok=True)
    if score_bytes is None:
        shutil.copyfile(ROOT / SCORE_REL, score)
    else:
        score.write_bytes(score_bytes)
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    for key, value in over.items():
        if value is None:
            record.pop(key, None)
        else:
            record[key] = value
    path = tmp_path / "specs" / "approvals" / "t2_semantic_verifier.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


# --- approval record -------------------------------------------------------------------------------------------

def test_real_approval_record_is_accepted():
    from src.constraints.t2_wiring import load_t2_approval

    approval = load_t2_approval()
    assert approval.enabled and approval.reason == "ACCEPTED"
    assert approval.record_sha256 == hashlib.sha256(RECORD.read_bytes()).hexdigest()
    assert approval.evaluation_id == "v4-claim-support-eval-14d-v1"
    assert approval.provider_id == "groq-claim-support-14d-v1"
    assert approval.prompt_version == "14d-prompt-r0"


@pytest.mark.parametrize("over, reason", [
    ({"score_bytes": (ROOT / SCORE_REL).read_bytes() + b"\n"}, "SCORE_HASH_MISMATCH"),
    ({"verdict": "CLAIM_SUPPORT_VERIFIER_USEFUL"}, "VERDICT_NOT_T2_USEFUL"),
    ({"prompt_sha256": "0" * 64}, "PROMPT_HASH_MISMATCH"),
    ({"request_settings": {"temperature": 0.0, "seed": 14, "reasoning_effort": "low",
                           "include_reasoning": False, "max_completion_tokens": 4096}}, "SETTINGS_MISMATCH"),
    ({"model_id": "openai/gpt-oss-20b"}, "MODEL_MISMATCH"),
    ({"prompt_version": "14d-prompt-r1"}, "PROMPT_VERSION_MISMATCH"),
    ({"score_path": "../outside/score.json"}, "SCORE_PATH_INVALID"),
])
def test_tampered_records_disable_t2_with_reason(tmp_path, over, reason):
    from src.constraints.t2_wiring import load_t2_approval

    approval = load_t2_approval(_tmp_record(tmp_path, **over), root=tmp_path)
    assert not approval.enabled and approval.reason == reason


def test_unmodified_copy_is_accepted_so_the_tamper_tests_mean_something(tmp_path):
    from src.constraints.t2_wiring import load_t2_approval

    assert load_t2_approval(_tmp_record(tmp_path), root=tmp_path).enabled


def test_missing_record_disables_t2(tmp_path):
    from src.constraints.t2_wiring import load_t2_approval

    approval = load_t2_approval(tmp_path / "absent.json", root=tmp_path)
    assert not approval.enabled and approval.reason == "APPROVAL_MISSING"


@pytest.mark.parametrize("style", ["14C", "14B"])
def test_14c_and_14b_style_records_never_enable_t2(tmp_path, style):
    from src.constraints.t2_wiring import load_t2_approval

    old = {
        "14C": {"evaluation_id": "v3-claim-support-eval-14c-v1", "provider_id": "groq-claim-support-v1",
                "prompt_version": "14b-prompt-v1"},
        "14B": {"evaluation_id": "v3-claim-support-eval-14b-v1", "provider_id": "gemini-claim-support-v1",
                "model_id": "gemini-2.5-flash", "prompt_version": "14b-prompt-v1"},
    }[style]
    path = _tmp_record(tmp_path, verdict="CLAIM_SUPPORT_VERIFIER_USEFUL", prompt_sha256=None, **old)
    approval = load_t2_approval(path, root=tmp_path)
    assert not approval.enabled
    assert approval.reason in {"APPROVAL_FIELDS", "VERDICT_NOT_T2_USEFUL"}
    fake = FakeTransport()
    load = _load(tmp_path, fake, approval_path=path)
    assert not load.t2_enabled and fake.calls == []
    assert {t.tier.value for t in load.tiered} == {"T1"}


# --- loader ----------------------------------------------------------------------------------------------------

def test_accepted_record_and_supported_answer_give_t2_with_t1_params(tmp_path):
    fake = FakeTransport("SUPPORTED", ids=(1,))
    load = _load(tmp_path, fake)
    (tiered,) = load.tiered
    assert load.t2_enabled and load.t2_reason == "ENABLED"
    assert tiered.tier.value == "T2" and dict(tiered.active_params) == {"minutes": 40}
    assert len(fake.calls) == 1


@pytest.mark.parametrize("verdict, ids", [("PARTIALLY_SUPPORTED", (1,)), ("UNSUPPORTED", ()), ("SUPPORTED", ())])
def test_anything_but_supported_with_integrity_stays_t1(tmp_path, verdict, ids):
    (tiered,) = _load(tmp_path, FakeTransport(verdict, ids=ids)).tiered
    assert tiered.tier.value == "T1" and dict(tiered.active_params) == {"minutes": 40}


def test_parameters_identical_between_t1_and_t2(tmp_path):
    from src.constraints.tiering import predicates_for

    t2 = _load(tmp_path, FakeTransport("SUPPORTED")).tiered
    t1 = _load(tmp_path, FakeTransport("SUPPORTED"), attest=False).tiered
    assert [t.tier.value for t in t2] == ["T2"] and [t.tier.value for t in t1] == ["T1"]
    assert [dict(t.active_params) for t in t2] == [dict(t.active_params) for t in t1]
    strip = lambda ps: [(p.rule_id, p.predicate, p.limit) for p in ps]  # noqa: E731
    assert strip(predicates_for(t2)) == strip(predicates_for(t1))


@pytest.mark.parametrize("kwargs, reason", [
    ({"attest": False}, "ZDR_NOT_ATTESTED"),
    ({"env": {}}, "API_KEY_MISSING"),
    ({"env": {"GROQ_API_KEY": ""}}, "API_KEY_MISSING"),
])
def test_no_call_without_zdr_attest_or_key(tmp_path, kwargs, reason):
    fake = FakeTransport()
    load = _load(tmp_path, fake, **kwargs)
    assert not load.t2_enabled and load.t2_reason == reason and fake.calls == []
    assert [t.tier.value for t in load.tiered] == ["T1"]
    assert all(r["semantic"] is None and r["semantic_status"] == "NOT_CALLED_T2_DISABLED" for r in load.records)


def test_disabled_approval_makes_no_call(tmp_path):
    fake = FakeTransport()
    path = _tmp_record(tmp_path, prompt_sha256="1" * 64)
    load = _load(tmp_path, fake, approval_path=path)
    assert not load.t2_enabled and load.t2_reason == "PROMPT_HASH_MISMATCH" and fake.calls == []


def test_default_is_offline(tmp_path):
    from src.constraints.t2_wiring import load_tiered_rules

    load = load_tiered_rules(_rules_file(tmp_path), lambda r: _chunk(), env={"GROQ_API_KEY": FAKE_KEY})
    assert not load.t2_enabled and load.t2_reason == "ZDR_NOT_ATTESTED"
    assert [t.tier.value for t in load.tiered] == ["T1"]


def test_provider_stop_leaves_rule_t1_and_is_recorded(tmp_path):
    fake = FakeTransport(status=503)
    load = _load(tmp_path, fake)
    (tiered,), (record,) = load.tiered, load.records
    assert tiered.tier.value == "T1" and dict(tiered.active_params) == {"minutes": 40}
    assert record["semantic_status"] == "PROVIDER_STOP"
    assert record["semantic"]["outcome"] == "PROVIDER_STOP"
    assert record["semantic"]["stop_reason"] == "PROVIDER_UNAVAILABLE" and record["semantic"]["http_status"] == 503
    assert len(fake.calls) == 1


def test_t0_rule_is_not_sent(tmp_path):
    fake = FakeTransport()
    load = _load(tmp_path, fake, chunk=_chunk(text=TEXT.replace("forty", "fifty")))
    (tiered,), (record,) = load.tiered, load.records
    assert tiered.tier.value == "T0" and fake.calls == []
    assert record["semantic_status"] == "NOT_CALLED_T0" and record["semantic"] is None


def test_one_call_per_rule_at_load_and_none_per_dispatch(tmp_path):
    from src.constraints.tiering import predicates_for, rules_digest, tier_audit_records

    fake = FakeTransport()
    rules = [_rule("NDMA-T01"), _rule("NDMA-T02"), _rule("NDMA-T03", approved=False)]
    load = _load(tmp_path, fake, rules=rules)
    assert [t.rule.rule_id for t in load.tiered] == ["NDMA-T01", "NDMA-T02"]
    assert len(fake.calls) == 2
    for tiered in load.tiered:
        assert not any(callable(getattr(tiered, f.name)) for f in dataclasses.fields(tiered))
    for step in range(50):  # stands in for 50 dispatch decisions
        for predicate in predicates_for(load.tiered):
            predicate(None, None, 0, 10.0 + step, (0.1,), None)
        rules_digest(load.tiered)
        tier_audit_records(load.tiered, step)
    assert len(fake.calls) == 2


def test_records_carry_approval_hash_and_call_metadata_but_no_secrets(tmp_path):
    from src.constraints.claim_support_p14d import load_prompt

    load = _load(tmp_path, FakeTransport("SUPPORTED"))
    (record,) = load.records
    assert record["approval_record_sha256"] == hashlib.sha256(RECORD.read_bytes()).hexdigest()
    assert record["evaluation_id"] == "v4-claim-support-eval-14d-v1"
    assert record["prompt_version"] == "14d-prompt-r0"
    assert record["semantic_status"] == "CALLED" and record["tier"] == "T2"
    sem = record["semantic"]
    assert sem["outcome"] == "SUPPORTED" and sem["source_integrity_pass"] is True
    assert sem["supporting_sentence_ids"] == [1] and sem["attempts"] == 1
    assert sem["response_model"] == "openai/gpt-oss-120b" and sem["usage"]["total_tokens"] == 15
    dumped = json.dumps(load.records)
    for forbidden in (FAKE_KEY, MODEL_REASON, load_prompt("14d-prompt-r0")[:60], TEXT, RULE_TEXT):
        assert forbidden not in dumped
