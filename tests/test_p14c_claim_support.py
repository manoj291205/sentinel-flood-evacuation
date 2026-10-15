"""Phase 14C acceptance tests (Lead) — second-provider claim-support evaluation. No network.

Spec: specs/V4_CLAIM_SUPPORT_14C_SPEC.md (pinned by hash below). Do not edit; escalate instead.
"""

from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P14C")

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs/V4_CLAIM_SUPPORT_14C_SPEC.md"
SPEC_SHA256 = "5675f1880c0a8b0ff73a1f967a52f32cbd0d98a80c9b6797a4e17b996854a43e"
CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
MANIFEST = ROOT / "data/eval_v3/phase14/claim_support_manifest.json"
LABEL_ONLY_FIELDS = ("construction_label", "construction_reason", "reason_subtype", "synthetic_variant")
SECRET = "gsk-test-secret-should-never-be-written"
DAY0 = datetime(2026, 10, 16, 0, 0, tzinfo=timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access in a Phase 14C test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setenv("GROQ_API_KEY", SECRET)


@functools.lru_cache(maxsize=None)
def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses in the script need their module registered
    spec.loader.exec_module(module)
    return module


def _p():
    from src.constraints import claim_support_p14c

    return claim_support_p14c


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


def _evidence(text="Flood plain zoning restricts construction in areas liable to flooding."):
    from src.constraints.claim_support import EvidenceChunk

    return EvidenceChunk(
        chunk_id="c-1", source_id="ndma", filename="ndma.pdf", page=3, text=text,
        passage_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _ok(verdict="UNSUPPORTED", spans=(), confidence=0.6, reason="Not stated.", *, content=None,
        reasoning=None, finish="stop", total_tokens=900, headers=None):
    p = _p()
    message = {"role": "assistant", "content": content if content is not None else json.dumps(
        {"verdict": verdict, "confidence": confidence, "supporting_spans": list(spans), "reason": reason})}
    if reasoning is not None:
        message["reasoning"] = reasoning
    body = {"model": p.MODEL_ID, "system_fingerprint": "fp_test",
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 600, "completion_tokens": total_tokens - 600, "total_tokens": total_tokens}}
    return p.ProviderResponse(status=200, body=body, headers=headers or {})


def _err(status, code="error", headers=None):
    return _p().ProviderResponse(status=status, body={"error": {"code": code, "message": "x"}}, headers=headers or {})


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


# --- protocol ------------------------------------------------------------------------------------

def test_protocol_is_pinned_and_identity_is_separate_from_14b():
    assert hashlib.sha256(SPEC.read_bytes()).hexdigest() == SPEC_SHA256
    p = _p()
    from src.constraints import claim_support_gemini as gemini

    assert (p.EVALUATION_ID, p.PROVIDER_ID, p.MODEL_ID, p.PROMPT_VERSION) == (
        "v3-claim-support-eval-14c-v1", "groq-claim-support-v1", "openai/gpt-oss-120b", "14b-prompt-v1")
    assert p.PROVIDER_ID != gemini.PROVIDER_ID
    assert p.API_URL == "https://api.groq.com/openai/v1/chat/completions"
    assert p.REQUEST_SETTINGS == {"temperature": 0.0, "seed": 14, "reasoning_effort": "low",
                                  "include_reasoning": False, "max_completion_tokens": 2048}
    assert p.TEMPERATURE_NOTE == "provider converts 0 to 1e-8"
    source = (ROOT / "src/constraints/claim_support_p14c.py").read_text(encoding="utf-8")
    for forbidden in ("/batches", "/files", "GEMINI_API_KEY", "service_tier"):
        assert forbidden not in source


def test_prompt_is_identical_to_14b_and_request_body_is_exact():
    from src.constraints.claim_support import build_verifier_payload
    from src.constraints import claim_support_gemini as gemini

    p = _p()
    payload = build_verifier_payload("Zoning limits building in flood areas.", _evidence())
    prompt = p.build_prompt(payload)
    assert prompt == gemini.build_prompt(payload)
    body = p.build_request(prompt)
    assert body == {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "claim_support_verdict", "strict": True, "schema": p.RESPONSE_SCHEMA}},
        **p.REQUEST_SETTINGS,
    }
    schema = p.RESPONSE_SCHEMA
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == sorted(schema["properties"]) == ["confidence", "reason", "supporting_spans", "verdict"]
    assert schema["properties"]["verdict"]["enum"] == ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]
    body["model"] = "changed"
    assert p.build_request(prompt)["model"] == "openai/gpt-oss-120b"


# --- provider: same semantic and integrity checks as 14B ---------------------------------------

def test_semantic_and_integrity_checks_match_14b():
    p = _p()
    good = p.verify_claim_support_p14c("Zoning limits building.", _evidence(),
                                       transport=lambda body: _ok("SUPPORTED", ["restricts construction"], 0.9, "Stated."))
    assert good.result.verdict.value == "SUPPORTED" and good.result.source_integrity_pass and good.attempts == 1
    assert (good.response_model, good.system_fingerprint, good.finish_reason) == ("openai/gpt-oss-120b", "fp_test", "stop")
    invented = p.verify_claim_support_p14c("claim", _evidence(),
                                           transport=lambda body: _ok("SUPPORTED", ["text that is not there"], 0.8, "x"))
    assert invented.result.source_integrity_pass is False


@pytest.mark.parametrize("bad", [
    lambda: _ok(content="not json at all"),
    lambda: _ok(content=json.dumps({"verdict": "SUPPORTED", "confidence": 0.5, "supporting_spans": [], "reason": "x", "extra": 1})),
    lambda: _ok(confidence=1.7),
    lambda: _ok(finish="length"),
    lambda: _err(400, "json_validate_failed"),
])
def test_bad_output_retries_once_then_parse_failure(bad):
    p = _p()
    calls = []

    def transport(body):
        calls.append(body)
        return bad()

    outcome = p.verify_claim_support_p14c("claim", _evidence(), transport=transport)
    assert len(calls) == 2 and outcome.attempts == 2
    assert outcome.result.verdict.value == "UNSUPPORTED"
    assert "PROVIDER_PARSE_FAILURE" in outcome.result.reason
    assert outcome.result.source_integrity_pass is False


def test_reasoning_text_is_discarded():
    p = _p()
    outcome = p.verify_claim_support_p14c(
        "claim", _evidence(), transport=lambda body: _ok(reasoning="PRIVATE-REASONING-TOKENS"))
    assert "PRIVATE-REASONING-TOKENS" not in repr(outcome)


@pytest.mark.parametrize("status,code,reason", [
    (500, "error", "PROVIDER_UNAVAILABLE"), (503, "error", "PROVIDER_UNAVAILABLE"),
    (401, "invalid_api_key", "AUTH_ERROR"), (403, "error", "AUTH_ERROR"),
    (404, "model_not_found", "REQUEST_REJECTED"), (400, "invalid_request_error", "REQUEST_REJECTED"),
    (413, "error", "REQUEST_REJECTED"),
])
def test_errors_stop_without_a_disposition(status, code, reason):
    p = _p()
    with pytest.raises(p.ProviderStop) as info:
        p.verify_claim_support_p14c("claim", _evidence(), transport=lambda body: _err(status, code))
    assert info.value.reason == reason and info.value.status == status


def test_429_bounded_wait_then_stop():
    p = _p()
    clock = Clock()
    replies = [_err(429, headers={"retry-after": "2"}), _ok()]
    outcome = p.verify_claim_support_p14c("claim", _evidence(), transport=lambda body: replies.pop(0), sleep=clock.sleep)
    assert outcome.attempts == 2 and clock.sleeps == [2.0]

    clock = Clock()
    calls = []

    def always_429(body):
        calls.append(body)
        return _err(429, headers={"retry-after": "2"})

    with pytest.raises(p.ProviderStop) as info:
        p.verify_claim_support_p14c("claim", _evidence(), transport=always_429, sleep=clock.sleep)
    assert info.value.reason == "RATE_LIMITED" and len(calls) == 3 and clock.sleeps == [2.0, 2.0]

    clock = Clock()
    with pytest.raises(p.ProviderStop) as info:
        p.verify_claim_support_p14c("claim", _evidence(), transport=lambda body: _err(429, headers={"retry-after": "120"}),
                                    sleep=clock.sleep)
    assert info.value.reason == "RATE_LIMITED" and info.value.retry_after == 120.0 and clock.sleeps == []


# --- real transport over a mock HTTP layer -------------------------------------------------------

def test_http_transport_sends_key_only_in_header_and_hides_it_on_errors():
    import httpx

    p = _p()
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok().body, headers={"x-ratelimit-remaining-requests": "999"})

    body = p.build_request("prompt")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        response = p.http_transport(body, client=client)
    assert seen == {"url": p.API_URL, "auth": f"Bearer {SECRET}", "body": body}
    assert SECRET not in json.dumps(seen["body"])
    assert response.status == 200 and response.headers["x-ratelimit-remaining-requests"] == "999"

    def broken(request):
        raise httpx.ConnectError(f"failed with {request.headers.get('authorization')}")

    with httpx.Client(transport=httpx.MockTransport(broken)) as client:
        with pytest.raises(p.ProviderStop) as info:
            p.http_transport(body, client=client)
    assert info.value.reason == "NETWORK_ERROR"
    assert SECRET not in str(info.value) and SECRET not in repr(info.value.args)


def test_http_transport_requires_env_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(RuntimeError):
        _p().http_transport({"model": "x"})


# --- runner ----------------------------------------------------------------------------------------

def test_runner_is_resumable_ordered_counted_and_secret_free(tmp_path, capsys):
    from src.constraints.claim_support import label_independent_order

    p = _p()
    runner = _load_script("phase14c_run_claim_support")
    clock = Clock()
    bodies = []

    def fake(body):
        bodies.append(body)
        text = json.dumps(body)
        for field in LABEL_ONLY_FIELDS:
            assert field not in text
        assert SECRET not in text
        return _ok(reasoning="PRIVATE-REASONING-TOKENS")

    kwargs = dict(transport=fake, out_dir=tmp_path, budget=_big_budget(runner), zdr_attested=True,
                  clock=clock, sleep=clock.sleep)
    first = runner.run(max_requests=5, **kwargs)
    assert (first["done"], first["total"], first["requests_made"], first["stopped_reason"]) == (5, 135, 5, "MAX_REQUESTS")
    second = runner.run(max_requests=500, **kwargs)
    assert (second["done"], second["requests_made"], second["stopped_reason"]) == (135, 130, "COMPLETE")
    assert len(bodies) == 135

    rows = _rows(tmp_path / "dispositions.jsonl")
    calls = _rows(tmp_path / "calls.jsonl")
    fingerprint = json.loads(MANIFEST.read_text(encoding="utf-8"))["challenge_fingerprint"]
    pairs = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    assert [row["claim_pair_id"] for row in rows] == label_independent_order([x["claim_pair_id"] for x in pairs], fingerprint)
    assert [row["order_index"] for row in rows] == list(range(135))
    assert len(calls) == 135 and [c["call_index"] for c in calls] == list(range(135))
    protocol = hashlib.sha256(SPEC.read_bytes()).hexdigest()
    for row in rows:
        assert row["evaluation_id"] == p.EVALUATION_ID and row["provider_id"] == p.PROVIDER_ID
        assert row["model_id"] == p.MODEL_ID and row["prompt_version"] == p.PROMPT_VERSION
        assert row["temperature_requested"] == 0.0 and row["temperature_note"] == p.TEMPERATURE_NOTE
        assert row["request_settings"] == p.REQUEST_SETTINGS
        assert row["challenge_fingerprint"] == fingerprint and row["protocol_sha256"] == protocol
        assert row["zdr_attested"] is True and row["attempts"] == 1
    output = capsys.readouterr()
    for text in ((tmp_path / "dispositions.jsonl").read_text(encoding="utf-8"),
                 (tmp_path / "calls.jsonl").read_text(encoding="utf-8"), output.out, output.err):
        assert SECRET not in text and "PRIVATE-REASONING-TOKENS" not in text
        for field in LABEL_ONLY_FIELDS:
            assert field not in text


def test_retries_and_errors_count_as_calls_and_stops_write_nothing(tmp_path):
    runner = _load_script("phase14c_run_claim_support")
    clock = Clock()
    replies = [_ok(content="bad"), _ok(), _err(429, headers={"retry-after": "1"}), _ok(), _err(503)]
    result = runner.run(transport=lambda body: replies.pop(0), out_dir=tmp_path, max_requests=50,
                        budget=_big_budget(runner), zdr_attested=True, clock=clock, sleep=clock.sleep)
    assert (result["done"], result["requests_made"], result["stopped_reason"]) == (2, 5, "PROVIDER_UNAVAILABLE")
    assert [row["attempts"] for row in _rows(tmp_path / "dispositions.jsonl")] == [2, 2]
    assert [c["http_status"] for c in _rows(tmp_path / "calls.jsonl")] == [200, 200, 429, 200, 503]

    capped = runner.run(transport=lambda body: _ok(content="bad"), out_dir=tmp_path, max_requests=3,
                        budget=_big_budget(runner), zdr_attested=True, clock=clock, sleep=clock.sleep)
    # pair 3 uses 2 calls; pair 4 gets 1 call, then the cap discards it unwritten
    assert (capped["done"], capped["requests_made"], capped["stopped_reason"]) == (3, 3, "MAX_REQUESTS")


def test_daily_budgets_span_runs_and_reset_next_utc_day(tmp_path):
    runner = _load_script("phase14c_run_claim_support")
    clock = Clock()
    kwargs = dict(transport=lambda body: _ok(), out_dir=tmp_path, zdr_attested=True, clock=clock, sleep=clock.sleep,
                  budget=_big_budget(runner, requests_per_day=7))
    assert runner.run(max_requests=5, **kwargs)["done"] == 5
    second = runner.run(max_requests=50, **kwargs)
    assert (second["done"], second["requests_made"], second["stopped_reason"]) == (7, 2, "DAILY_REQUEST_BUDGET")
    clock.t += 86_400
    assert runner.run(max_requests=3, **kwargs)["done"] == 10

    tokens_dir = tmp_path / "tokens"
    result = runner.run(transport=lambda body: _ok(total_tokens=1000), out_dir=tokens_dir, max_requests=500,
                        zdr_attested=True, clock=clock, sleep=clock.sleep,
                        budget=_big_budget(runner, tokens_per_day=12_000))
    assert result["stopped_reason"] == "DAILY_TOKEN_BUDGET" and 1 <= result["done"] < 12
    assert result["tokens_counted"] <= 12_000

    header_dir = tmp_path / "header"
    replies = iter([_ok(), _ok(), _ok(headers={"x-ratelimit-remaining-requests": "1"})] + [_ok()] * 10)
    result = runner.run(transport=lambda body: next(replies), out_dir=header_dir, max_requests=50, zdr_attested=True,
                        clock=clock, sleep=clock.sleep, budget=_big_budget(runner))
    assert (result["done"], result["stopped_reason"]) == (3, "DAILY_REQUEST_BUDGET")


def test_per_minute_pacing(tmp_path):
    runner = _load_script("phase14c_run_claim_support")
    clock = Clock()
    times = []

    def fake(body):
        times.append(clock.t)
        return _ok()

    result = runner.run(transport=fake, out_dir=tmp_path, max_requests=6, zdr_attested=True, clock=clock,
                        sleep=clock.sleep, budget=_big_budget(runner, requests_per_minute=2))
    assert result["done"] == 6 and clock.sleeps
    for t in times:
        assert sum(t - 60 < other <= t for other in times) <= 2


def test_runner_guards(tmp_path):
    runner = _load_script("phase14c_run_claim_support")
    clock = Clock()
    base = dict(transport=lambda body: _ok(), max_requests=2, budget=_big_budget(runner), clock=clock, sleep=clock.sleep)
    with pytest.raises(ValueError):
        runner.run(out_dir=tmp_path / "a", zdr_attested=False, **base)
    assert not (tmp_path / "a" / "calls.jsonl").exists()
    with pytest.raises(ValueError):
        runner.run(out_dir=ROOT / "data/eval_results/phase14b", zdr_attested=True, **base)
    with pytest.raises(ValueError):
        runner.run(out_dir=ROOT / "data/eval_results/phase14b/sub", zdr_attested=True, **base)

    runner.run(out_dir=tmp_path / "b", zdr_attested=True, **base)
    ledger = tmp_path / "b" / "dispositions.jsonl"
    rows = _rows(ledger)
    rows[1]["provider_id"] = "gemini-claim-support-v1"
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    before = ledger.read_bytes()
    with pytest.raises(ValueError):
        runner.run(out_dir=tmp_path / "b", zdr_attested=True, **base)
    assert ledger.read_bytes() == before


# --- scorer ------------------------------------------------------------------------------------------

def test_scorer_refuses_partial_or_mixed_and_applies_frozen_gate(tmp_path):
    p = _p()
    runner = _load_script("phase14c_run_claim_support")
    scorer = _load_script("phase14c_score")
    clock = Clock()
    kwargs = dict(transport=lambda body: _ok(), out_dir=tmp_path, budget=_big_budget(runner), zdr_attested=True,
                  clock=clock, sleep=clock.sleep)
    ledger, calls, out = tmp_path / "dispositions.jsonl", tmp_path / "calls.jsonl", tmp_path / "score.json"
    runner.run(max_requests=10, **kwargs)
    with pytest.raises(ValueError):
        scorer.score(ledger, out, calls)
    runner.run(max_requests=500, **kwargs)
    with pytest.raises(ValueError):
        scorer.score(ledger, ROOT / "data/eval_results/phase14b/score.json", calls)

    result = scorer.score(ledger, out, calls)
    assert result["verdict"] == "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE"  # all-UNSUPPORTED cannot pass
    stored = json.loads(out.read_text(encoding="utf-8"))
    assert stored["verdict"] == result["verdict"]
    assert (stored["evaluation_id"], stored["provider_id"], stored["model_id"], stored["prompt_version"]) == (
        p.EVALUATION_ID, p.PROVIDER_ID, p.MODEL_ID, p.PROMPT_VERSION)
    assert stored["request_settings"] == p.REQUEST_SETTINGS and stored["temperature_requested"] == 0.0
    assert stored["challenge_fingerprint"] == json.loads(MANIFEST.read_text(encoding="utf-8"))["challenge_fingerprint"]
    assert stored["ledger_sha256"] == hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert stored["claim_pairs"] == 135 and stored["calls_total"] == 135
    assert stored["supported_precision"] == stored["metrics"]["per_class"]["SUPPORTED"]["precision"]
    assert stored["macro_f1"] == stored["metrics"]["macro_f1"]
    assert "not a Phase 14B / Gemini result" in stored["label"]

    rows = _rows(ledger)
    rows[7]["model_id"] = "another-model"
    mixed = tmp_path / "mixed.jsonl"
    mixed.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        scorer.score(mixed, tmp_path / "mixed_score.json", calls)
