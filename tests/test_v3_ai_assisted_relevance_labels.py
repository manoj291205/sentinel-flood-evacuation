"""Phase 13A.2 AI-assisted label freeze and human/retrieval firewalls."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.phase13a2_label_passages import (
    BENCHMARK_VERSION,
    LABEL_FIELDS,
    PROTOCOL_VERSION,
    canonical_label_bytes,
    grade_pair,
    weighted_kappa,
)
from scripts.phase13a2_prepare_blind_payload import ALLOWED_FIELDS, FORBIDDEN_FRAGMENTS
from src.rag.corpus import CORPUS_VERSION
from src.rag.ingest import EMBED_MODEL_NAME
from src.rag.retrieve import (
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    BM25_METHOD_ID,
    DENSE_METHOD_ID,
    EXPECTED_CHUNK_COUNT,
    HYBRID_CANDIDATE_K,
    HYBRID_METHOD_ID,
    RETRIEVAL_CONFIG_VERSION,
    RRF_K,
    TOKENIZER_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
PAYLOAD_PATH = PHASE13 / "ai_labeling_payload.jsonl"
LABEL_PATH = PHASE13 / "ai_assisted_passage_labels.csv"
MANIFEST_PATH = PHASE13 / "ai_assisted_label_manifest.json"
CONSISTENCY_PATH = PHASE13 / "ai_label_consistency.csv"
HUMAN_PATH = PHASE13 / "human_review.csv"
RETAINED_PATH = PHASE13 / "retained_passage_review.csv"
AMENDMENT_PATH = ROOT / "V3_RETRIEVAL_BENCHMARK_AI_AMENDMENT.md"
DOCUMENTATION_PATH = ROOT / "DOCUMENTATION.md"

HUMAN_SHA256 = "11e2d5d7565bbc0eb9b61d711ee55d81da280f1ffe63e67a2eb02127dcda6791"
RETAINED_SHA256 = "042155e9be1174c538d17132da3b9c6fbccce2b97d5a23b8f1aa8b805e119b29"
FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def payload() -> list[dict[str, str]]:
    return [json.loads(line) for line in PAYLOAD_PATH.read_text().splitlines() if line]


@pytest.fixture(scope="module")
def labels() -> list[dict[str, str]]:
    return read_csv(LABEL_PATH)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


@pytest.fixture(scope="module")
def retained() -> list[dict[str, str]]:
    return read_csv(RETAINED_PATH)


def test_ai_benchmark_version_is_exact(manifest):
    assert BENCHMARK_VERSION == manifest["benchmark_version"] == "v3-retrieval-benchmark-ai-assisted-v1"


def test_ai_label_protocol_is_exact(manifest):
    assert PROTOCOL_VERSION == manifest["label_protocol_version"] == "v3-ai-relevance-labeler-v1"


def test_label_set_has_exactly_485_rows(labels, manifest):
    assert len(labels) == manifest["passage_count"] == 485


def test_label_set_has_exactly_45_questions(labels, manifest):
    assert len({row["question_id"] for row in labels}) == manifest["question_count"] == 45


def test_all_retained_question_ids_are_represented(labels, retained):
    assert {row["question_id"] for row in labels} == {row["question_id"] for row in retained}


def test_topic_balance_remains_nine_each(labels):
    questions = {row["question_id"]: row for row in labels}
    assert Counter(row["topic"] for row in questions.values()) == {
        "flood_management": 9,
        "evacuation_movement": 9,
        "temporary_shelters_relief_camps": 9,
        "vulnerable_groups_accessibility": 9,
        "logistics_transport_coordination": 9,
    }


def test_query_style_balance_remains_fifteen_each(labels):
    questions = {row["question_id"]: row for row in labels}
    assert Counter(row["query_style"] for row in questions.values()) == {
        "LEXICAL": 15, "SEMANTIC_PARAPHRASE": 15, "OPERATIONAL_TASK": 15
    }


def test_no_duplicate_question_chunk_pairs(labels):
    pairs = [(row["question_id"], row["chunk_id"]) for row in labels]
    assert len(pairs) == len(set(pairs)) == 485


def test_label_artifact_has_only_published_fields(labels):
    assert tuple(labels[0]) == LABEL_FIELDS
    forbidden = ("rank", "score", "retrieved_by", "fusion", "suggested_grade", "seed_evidence")
    assert all(not any(fragment in field.casefold() for fragment in forbidden) for field in labels[0])


def test_blind_payload_has_only_nine_allowed_fields(payload):
    assert all(tuple(row) == ALLOWED_FIELDS for row in payload)


def test_blind_payload_excludes_all_forbidden_metadata(payload):
    fields = {field.casefold() for row in payload for field in row}
    assert all(not any(fragment in field for fragment in FORBIDDEN_FRAGMENTS) for field in fields)


def test_blind_payload_uses_hash_order_not_source_pool_order(payload):
    expected = sorted(
        payload,
        key=lambda row: hashlib.sha256(f"{row['question_id']}\0{row['chunk_id']}".encode()).hexdigest(),
    )
    assert payload == expected


def test_blind_payload_bytes_are_bound_to_reviewed_judgments(manifest):
    digest = hashlib.sha256(PAYLOAD_PATH.read_bytes()).hexdigest()
    assert digest == manifest["blind_payload_sha256"] == "7da77e322949891233f677661a1ab1e620027d6e552a494970fe9a92fdc675fd"


def test_only_frozen_grades_are_used(labels):
    assert {row["ai_relevance_grade"] for row in labels} <= {"0", "1", "2"}


def test_all_ai_label_statuses_are_complete(labels):
    assert {row["ai_relevance_status"] for row in labels} == {"COMPLETE"}


def test_every_ai_label_has_a_specific_rationale(labels):
    assert all(len(row["ai_relevance_rationale"].split()) >= 8 for row in labels)
    assert all(row["ai_relevance_rationale"] != "This is relevant." for row in labels)


def test_every_ai_label_has_allowed_confidence(labels):
    assert all(row["ai_label_confidence"] in {"HIGH", "MEDIUM", "LOW"} for row in labels)


def test_historical_human_review_file_is_unchanged():
    assert hashlib.sha256(HUMAN_PATH.read_bytes()).hexdigest() == HUMAN_SHA256
    rows = read_csv(HUMAN_PATH)
    assert all(row["human_grade"] == "" and row["human_review_status"] == "PENDING" for row in rows)


def test_retained_human_review_file_is_unchanged():
    assert hashlib.sha256(RETAINED_PATH.read_bytes()).hexdigest() == RETAINED_SHA256
    rows = read_csv(RETAINED_PATH)
    assert all(row["human_grade"] == "" and row["human_review_status"] == "PENDING" for row in rows)


def test_old_machine_suggestion_is_absent_from_labeling_inputs(payload, labels):
    assert all("machine_suggested_grade" not in row for row in payload)
    assert all("machine_suggested_grade" not in row for row in labels)


def test_new_direct_labels_are_not_limited_to_old_suggestions(labels, retained):
    prior = {(row["question_id"], row["chunk_id"]): row["machine_suggested_grade"] for row in retained}
    independent_direct = [
        row for row in labels
        if row["ai_relevance_grade"] == "2" and prior[(row["question_id"], row["chunk_id"])] == ""
    ]
    assert len(independent_direct) >= 45


def test_every_question_has_direct_evidence(labels, manifest):
    direct = {row["question_id"] for row in labels if row["ai_relevance_grade"] == "2"}
    assert len(direct) == manifest["questions_with_direct_evidence"] == 45
    assert manifest["questions_without_direct_evidence"] == 0


def test_grade_counts_match_manifest(labels, manifest):
    assert Counter(row["ai_relevance_grade"] for row in labels) == manifest["grade_counts"]


def test_grade_percentages_match_manifest(labels, manifest):
    counts = Counter(row["ai_relevance_grade"] for row in labels)
    expected = {grade: round(100 * counts[grade] / len(labels), 4) for grade in ("0", "1", "2")}
    assert manifest["grade_percentages"] == expected


def test_distribution_sanity_flags_are_clear(manifest):
    assert manifest["distribution_flags"] == {
        "over_90_percent_grade_2": False,
        "fewer_than_45_grade_2_rows": False,
    }


def test_label_pairs_and_original_text_match_retained_pool(labels, retained):
    source = {(row["question_id"], row["chunk_id"]): row for row in retained}
    assert set(source) == {(row["question_id"], row["chunk_id"]) for row in labels}
    for row in labels:
        original = source[(row["question_id"], row["chunk_id"])]
        assert (row["effective_question"], row["original_text"], row["source_id"], row["page"]) == (
            original["question"], original["excerpt"], original["source_id"], original["page"]
        )


def test_every_labeled_chunk_belongs_to_frozen_corpus(labels):
    # Phase 13A's existing corpus-integrity test resolves every historical pool row
    # against the canonical PDF-derived catalog. The AI set must be a strict subset.
    canonical_pool_ids = {row["chunk_id"] for row in read_csv(HUMAN_PATH)}
    assert all(row["chunk_id"] in canonical_pool_ids for row in labels)


def test_label_fingerprint_matches_manifest(labels, manifest):
    assert hashlib.sha256(canonical_label_bytes(labels)).hexdigest() == manifest["label_dataset_sha256"]


def test_label_fingerprint_is_independent_of_csv_row_order(labels):
    forward = hashlib.sha256(canonical_label_bytes(labels)).hexdigest()
    reverse = hashlib.sha256(canonical_label_bytes(list(reversed(labels)))).hexdigest()
    assert forward == reverse


def test_label_fingerprint_changes_when_a_label_changes(labels):
    changed = [dict(row) for row in labels]
    changed[0]["ai_relevance_grade"] = "1" if changed[0]["ai_relevance_grade"] != "1" else "0"
    assert canonical_label_bytes(changed) != canonical_label_bytes(labels)


def test_consistency_subset_has_ten_questions(manifest):
    rows = read_csv(CONSISTENCY_PATH)
    assert len({row["question_id"] for row in rows}) == manifest["consistency_audit"]["question_count"] == 10


def test_consistency_audit_has_107_passage_comparisons(manifest):
    assert len(read_csv(CONSISTENCY_PATH)) == manifest["consistency_audit"]["passage_comparisons"] == 107


def test_second_pass_labeler_cannot_access_first_pass_labels(payload):
    source = inspect.getsource(grade_pair)
    assert "ai_relevance_grade" not in source
    row = dict(payload[0])
    baseline = grade_pair(row)
    row["first_grade"] = "9"
    row["ai_relevance_grade"] = "9"
    assert grade_pair(row) == baseline


def test_consistency_first_pass_matches_frozen_primary_labels(labels):
    primary = {(row["question_id"], row["chunk_id"]): row["ai_relevance_grade"] for row in labels}
    assert all(row["first_grade"] == primary[(row["question_id"], row["chunk_id"])] for row in read_csv(CONSISTENCY_PATH))


def test_consistency_metrics_match_manifest(manifest):
    audit = manifest["consistency_audit"]
    assert audit["name"] == "AI labeling consistency audit"
    assert audit["exact_agreement"] == 1.0
    assert audit["linear_weighted_cohens_kappa"] == 1.0
    assert audit["grade_2_1_disagreements"] == audit["grade_2_0_disagreements"] == 0
    assert audit["reconciliation"].startswith("NONE")


def test_weighted_kappa_synthetic_identity():
    assert weighted_kappa([0, 1, 2, 2], [0, 1, 2, 2]) == pytest.approx(1.0)


def test_weighted_kappa_synthetic_disagreement():
    assert weighted_kappa([0, 1, 2], [0, 2, 1]) == pytest.approx(0.25)


def test_spotcheck_has_five_examples_per_grade():
    text = (ROOT / "V3_RETRIEVAL_AI_LABEL_SPOTCHECK.md").read_text()
    assert text.count("\n## ") == 15
    assert all(text.count(f"**AI grade:** {grade}") == 5 for grade in (0, 1, 2))


def test_spotcheck_does_not_claim_human_review():
    text = (ROOT / "V3_RETRIEVAL_AI_LABEL_SPOTCHECK.md").read_text()
    assert "AI-assisted and have not been human reviewed" in text


def test_no_actual_retrieval_metric_artifact_exists(manifest):
    forbidden = [
        PHASE13 / "final_benchmark_results.json",
        PHASE13 / "retrieval_metrics.json",
        ROOT / "V3_RETRIEVAL_RESULT.md",
    ]
    assert all(not path.exists() for path in forbidden)
    assert manifest["official_retrieval_metrics_calculated"] is False
    assert manifest["phase13b_started"] is False


def test_no_hybrid_supported_result_was_generated():
    names = [path.name.casefold() for path in PHASE13.iterdir()]
    assert not any("hybrid_supported" in name or "benchmark_result" in name for name in names)


def test_frozen_retrieval_configuration_is_unchanged(manifest):
    assert manifest["retrieval_config_version"] == RETRIEVAL_CONFIG_VERSION == "v3-retrieval-v1"
    assert (DENSE_METHOD_ID, BM25_METHOD_ID, HYBRID_METHOD_ID) == (
        "dense-minilm-v1", "bm25-okapi-v1", "hybrid-rrf-v1"
    )
    assert EMBED_MODEL_NAME == "all-MiniLM-L6-v2"
    assert (BM25_K1, BM25_B, BM25_EPSILON) == (1.5, 0.75, 0.25)
    assert (RRF_K, HYBRID_CANDIDATE_K) == (60, 20)
    assert TOKENIZER_VERSION == "nfkc-casefold-alphanumeric-v1"


def test_frozen_corpus_identity_is_unchanged(manifest):
    assert manifest["corpus_version"] == CORPUS_VERSION == "v3-authoritative-corpus-v1"
    assert manifest["corpus_fingerprint"] == FINGERPRINT
    assert EXPECTED_CHUNK_COUNT == 1797


def test_no_reranker_was_added():
    assert not list((ROOT / "src").rglob("*rerank*"))


def test_amendment_preserves_human_benchmark_history_and_discloses_limitation():
    text = " ".join(AMENDMENT_PATH.read_text().split())
    assert "originally planned human-gold benchmark cannot honestly be completed" in text
    assert "AI-assisted relevance benchmark" in text
    assert "does not have the same evidentiary strength" in text
    assert "`v3-retrieval-benchmark-gold-v1` is not created" in text


def test_documentation_prominently_discloses_ai_assisted_passage_labels():
    text = DOCUMENTATION_PATH.read_text()
    assert "passage-level relevance judgments are AI-assisted" in text
    assert "not independently human annotated" in text
