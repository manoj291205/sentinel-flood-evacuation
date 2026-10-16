"""Phase 14D acceptance tests (Lead) — claim-support evaluation for T2, replaces 14C. No network.

Spec: specs/V4_CLAIM_SUPPORT_14D_SPEC.md (pinned by hash below). Do not edit; escalate instead.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import re
import socket
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P14D")

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs/V4_CLAIM_SUPPORT_14D_SPEC.md"
SPEC_SHA256 = "f22f3e33ad260187c550f595b190b2b3b72d4d25b11289bcef938c55b17e9aee"
CHALLENGE_DIR = ROOT / "data/eval_v4/phase14d"
V3_CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
LABEL_ONLY_FIELDS = ("construction_label", "construction_reason", "reason_subtype", "synthetic_variant")
SECRET = "gsk-test-secret-should-never-be-written"
DAY0 = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc).timestamp()
LABELS = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED")
TEST_MIX = {
    "PARTIALLY_SUPPORTED": {"SCOPE_OVERSTATEMENT": 10, "TIMING_ADDITION": 8, "NUMERIC_ADDITION": 7, "ACTOR_MISMATCH": 7,
                            "MODALITY_OVERSTATEMENT": 5, "POPULATION_MISMATCH": 4, "UNSUPPORTED_ADDITION": 3,
                            "CONDITION_ADDITION": 1},
    "UNSUPPORTED": {"CONTRADICTION": 40, "SAME_TOPIC_WRONG_CLAIM": 5},
    "SUPPORTED": {"SUPPORTED_PARAPHRASE": 45},
}
PRACTICE_MIX = {
    "PARTIALLY_SUPPORTED": {"SCOPE_OVERSTATEMENT": 2, "TIMING_ADDITION": 2, "NUMERIC_ADDITION": 2, "ACTOR_MISMATCH": 2,
                            "MODALITY_OVERSTATEMENT": 1, "POPULATION_MISMATCH": 1},
    "UNSUPPORTED": {"CONTRADICTION": 9, "SAME_TOPIC_WRONG_CLAIM": 1},
    "SUPPORTED": {"SUPPORTED_PARAPHRASE": 10},
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access in a Phase 14D test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setenv("GROQ_API_KEY", SECRET)


@functools.lru_cache(maxsize=None)
def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _p():
    from src.constraints import claim_support_p14d

    return claim_support_p14d


def _big_budget(runner, **overrides):
    values = dict(requests_per_minute=100_000, tokens_per_minute=10**12, requests_per_day=100_000, tokens_per_day=10**12)
    values.update(overrides)
    return runner.Budget(**values)


class Clock:
    def __init__(self, t=DAY0 + 3600):
        self.t = t
        self.sleeps = []

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        assert seconds >= 0
        self.sleeps.append(seconds)
        self.t += seconds


TEXT = ("Shelters should be located on high ground. They must have safe drinking water!\n"
        "Is sanitation required? Yes, separate toilets for women are needed.")


def _evidence(text=TEXT):
    from src.constraints.claim_support import EvidenceChunk

    return EvidenceChunk(chunk_id="c-1", source_id="ndma", filename="ndma.pdf", page=3, text=text,
                         passage_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())


def _ok(verdict="UNSUPPORTED", ids=(), confidence=0.6, reason="Not stated.", *, content=None,
        reasoning=None, finish="stop", total_tokens=1400, headers=None):
    p = _p()
    message = {"role": "assistant", "content": content if content is not None else json.dumps(
        {"verdict": verdict, "confidence": confidence, "supporting_sentence_ids": list(ids), "reason": reason})}
    if reasoning is not None:
        message["reasoning"] = reasoning
    body = {"model": p.MODEL_ID, "system_fingerprint": "fp_test",
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 900, "completion_tokens": total_tokens - 900, "total_tokens": total_tokens}}
    return p.ProviderResponse(status=200, body=body, headers=headers or {})


def _err(status, code="error", headers=None):
    return _p().ProviderResponse(status=status, body={"error": {"code": code, "message": "x"}}, headers=headers or {})


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _challenge(name):
    return json.loads((CHALLENGE_DIR / f"challenge_{name}.json").read_text(encoding="utf-8"))


def _manifest():
    return json.loads((CHALLENGE_DIR / "manifest.json").read_text(encoding="utf-8"))


def _freeze(tmp_path, version="14d-prompt-r0", sha=None):
    path = tmp_path / "freeze.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"evaluation_id": _p().EVALUATION_ID, "prompt_version": version,
                                "prompt_sha256": sha or _p().prompt_sha256(version), "practice_rounds": [],
                                "frozen_by_opus_utc": "2026-10-20T00:00:00Z"}), encoding="utf-8")
    return path


# --- protocol ------------------------------------------------------------------------------------

def test_protocol_is_pinned_and_identity_replaces_14c():
    assert hashlib.sha256(SPEC.read_bytes()).hexdigest() == SPEC_SHA256
    p = _p()
    from src.constraints import claim_support_p14c as c

    assert (p.EVALUATION_ID, p.PROVIDER_ID, p.MODEL_ID) == (
        "v4-claim-support-eval-14d-v1", "groq-claim-support-14d-v1", "openai/gpt-oss-120b")
    assert p.EVALUATION_ID != c.EVALUATION_ID and p.PROVIDER_ID != c.PROVIDER_ID
    assert p.API_URL == "https://api.groq.com/openai/v1/chat/completions"
    assert p.REQUEST_SETTINGS == {"temperature": 0.0, "seed": 14, "reasoning_effort": "medium",
                                  "include_reasoning": False, "max_completion_tokens": 4096}
    assert p.TEMPERATURE_NOTE == "provider converts 0 to 1e-8"
    assert p.PROMPT_VERSIONS == ("14d-prompt-r0", "14d-prompt-r1")
    source = (ROOT / "src/constraints/claim_support_p14d.py").read_text(encoding="utf-8")
    for forbidden in ("/batches", "/files", "GEMINI_API_KEY", "service_tier"):
        assert forbidden not in source


def test_prompt_r0_is_byte_identical_to_spec():
    spec = SPEC.read_text(encoding="utf-8")
    block = re.search(r"<!-- BEGIN 14d-prompt-r0 -->\n(.*?)<!-- END 14d-prompt-r0 -->", spec, re.S).group(1)
    p = _p()
    assert (p.PROMPT_DIR / "14d-prompt-r0.txt").read_bytes() == block.encode("utf-8")
    assert p.load_prompt("14d-prompt-r0") == block
    assert p.prompt_sha256("14d-prompt-r0") == hashlib.sha256(block.encode("utf-8")).hexdigest()
    with pytest.raises(ValueError):
        p.load_prompt("14d-prompt-r2")


def test_sentences_are_verbatim_and_payload_has_only_claim_evidence_provenance():
    p = _p()
    sentences = p.split_sentences(TEXT)
    assert sentences == ["Shelters should be located on high ground.", "They must have safe drinking water!",
                         "Is sanitation required?", "Yes, separate toilets for women are needed."]
    assert all(s in TEXT for s in sentences)
    payload = p.build_payload("Shelters go on high ground.", _evidence())
    assert set(payload) == {"claim", "evidence_sentences", "source_provenance"}
    assert payload["evidence_sentences"] == [{"id": i, "text": s} for i, s in enumerate(sentences, 1)]
    assert payload["source_provenance"]["passage_sha256"] == _evidence().passage_sha256
    prompt = p.build_prompt(payload, "14d-prompt-r0")
    assert prompt == p.load_prompt("14d-prompt-r0") + json.dumps(payload, ensure_ascii=False)


def test_request_body_and_strict_schema_are_exact():
    p = _p()
    body = p.build_request("prompt")
    assert body == {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": "prompt"}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "claim_support_verdict_14d", "strict": True, "schema": p.RESPONSE_SCHEMA}},
        **p.REQUEST_SETTINGS,
    }
    schema = p.RESPONSE_SCHEMA
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == sorted(schema["properties"]) == [
        "confidence", "reason", "supporting_sentence_ids", "verdict"]
    assert schema["properties"]["supporting_sentence_ids"] == {"type": "array", "items": {"type": "integer"}}
    assert schema["properties"]["verdict"]["enum"] == list(LABELS)
    body["model"] = "changed"
    assert p.build_request("prompt")["model"] == "openai/gpt-oss-120b"


# --- provider ------------------------------------------------------------------------------------

def _verify(reply, **kwargs):
    return _p().verify_claim_support_p14d("claim", _evidence(), prompt_version="14d-prompt-r0",
                                          transport=reply if callable(reply) else (lambda body: reply), **kwargs)


def test_sentence_ids_become_verbatim_spans():
    good = _verify(_ok("SUPPORTED", [2, 1], 0.9, "Stated."))
    assert good.result.verdict.value == "SUPPORTED" and good.result.source_integrity_pass and good.attempts == 1
    assert good.result.supporting_spans == ["They must have safe drinking water!", "Shelters should be located on high ground."]
    assert good.supporting_sentence_ids == (2, 1)
    assert (good.response_model, good.system_fingerprint, good.finish_reason) == ("openai/gpt-oss-120b", "fp_test", "stop")
    no_ids = _verify(_ok("PARTIALLY_SUPPORTED", [], 0.7, "Part."))
    assert no_ids.result.source_integrity_pass is False
    unsupported = _verify(_ok("UNSUPPORTED", [], 0.7, "No."))
    assert unsupported.result.verdict.value == "UNSUPPORTED"


@pytest.mark.parametrize("bad", [
    lambda: _ok(content="not json at all"),
    lambda: _ok(content=json.dumps({"verdict": "SUPPORTED", "confidence": 0.5, "supporting_sentence_ids": [1],
                                    "reason": "x", "extra": 1})),
    lambda: _ok(content=json.dumps({"verdict": "SUPPORTED", "confidence": 0.5, "supporting_spans": ["x"], "reason": "x"})),
    lambda: _ok("SUPPORTED", [0]),
    lambda: _ok("SUPPORTED", [5]),
    lambda: _ok("SUPPORTED", [1, 1]),
    lambda: _ok("SUPPORTED", [True]),
    lambda: _ok(content=json.dumps({"verdict": "SUPPORTED", "confidence": 0.5, "supporting_sentence_ids": ["1"], "reason": "x"})),
    lambda: _ok(confidence=1.7),
    lambda: _ok(content=json.dumps({"verdict": "MAYBE", "confidence": 0.5, "supporting_sentence_ids": [], "reason": "x"})),
    lambda: _ok(finish="length"),
    lambda: _err(400, "json_validate_failed"),
])
def test_bad_output_retries_once_then_parse_failure(bad):
    calls = []

    def transport(body):
        calls.append(body)
        return bad()

    outcome = _verify(transport)
    assert len(calls) == 2 and outcome.attempts == 2
    assert outcome.result.verdict.value == "UNSUPPORTED" and "PROVIDER_PARSE_FAILURE" in outcome.result.reason
    assert outcome.result.source_integrity_pass is False and outcome.supporting_sentence_ids == ()


def test_reasoning_text_is_discarded():
    outcome = _verify(_ok(reasoning="PRIVATE-REASONING-TOKENS"))
    assert "PRIVATE-REASONING-TOKENS" not in repr(outcome)


@pytest.mark.parametrize("status,code,reason", [
    (500, "error", "PROVIDER_UNAVAILABLE"), (529, "error", "PROVIDER_UNAVAILABLE"),
    (401, "invalid_api_key", "AUTH_ERROR"), (403, "error", "AUTH_ERROR"),
    (404, "model_not_found", "REQUEST_REJECTED"), (400, "invalid_request_error", "REQUEST_REJECTED"),
    (301, "error", "REQUEST_REJECTED"),
])
def test_errors_stop_without_a_disposition(status, code, reason):
    p = _p()
    with pytest.raises(p.ProviderStop) as info:
        _verify(_err(status, code))
    assert info.value.reason == reason and info.value.status == status


def test_429_bounded_wait_then_stop():
    p = _p()
    clock = Clock()
    replies = [_err(429, headers={"retry-after": "2"}), _ok()]
    assert _verify(lambda body: replies.pop(0), sleep=clock.sleep).attempts == 2 and clock.sleeps == [2.0]
    clock = Clock()
    with pytest.raises(p.ProviderStop) as info:
        _verify(lambda body: _err(429, headers={"retry-after": "2"}), sleep=clock.sleep)
    assert info.value.reason == "RATE_LIMITED" and clock.sleeps == [2.0, 2.0]


def test_transport_is_the_14c_transport():
    p = _p()
    from src.constraints import claim_support_p14c as c

    assert p.http_transport is c.http_transport
    assert p.ProviderResponse is c.ProviderResponse and p.ProviderStop is c.ProviderStop


# --- runner ----------------------------------------------------------------------------------------

def test_runner_is_resumable_ordered_counted_and_secret_free(tmp_path, capsys):
    from src.constraints.claim_support import label_independent_order

    p = _p()
    runner = _load_script("phase14d_run_claim_support")
    clock = Clock()
    bodies = []

    def fake(body):
        bodies.append(body)
        text = json.dumps(body)
        for field in LABEL_ONLY_FIELDS:
            assert field not in text
        assert SECRET not in text and "evidence_sentences" in text
        return _ok(reasoning="PRIVATE-REASONING-TOKENS")

    kwargs = dict(transport=fake, challenge_set="practice", out_dir=tmp_path, prompt_version="14d-prompt-r0",
                  budget=_big_budget(runner), zdr_attested=True, clock=clock, sleep=clock.sleep)
    first = runner.run(max_requests=4, **kwargs)
    assert (first["done"], first["total"], first["requests_made"], first["stopped_reason"]) == (4, 30, 4, "MAX_REQUESTS")
    second = runner.run(max_requests=500, **kwargs)
    assert (second["done"], second["requests_made"], second["stopped_reason"]) == (30, 26, "COMPLETE")
    assert len(bodies) == 30

    rows, calls = _rows(tmp_path / "dispositions.jsonl"), _rows(tmp_path / "calls.jsonl")
    fingerprint = _manifest()["sets"]["practice"]["challenge_fingerprint"]
    pairs = _challenge("practice")
    assert [r["claim_pair_id"] for r in rows] == label_independent_order([x["claim_pair_id"] for x in pairs], fingerprint)
    assert [r["order_index"] for r in rows] == list(range(30)) and [c["call_index"] for c in calls] == list(range(30))
    protocol = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    for row in rows:
        assert (row["evaluation_id"], row["provider_id"], row["model_id"]) == (p.EVALUATION_ID, p.PROVIDER_ID, p.MODEL_ID)
        assert row["prompt_version"] == "14d-prompt-r0" and row["prompt_sha256"] == p.prompt_sha256("14d-prompt-r0")
        assert row["request_settings"] == p.REQUEST_SETTINGS and row["temperature_requested"] == 0.0
        assert row["challenge_id"] == "v4-claim-support-challenge-14d-v1" and row["challenge_set"] == "practice"
        assert row["challenge_fingerprint"] == fingerprint and row["protocol_sha256"] == protocol
        assert row["zdr_attested"] is True and row["attempts"] == 1 and row["supporting_sentence_ids"] == []
    output = capsys.readouterr()
    for text in ((tmp_path / "dispositions.jsonl").read_text(encoding="utf-8"),
                 (tmp_path / "calls.jsonl").read_text(encoding="utf-8"), output.out, output.err):
        assert SECRET not in text and "PRIVATE-REASONING-TOKENS" not in text
        for field in LABEL_ONLY_FIELDS:
            assert field not in text


def test_test_set_needs_a_matching_freeze_record(tmp_path):
    runner = _load_script("phase14d_run_claim_support")
    clock = Clock()
    base = dict(transport=lambda body: _ok(), challenge_set="test", max_requests=3, prompt_version="14d-prompt-r0",
                budget=_big_budget(runner), zdr_attested=True, clock=clock, sleep=clock.sleep)
    with pytest.raises(ValueError):
        runner.run(out_dir=tmp_path / "a", **base)
    with pytest.raises(ValueError):
        runner.run(out_dir=tmp_path / "b", freeze_path=_freeze(tmp_path, sha="0" * 64), **base)
    assert not (tmp_path / "a" / "calls.jsonl").exists() and not (tmp_path / "b" / "calls.jsonl").exists()
    result = runner.run(out_dir=tmp_path / "c", freeze_path=_freeze(tmp_path), **base)
    assert (result["done"], result["total"]) == (3, 135)


def test_daily_budget_is_shared_across_practice_and_test(tmp_path):
    runner = _load_script("phase14d_run_claim_support")
    clock = Clock()
    root = tmp_path / "phase14d"
    common = dict(transport=lambda body: _ok(), prompt_version="14d-prompt-r0", zdr_attested=True, clock=clock,
                  sleep=clock.sleep, budget_root=root, budget=_big_budget(runner, requests_per_day=10))
    assert runner.run(challenge_set="practice", out_dir=root / "practice/round1", max_requests=7, **common)["done"] == 7
    test = runner.run(challenge_set="test", out_dir=root / "test", max_requests=50,
                      freeze_path=_freeze(tmp_path), **common)
    assert (test["done"], test["requests_made"], test["stopped_reason"]) == (3, 3, "DAILY_REQUEST_BUDGET")
    clock.t += 86_400
    assert runner.run(challenge_set="test", out_dir=root / "test", max_requests=2, freeze_path=_freeze(tmp_path),
                      **common)["done"] == 5


def test_retries_and_stops_count_as_calls_and_write_nothing(tmp_path):
    runner = _load_script("phase14d_run_claim_support")
    clock = Clock()
    replies = [_ok(content="bad"), _ok(), _err(429, headers={"retry-after": "1"}), _ok(), _err(503)]
    result = runner.run(transport=lambda body: replies.pop(0), challenge_set="practice", out_dir=tmp_path,
                        max_requests=50, prompt_version="14d-prompt-r0", budget=_big_budget(runner),
                        zdr_attested=True, clock=clock, sleep=clock.sleep)
    assert (result["done"], result["requests_made"], result["stopped_reason"]) == (2, 5, "PROVIDER_UNAVAILABLE")
    assert [r["attempts"] for r in _rows(tmp_path / "dispositions.jsonl")] == [2, 2]
    assert [c["http_status"] for c in _rows(tmp_path / "calls.jsonl")] == [200, 200, 429, 200, 503]


def test_runner_guards(tmp_path):
    runner = _load_script("phase14d_run_claim_support")
    clock = Clock()
    base = dict(transport=lambda body: _ok(), max_requests=2, budget=_big_budget(runner), clock=clock,
                sleep=clock.sleep, prompt_version="14d-prompt-r0")
    with pytest.raises(ValueError):
        runner.run(challenge_set="practice", out_dir=tmp_path / "a", zdr_attested=False, **base)
    with pytest.raises(ValueError):
        runner.run(challenge_set="dev", out_dir=tmp_path / "a", zdr_attested=True, **base)
    with pytest.raises(ValueError):
        runner.run(challenge_set="practice", out_dir=tmp_path / "a", zdr_attested=True,
                   **{**base, "prompt_version": "14d-prompt-r9"})
    for folder in ("phase14b", "phase14c", "phase14c/sub"):
        with pytest.raises(ValueError):
            runner.run(challenge_set="practice", out_dir=ROOT / "data/eval_results" / folder, zdr_attested=True, **base)
    assert not (tmp_path / "a" / "calls.jsonl").exists()

    runner.run(challenge_set="practice", out_dir=tmp_path / "b", zdr_attested=True, **base)
    ledger = tmp_path / "b" / "dispositions.jsonl"
    rows = _rows(ledger)
    rows[1]["prompt_sha256"] = "0" * 64
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    before = ledger.read_bytes()
    with pytest.raises(ValueError):
        runner.run(challenge_set="practice", out_dir=tmp_path / "b", zdr_attested=True, **base)
    assert ledger.read_bytes() == before


# --- scorer ------------------------------------------------------------------------------------------

def _scored_run(tmp_path, answer):
    """Run the full test set with a fake transport that answers from the construction label."""
    runner = _load_script("phase14d_run_claim_support")
    labels = {}
    for pair in _challenge("test"):
        labels[pair["claim"]] = pair["construction_label"]

    def fake(body):
        claim = json.loads(body["messages"][0]["content"].rsplit("Input:\n", 1)[1])["claim"]
        verdict, ids = answer(labels[claim])
        return _ok(verdict, ids)

    clock = Clock()
    out = tmp_path / "run"
    runner.run(transport=fake, challenge_set="test", out_dir=out, max_requests=500, prompt_version="14d-prompt-r0",
               freeze_path=_freeze(tmp_path), budget=_big_budget(runner), zdr_attested=True, clock=clock,
               sleep=clock.sleep)
    return out


def test_scorer_applies_t2_gate_and_reports_v3_gate(tmp_path):
    p = _p()
    scorer = _load_script("phase14d_score")
    out = _scored_run(tmp_path, lambda label: (label, [1] if label != "UNSUPPORTED" else []))
    result = scorer.score(out / "dispositions.jsonl", out / "score.json", out / "calls.jsonl")
    assert result["verdict"] == result["t2_verdict"] == "T2_VERIFIER_USEFUL"
    assert result["v3_verdict"] == "CLAIM_SUPPORT_VERIFIER_USEFUL"
    assert result["t2_metrics"]["t2_precision"] == 1.0 and result["t2_metrics"]["t2_recall"] == 1.0
    assert result["t2_metrics"]["t2_positive_count"] == 45 and result["claim_pairs"] == 135
    stored = json.loads((out / "score.json").read_text(encoding="utf-8"))
    assert stored == result
    assert (stored["evaluation_id"], stored["provider_id"], stored["model_id"]) == (p.EVALUATION_ID, p.PROVIDER_ID, p.MODEL_ID)
    assert stored["prompt_sha256"] == p.prompt_sha256("14d-prompt-r0") and stored["challenge_set"] == "test"
    assert stored["ledger_sha256"] == hashlib.sha256((out / "dispositions.jsonl").read_bytes()).hexdigest()
    assert stored["calls_total"] == 135 and "replaces 14C" in stored["label"]

    # T2 ignores partial-vs-unsupported confusion: the 14C failure pattern passes T2 but fails V3.
    out2 = _scored_run(tmp_path / "x", lambda label: ("SUPPORTED", [1]) if label == "SUPPORTED" else ("UNSUPPORTED", []))
    mixed = scorer.score(out2 / "dispositions.jsonl", out2 / "score.json", out2 / "calls.jsonl")
    assert mixed["t2_verdict"] == "T2_VERIFIER_USEFUL" and mixed["v3_verdict"] == "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE"

    # Low recall fails T2.
    out3 = _scored_run(tmp_path / "y", lambda label: ("UNSUPPORTED", []))
    low = scorer.score(out3 / "dispositions.jsonl", out3 / "score.json", out3 / "calls.jsonl")
    assert low["t2_verdict"] == "T2_VERIFIER_NOT_YET_RELIABLE" and low["t2_conditions"]["t2_recall"] is False


def test_t2_metric_definitions():
    scorer = _load_script("phase14d_score")
    expected = ["SUPPORTED"] * 45 + ["PARTIALLY_SUPPORTED"] * 45 + ["UNSUPPORTED"] * 45
    predicted = (["SUPPORTED"] * 40 + ["UNSUPPORTED"] * 5) + (["SUPPORTED"] * 3 + ["UNSUPPORTED"] * 42) + ["UNSUPPORTED"] * 45
    integrity = [True] * 39 + [False] + [True] * 95
    metrics, verdict, conditions = scorer.t2_gate(expected, predicted, integrity)
    assert metrics["t2_positive_count"] == 42                      # 39 + 3 (one SUPPORTED failed integrity)
    assert metrics["t2_precision"] == pytest.approx(39 / 42)
    assert metrics["t2_unsafe_acceptance"] == pytest.approx(3 / 90)
    assert metrics["t2_recall"] == pytest.approx(39 / 45)
    assert metrics["supported_integrity_failure"] == pytest.approx(1 / 43)
    assert conditions == {"t2_precision": False, "t2_unsafe_acceptance": True, "t2_recall": True,
                          "supported_integrity_failure": False}
    assert verdict == "T2_VERIFIER_NOT_YET_RELIABLE"


def test_scorer_refuses_partial_mixed_and_old_paths(tmp_path):
    runner = _load_script("phase14d_run_claim_support")
    scorer = _load_script("phase14d_score")
    clock = Clock()
    kwargs = dict(transport=lambda body: _ok(), challenge_set="test", out_dir=tmp_path, prompt_version="14d-prompt-r0",
                  freeze_path=_freeze(tmp_path), budget=_big_budget(runner), zdr_attested=True, clock=clock,
                  sleep=clock.sleep)
    ledger, calls = tmp_path / "dispositions.jsonl", tmp_path / "calls.jsonl"
    runner.run(max_requests=10, **kwargs)
    with pytest.raises(ValueError):
        scorer.score(ledger, tmp_path / "score.json", calls)
    runner.run(max_requests=500, **kwargs)
    for folder in ("phase14b", "phase14c"):
        with pytest.raises(ValueError):
            scorer.score(ledger, ROOT / "data/eval_results" / folder / "score.json", calls)
    rows = _rows(ledger)
    rows[7]["model_id"] = "another-model"
    mixed = tmp_path / "mixed.jsonl"
    mixed.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        scorer.score(mixed, tmp_path / "mixed_score.json", calls)
    complete = scorer.score(ledger, tmp_path / "score.json", calls)
    assert complete["challenge_set"] == "test"


# --- challenge sets (built by Lead) --------------------------------------------------------------

def test_challenge_counts_mix_and_schema():
    manifest = _manifest()
    assert manifest["challenge_id"] == "v4-claim-support-challenge-14d-v1"
    assert manifest["corpus_fingerprint"] == "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"
    fields = manifest["canonical_fields_in_order"]
    for name, count, mix in (("test", 45, TEST_MIX), ("practice", 10, PRACTICE_MIX)):
        rows = _challenge(name)
        assert len(rows) == 3 * count and all(list(row) == fields for row in rows)
        assert Counter(r["construction_label"] for r in rows) == {label: count for label in LABELS}
        for label, subtypes in mix.items():
            assert Counter(r["reason_subtype"] for r in rows if r["construction_label"] == label) == subtypes
        prefix = "T" if name == "test" else "P"
        for row in rows:
            assert re.fullmatch(rf"{prefix}\d\d-C[123]", row["claim_pair_id"])
            assert row["construction_label"] == LABELS[int(row["claim_pair_id"][-1]) - 1]
            assert row["challenge_set"] == name and row["synthetic_variant"] is True
            assert row["not_authoritative_policy"] is True and row["benchmark_version"] == manifest["challenge_id"]
            assert row["construction_protocol_version"] == "v4-claim-support-construction-14d-v1"
        by_chunk = Counter(r["chunk_id"] for r in rows)
        assert len(by_chunk) == count and set(by_chunk.values()) == {3}
        assert manifest["sets"][name]["claim_pairs"] == 3 * count
        assert sorted(manifest["sets"][name]["chunk_ids"]) == sorted(by_chunk)


def test_challenge_fingerprints_provenance_and_disjointness():
    from src.constraints.claim_support import get_chunk_by_id
    from src.rag.ingest import prepare_corpus

    manifest = _manifest()
    fields = manifest["canonical_fields_in_order"]
    v3 = json.loads(V3_CHALLENGE.read_text(encoding="utf-8"))
    v3_pages = {(r["source_id"], r["page"]) for r in v3}
    assert {tuple(x) for x in manifest["excluded_v3_pages"]} == v3_pages
    prepared = prepare_corpus()
    chunk_sets = {}
    for name in ("test", "practice"):
        rows = _challenge(name)
        lines = [json.dumps([r[f] for f in fields], ensure_ascii=False, separators=(",", ":"))
                 for r in sorted(rows, key=lambda r: r["claim_pair_id"])]
        digest = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
        assert digest == manifest["sets"][name]["challenge_fingerprint"]
        for row in rows:
            assert (row["source_id"], row["page"]) not in v3_pages
            chunk = get_chunk_by_id(row["chunk_id"], prepared, source_id=row["source_id"], filename=row["filename"],
                                    page=row["page"], passage_sha256=row["passage_sha256"])
            assert len(chunk.text) >= 400
        chunk_sets[name] = {r["chunk_id"] for r in rows}
    assert not chunk_sets["test"] & chunk_sets["practice"]


def test_selection_log_explains_every_walked_chunk():
    manifest = _manifest()
    log = json.loads((CHALLENGE_DIR / "selection_log.json").read_text(encoding="utf-8"))
    entries = log["walked"]
    keys = [hashlib.sha256(("14d-v1:" + e["chunk_id"]).encode("utf-8")).hexdigest() for e in entries]
    assert keys == sorted(keys)
    decisions = [e["decision"] for e in entries]
    assert set(decisions) <= {"ACCEPTED_TEST", "ACCEPTED_PRACTICE", "SKIPPED"}
    assert decisions.count("ACCEPTED_TEST") == 45 and decisions.count("ACCEPTED_PRACTICE") == 10
    assert decisions[-1] == "ACCEPTED_PRACTICE"
    accepted = [e["chunk_id"] for e in entries if e["decision"] != "SKIPPED"]
    assert accepted[:45] == [e["chunk_id"] for e in entries if e["decision"] == "ACCEPTED_TEST"]
    assert set(accepted[:45]) == set(manifest["sets"]["test"]["chunk_ids"])
    assert set(accepted[45:]) == set(manifest["sets"]["practice"]["chunk_ids"])
    for e in entries:
        if e["decision"] == "SKIPPED":
            assert e["reason"] in {"NON_SUBSTANTIVE", "GARBLED_TEXT", "NEAR_DUPLICATE"}
