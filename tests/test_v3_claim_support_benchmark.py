"""Phase 14A claim-support challenge and frozen-interface tests."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase14a_prepare_claim_support import (
    BENCHMARK_VERSION, CANONICAL_FIELDS, CHALLENGE_PATH, CLAIMS,
    CONSTRUCTION_PROTOCOL_VERSION, CORPUS_FINGERPRINT, LABELS_PATH, MANIFEST_PATH,
    QUESTIONS_PATH, REASON_SUBTYPES, REVIEW_PATH, SOURCE_BENCHMARK_VERSION,
    SOURCE_LABEL_FINGERPRINT, SPOTCHECK_PATH, build_artifacts, challenge_fingerprint,
    duplicate_audit, read_csv,
)
from src.constraints.claim_support import (
    QUOTE_INTEGRITY_PROTOCOL_VERSION, SUPPORT_PROTOCOL_VERSION, ClaimSupportResult,
    ClaimSupportVerdict, EvidenceChunk, build_verifier_payload, classification_metrics,
    finalize_semantic_result, get_chunk_by_id, label_independent_order, safe_to_cite,
    span_integrity_failure_rate, usefulness_gate, validate_supporting_spans,
    verify_claim_support, verify_evidence_integrity,
)
from src.rag.ingest import PreparedCorpus, prepare_corpus
from src.rag.retrieve import (
    BM25_B, BM25_EPSILON, BM25_K1, HYBRID_CANDIDATE_K,
    RETRIEVAL_CONFIG_VERSION, RRF_K,
)

PHASE13_RESULT = ROOT / "data/eval_v3/phase13/phase13b_retrieval_results_v2.json"


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return json.loads(CHALLENGE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prepared() -> PreparedCorpus:
    return prepare_corpus()


def test_benchmark_identity_is_exact(manifest):
    assert manifest["benchmark_version"] == BENCHMARK_VERSION == "v3-claim-support-challenge-v1"
    assert manifest["construction_protocol_version"] == CONSTRUCTION_PROTOCOL_VERSION == "v3-claim-support-construction-v1"
    assert manifest["source_benchmark_version"] == SOURCE_BENCHMARK_VERSION == "v3-retrieval-benchmark-ai-assisted-v2"
    assert manifest["source_label_fingerprint"] == SOURCE_LABEL_FINGERPRINT
    assert manifest["corpus_fingerprint"] == CORPUS_FINGERPRINT


def test_exact_structure_and_balance(records, manifest):
    assert manifest["questions"] == 45
    assert manifest["base_evidence_passages"] == 45
    assert manifest["claim_pairs"] == len(records) == 135
    assert Counter(row["construction_label"] for row in records) == {
        "SUPPORTED": 45, "PARTIALLY_SUPPORTED": 45, "UNSUPPORTED": 45,
    }
    assert len({row["question_id"] for row in records}) == 45


def test_exactly_three_unique_claims_and_same_evidence_per_question(records):
    grouped = defaultdict(list)
    for row in records:
        grouped[row["question_id"]].append(row)
    assert set(map(len, grouped.values())) == {3}
    for rows in grouped.values():
        assert {row["construction_label"] for row in rows} == set(ClaimSupportVerdict)
        assert len({row["claim"] for row in rows}) == 3
        evidence = {(row["chunk_id"], row["source_id"], row["filename"], row["page"], row["passage_sha256"]) for row in rows}
        assert len(evidence) == 1


def test_selected_chunk_is_lexicographically_first_frozen_grade_two(records):
    labels = read_csv(LABELS_PATH)
    expected = {
        question_id: min(row["chunk_id"] for row in labels if row["question_id"] == question_id and row["ai_relevance_grade"] == "2")
        for question_id in {row["question_id"] for row in records}
    }
    actual = {row["question_id"]: row["chunk_id"] for row in records}
    assert actual == expected


def test_every_selected_evidence_was_grade_two(records):
    direct = {(row["question_id"], row["chunk_id"]) for row in read_csv(LABELS_PATH) if row["ai_relevance_grade"] == "2"}
    assert {(row["question_id"], row["chunk_id"]) for row in records} <= direct


def test_all_chunks_resolve_and_provenance_hashes_match(records, prepared):
    for row in records[::3]:
        chunk = get_chunk_by_id(row["chunk_id"], prepared, source_id=row["source_id"], filename=row["filename"], page=row["page"], passage_sha256=row["passage_sha256"])
        assert verify_evidence_integrity(chunk)


def test_get_chunk_requires_exactly_one_match(prepared):
    with pytest.raises(ValueError, match="exactly once"):
        get_chunk_by_id("missing", prepared)
    duplicate = PreparedCorpus(prepared.documents + [prepared.documents[0]], prepared.metadatas + [prepared.metadatas[0]], prepared.ids + [prepared.ids[0]], prepared.source_chunk_counts, prepared.page_count, prepared.text_page_count)
    with pytest.raises(ValueError, match="exactly once"):
        get_chunk_by_id(prepared.ids[0], duplicate)


@pytest.mark.parametrize("field,value", [("source_id", "wrong"), ("filename", "wrong.pdf"), ("page", 999), ("passage_sha256", "0" * 64)])
def test_get_chunk_rejects_provenance_mismatch(prepared, field, value):
    with pytest.raises(ValueError, match="mismatch"):
        get_chunk_by_id(prepared.ids[0], prepared, **{field: value})


def test_records_have_exact_schema_and_no_authoritative_text(records):
    banned = {"text", "original_text", "excerpt", "passage_text", "evidence"}
    assert all(tuple(row) == CANONICAL_FIELDS for row in records)
    assert all(not (set(row) & banned) for row in records)


def test_no_retrieval_or_relevance_metadata_leaks_into_records(records):
    banned_fragments = ("retriever", "rank", "dense", "bm25", "hybrid", "relevance_grade")
    assert all(not any(fragment in key.casefold() for fragment in banned_fragments) for row in records for key in row)


def test_claims_flags_labels_and_vocab_are_valid(records):
    assert all(str(row["claim"]).strip() for row in records)
    assert all(row["synthetic_variant"] is True and row["not_authoritative_policy"] is True for row in records)
    assert {row["construction_label"] for row in records} == set(ClaimSupportVerdict)
    assert {row["reason_subtype"] for row in records} <= set(REASON_SUBTYPES)
    assert all(row["reason_subtype"] == "SUPPORTED_PARAPHRASE" for row in records if row["construction_label"] == "SUPPORTED")


def test_claim_construction_map_covers_frozen_questions():
    question_ids = {row["question_id"] for row in read_csv(QUESTIONS_PATH)}
    assert len(question_ids) == 45 and set(CLAIMS) == question_ids


def test_fingerprint_reproduces_and_changes_with_claim(records, manifest):
    assert challenge_fingerprint(records) == manifest["challenge_fingerprint"]
    changed = [dict(row) for row in records]
    changed[0]["claim"] += " changed"
    assert challenge_fingerprint(changed) != manifest["challenge_fingerprint"]


def test_fingerprint_is_stable_under_record_reordering(records):
    assert challenge_fingerprint(records) == challenge_fingerprint(list(reversed(records)))


def test_evaluation_order_is_deterministic_unique_and_label_independent(records, manifest):
    pair_ids = [row["claim_pair_id"] for row in records]
    expected = label_independent_order(pair_ids, manifest["challenge_fingerprint"])
    assert manifest["evaluation_order"]["claim_pair_ids"] == expected
    assert len(expected) == len(set(expected)) == 135
    label_by_id = {row["claim_pair_id"]: row["construction_label"] for row in records}
    ordered_labels = [label_by_id[pair_id] for pair_id in expected]
    assert any(left != right for left, right in zip(ordered_labels, ordered_labels[1:]))


def test_spotcheck_is_15_balanced_and_not_human_reviewed():
    spot = json.loads(SPOTCHECK_PATH.read_text(encoding="utf-8"))
    assert len(spot["examples"]) == 15
    assert Counter(row["construction_label"] for row in spot["examples"]) == {label: 5 for label in ClaimSupportVerdict}
    assert "not human-reviewed" in spot["purpose"]


def test_audit_marks_negative_claims_and_uses_short_excerpts(records):
    text = REVIEW_PATH.read_text(encoding="utf-8")
    assert text.count("SYNTHETIC CHALLENGE CLAIM — NOT AUTHORITATIVE POLICY") == 90
    assert text.count("CONSTRUCTED PARAPHRASE — NOT AUTHORITATIVE POLICY WORDING") == 45
    assert text.count("> Evidence excerpt:") == 135


def test_duplicate_and_triviality_audit_is_clean(records, prepared):
    texts = dict(zip(prepared.ids, prepared.documents))
    evidence = {row["question_id"]: texts[row["chunk_id"]] for row in records[::3]}
    audit = duplicate_audit(records, evidence)
    assert audit == {"exact_duplicate_claims": 0, "normalized_duplicate_claims": 0, "suspicious_supported_exact_copies": []}


def test_verdict_schema_confidence_and_required_spans():
    result = ClaimSupportResult(ClaimSupportVerdict.SUPPORTED, 0.9, ["span"], "reason", True)
    assert result.support_protocol_version == SUPPORT_PROTOCOL_VERSION
    with pytest.raises(ValueError, match="confidence"):
        replace(result, confidence=1.1)
    with pytest.raises(ValueError, match="require spans"):
        replace(result, supporting_spans=[])
    with pytest.raises(ValueError):
        replace(result, verdict="INVALID")


def test_quote_integrity_baseline_name_and_phase14b_delegation(monkeypatch):
    import src.constraints.claim_support_gemini as provider

    assert QUOTE_INTEGRITY_PROTOCOL_VERSION == "quote-integrity-v1"
    evidence = EvidenceChunk("c", "s", "f", 1, "text", hashlib.sha256(b"text").hexdigest())
    calls = []
    monkeypatch.setattr(provider, "verify_claim_support_gemini", lambda claim, ev: calls.append((claim, ev)) or "result")
    assert verify_claim_support("claim", evidence) == "result"
    assert calls == [("claim", evidence)]


def test_supporting_spans_are_verbatim_and_integrity_cannot_be_overridden():
    evidence = EvidenceChunk("c", "s", "f", 1, "authoritative exact span", hashlib.sha256(b"authoritative exact span").hexdigest())
    assert validate_supporting_spans(evidence, ["exact span"])
    assert not validate_supporting_spans(evidence, ["invented span"])
    result = finalize_semantic_result(evidence=evidence, verdict="SUPPORTED", confidence=0.8, supporting_spans=["invented span"], reason="toy")
    assert result.verdict is ClaimSupportVerdict.SUPPORTED and not result.source_integrity_pass


def test_verifier_payload_has_only_claim_evidence_and_source_provenance():
    evidence = EvidenceChunk("c", "s", "f", 1, "text", hashlib.sha256(b"text").hexdigest())
    payload = build_verifier_payload("claim", evidence)
    assert set(payload) == {"claim", "evidence", "source_provenance"}
    serialized = json.dumps(payload).casefold()
    for forbidden in ("construction_label", "construction_reason", "reason_subtype", "synthetic_variant", "relevance_grade", "retriever", "rank", "expected_verdict"):
        assert forbidden not in serialized


@pytest.mark.parametrize("verdict,expected", [("SUPPORTED", True), ("PARTIALLY_SUPPORTED", False), ("UNSUPPORTED", False)])
def test_safe_to_cite_mapping(verdict, expected):
    assert safe_to_cite(verdict) is expected


def test_toy_metrics_cover_primary_secondary_and_unsafe_acceptance():
    expected = ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "UNSUPPORTED"]
    predicted = ["SUPPORTED", "SUPPORTED", "UNSUPPORTED", "PARTIALLY_SUPPORTED"]
    metrics = classification_metrics(expected, predicted)
    assert metrics["accuracy"] == pytest.approx(0.5)
    assert 0 <= metrics["macro_f1"] <= 1
    assert metrics["per_class"]["SUPPORTED"]["precision"] == pytest.approx(0.5)
    assert metrics["safe_to_cite_precision"] == pytest.approx(0.5)
    assert metrics["safe_to_cite_recall"] == 1.0
    assert metrics["unsafe_citation_acceptance_rate"] == pytest.approx(1 / 3)
    assert sum(sum(row.values()) for row in metrics["confusion_matrix"].values()) == 4


def test_span_failure_rate_toy_fixture():
    results = [
        ClaimSupportResult(ClaimSupportVerdict.SUPPORTED, 1, ["x"], "r", True),
        ClaimSupportResult(ClaimSupportVerdict.UNSUPPORTED, 1, [], "r", False),
    ]
    assert span_integrity_failure_rate(results) == 0.5


@pytest.mark.parametrize("changed", ["macro_f1", "supported_precision", "unsafe_acceptance", "span_integrity_failure"])
def test_usefulness_gate_requires_every_condition(changed):
    passing = {"macro_f1": 0.75, "supported_precision": 0.85, "unsafe_acceptance": 0.15, "span_integrity_failure": 0.05}
    assert usefulness_gate(passing)[0] == "CLAIM_SUPPORT_VERIFIER_USEFUL"
    failing = dict(passing)
    failing[changed] = {"macro_f1": 0.749, "supported_precision": 0.849, "unsafe_acceptance": 0.151, "span_integrity_failure": 0.051}[changed]
    verdict, conditions = usefulness_gate(failing)
    assert verdict == "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE"
    assert conditions[changed] is False


def test_phase14a_records_no_official_performance_result(manifest):
    assert manifest["official_phase14b_metrics_calculated"] is False
    serialized = json.dumps(manifest)
    assert "CLAIM_SUPPORT_VERIFIER_USEFUL" not in serialized
    assert "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE" not in serialized


def test_frozen_phase13_and_retrieval_results_are_unchanged():
    result = json.loads(PHASE13_RESULT.read_text(encoding="utf-8"))
    assert result["principal_comparison"]["final_verdict"] == "HYBRID_SUPPORTED"
    assert result["overall"]["bm25"]["direct_hit_at_5"] == pytest.approx(39 / 45)
    assert RETRIEVAL_CONFIG_VERSION == "v3-retrieval-v1"
    assert (BM25_K1, BM25_B, BM25_EPSILON, RRF_K, HYBRID_CANDIDATE_K) == (1.5, 0.75, 0.25, 60, 20)


def test_frozen_phase13_files_have_expected_hashes():
    expected = {
        QUESTIONS_PATH: "a7367bb093a1fa65aba8c690cdf5001ff74ba860281d379721dbcbb21c822f3f",
        LABELS_PATH: "3bbaf030673b76e573c6f721142ac39f8f8f98a2a5985f55b8c6d1210bfa2129",
        PHASE13_RESULT: "6ad660f67d7d9f23adf4caf469e940cc0cb5a47b8bf4661cf3ae0f90e32226f8",
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_builder_reproduces_committed_artifacts(records, manifest):
    built_records, built_manifest, built_spotcheck, built_review = build_artifacts()
    assert built_records == records
    assert built_manifest == manifest
    assert built_spotcheck == json.loads(SPOTCHECK_PATH.read_text(encoding="utf-8"))
    assert built_review == REVIEW_PATH.read_text(encoding="utf-8")
