"""Phase 14B acceptance tests (Lead) — provider, resumable runner, scorer. No network.

Do not edit; escalate instead.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.milestone("P14B")

ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = ROOT / "data/eval_v3/phase14/claim_support_challenge.json"
MANIFEST = ROOT / "data/eval_v3/phase14/claim_support_manifest.json"
LABEL_ONLY_FIELDS = ("construction_label", "construction_reason", "reason_subtype", "synthetic_variant")


def _load_script(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evidence(text="Flood plain zoning restricts construction in areas liable to flooding."):
    from src.constraints.claim_support import EvidenceChunk

    return EvidenceChunk(
        chunk_id="c-1", source_id="ndma", filename="ndma.pdf", page=3, text=text,
        passage_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _reply(verdict="UNSUPPORTED", spans=(), confidence=0.6, reason="Not stated."):
    return json.dumps({"verdict": verdict, "confidence": confidence, "supporting_spans": list(spans), "reason": reason})


def test_payload_and_prompt_contain_only_allowed_fields():
    from src.constraints.claim_support import build_verifier_payload
    from src.constraints.claim_support_gemini import build_prompt, verify_claim_support_gemini

    evidence = _evidence()
    prompts = []

    def client(prompt):
        prompts.append(prompt)
        return _reply("SUPPORTED", ["restricts construction"], 0.9, "Directly stated.")

    result = verify_claim_support_gemini("Zoning limits building in flood areas.", evidence, client=client)
    assert result.verdict.value == "SUPPORTED" and result.source_integrity_pass
    payload = build_verifier_payload("Zoning limits building in flood areas.", evidence)
    assert json.dumps(payload, ensure_ascii=False) in build_prompt(payload) or json.dumps(payload) in build_prompt(payload)
    assert prompts == [build_prompt(payload)]
    for field in LABEL_ONLY_FIELDS:
        assert field not in prompts[0]


def test_invented_span_fails_integrity():
    from src.constraints.claim_support_gemini import verify_claim_support_gemini

    result = verify_claim_support_gemini(
        "claim", _evidence(), client=lambda prompt: _reply("SUPPORTED", ["text that is not there"], 0.8, "x")
    )
    assert result.source_integrity_pass is False


def test_parse_failure_retries_once_then_records_unsupported():
    from src.constraints.claim_support_gemini import verify_claim_support_gemini

    calls = []

    def broken(prompt):
        calls.append(prompt)
        return "not json at all"

    result = verify_claim_support_gemini("claim", _evidence(), client=broken)
    assert len(calls) == 2
    assert result.verdict.value == "UNSUPPORTED"
    assert "PROVIDER_PARSE_FAILURE" in result.reason
    assert result.source_integrity_pass is False


def test_runner_is_resumable_ordered_and_secret_free(tmp_path, monkeypatch):
    from src.constraints.claim_support import label_independent_order

    monkeypatch.setenv("GEMINI_API_KEY", "sk-test-secret-should-never-be-written")
    runner = _load_script("phase14b_run_claim_support")
    ledger = tmp_path / "dispositions.jsonl"
    seen = []

    def fake(prompt):
        seen.append(prompt)
        for field in LABEL_ONLY_FIELDS:
            assert field not in prompt
        return _reply()

    first = runner.run(max_requests=5, client=fake, ledger_path=ledger)
    assert (first["done"], first["total"], first["requests_made"], first["stopped_reason"]) == (5, 135, 5, "MAX_REQUESTS")
    second = runner.run(max_requests=500, client=fake, ledger_path=ledger)
    assert (second["done"], second["requests_made"], second["stopped_reason"]) == (135, 130, "COMPLETE")
    assert len(seen) == 135

    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert len({row["claim_pair_id"] for row in rows}) == 135
    pairs = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    fingerprint = json.loads(MANIFEST.read_text(encoding="utf-8"))["challenge_fingerprint"]
    expected = label_independent_order([p["claim_pair_id"] for p in pairs], fingerprint)
    assert [row["claim_pair_id"] for row in rows] == expected
    text = ledger.read_text(encoding="utf-8")
    assert "sk-test-secret-should-never-be-written" not in text
    for field in LABEL_ONLY_FIELDS:
        assert field not in text
    assert all(row["temperature"] == 0.0 for row in rows)


def test_scorer_refuses_partial_and_applies_frozen_gate(tmp_path):
    runner = _load_script("phase14b_run_claim_support")
    scorer = _load_script("phase14b_score")
    ledger = tmp_path / "dispositions.jsonl"
    runner.run(max_requests=10, client=lambda prompt: _reply(), ledger_path=ledger)
    with pytest.raises(ValueError):
        scorer.score(ledger, tmp_path / "score.json")
    runner.run(max_requests=500, client=lambda prompt: _reply(), ledger_path=ledger)
    result = scorer.score(ledger, tmp_path / "score.json")
    assert result["verdict"] in {"CLAIM_SUPPORT_VERIFIER_USEFUL", "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE"}
    # All-UNSUPPORTED predictions cannot pass the frozen gate.
    assert result["verdict"] == "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE"
    assert json.loads((tmp_path / "score.json").read_text(encoding="utf-8"))["verdict"] == result["verdict"]
