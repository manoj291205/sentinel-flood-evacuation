"""Phase 13A.1 adopted-question decisions and passage-review safeguards."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from src.rag.corpus import CORPUS_VERSION
from src.rag.retrieve import (
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    RRF_K,
    RETRIEVAL_CONFIG_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
MANIFEST_PATH = PHASE13 / "candidate_question_manifest.json"
QUESTION_PATH = PHASE13 / "question_review.csv"
ORIGINAL_PASSAGE_PATH = PHASE13 / "human_review.csv"
RETAINED_QUESTION_PATH = PHASE13 / "retained_question_review.csv"
RETAINED_PASSAGE_PATH = PHASE13 / "retained_passage_review.csv"
CONSISTENCY_PATH = PHASE13 / "review_consistency.csv"
PROVENANCE_PATH = PHASE13 / "question_review_provenance.json"
PACKET_PATH = ROOT / "V3_RETRIEVAL_FINAL_PASSAGE_REVIEW.md"
SPEC_PATH = ROOT / "V3_RETRIEVAL_BENCHMARK_SPEC.md"
DOCUMENTATION_PATH = ROOT / "DOCUMENTATION.md"

MANIFEST_SHA256 = "e7ed5e22aaba57dda174de6865e242789cbb611fc2a9e515c78729b05c02952f"
REJECTED = {
    "Q004", "Q007", "Q011", "Q014", "Q019", "Q024", "Q027", "Q032",
    "Q036", "Q038", "Q042", "Q047", "Q052", "Q053", "Q059",
}
EDITS = {
    "Q003": "Where should flood shelters and disaster relief centres be located so that they remain functional during floods?",
    "Q008": "How should flood warning information be presented to affected communities?",
    "Q016": "What personnel, equipment, and procedures are needed to move patients safely during evacuation?",
    "Q034": "What should authorities do when essential water, sanitation, or other services at a temporary shelter are disrupted?",
}


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def question_rows() -> list[dict[str, str]]:
    return csv_rows(QUESTION_PATH)


@pytest.fixture(scope="module")
def original_passages() -> list[dict[str, str]]:
    return csv_rows(ORIGINAL_PASSAGE_PATH)


@pytest.fixture(scope="module")
def retained_questions() -> list[dict[str, str]]:
    return csv_rows(RETAINED_QUESTION_PATH)


@pytest.fixture(scope="module")
def retained_passages() -> list[dict[str, str]]:
    return csv_rows(RETAINED_PASSAGE_PATH)


@pytest.fixture(scope="module")
def provenance() -> dict:
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def test_question_review_provenance_is_explicit(provenance):
    assert provenance["question_review_status"] == "PROJECT_OWNER_ADOPTED_AI_ASSISTED_QUESTION_REVIEW"
    assert provenance["question_review_method"] == "PROJECT_OWNER_ADOPTED_AI_ASSISTED_RECOMMENDATIONS"
    assert provenance["reviewer_role"] == "project_owner"
    assert provenance["ai_assistance"] is True


def test_provenance_rejects_inaccurate_independence_claims(provenance):
    assert provenance["independent_human_review"] is False
    assert provenance["blind_human_annotation"] is False
    assert provenance["multi_reviewer_review"] is False


def test_question_decision_counts_are_exact(question_rows):
    assert Counter(row["human_question_status"] for row in question_rows) == {
        "ACCEPT": 41, "EDIT": 4, "REJECT": 15
    }


def test_exactly_45_questions_are_retained(retained_questions):
    assert len(retained_questions) == 45


def test_retained_topic_balance_is_exact(retained_questions):
    assert Counter(row["topic"] for row in retained_questions) == {
        "flood_management": 9,
        "evacuation_movement": 9,
        "temporary_shelters_relief_camps": 9,
        "vulnerable_groups_accessibility": 9,
        "logistics_transport_coordination": 9,
    }


def test_retained_query_style_balance_is_exact(retained_questions):
    assert Counter(row["query_style"] for row in retained_questions) == {
        "LEXICAL": 15, "SEMANTIC_PARAPHRASE": 15, "OPERATIONAL_TASK": 15
    }


def test_rejected_ids_are_absent_from_retained_set(retained_questions):
    assert REJECTED.isdisjoint(row["question_id"] for row in retained_questions)


@pytest.mark.parametrize(("question_id", "wording"), sorted(EDITS.items()))
def test_edited_wording_is_effective(question_id, wording, retained_questions, retained_passages):
    question = next(row for row in retained_questions if row["question_id"] == question_id)
    assert question["question"] == wording
    assert {row["question"] for row in retained_passages if row["question_id"] == question_id} == {wording}


def test_original_candidate_manifest_is_byte_unchanged(manifest):
    assert hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() == MANIFEST_SHA256
    assert manifest["candidate_count"] == len(manifest["candidates"]) == 60


def test_retained_questions_keep_seed_source_provenance(retained_questions):
    assert all(row["machine_seed_source"] and row["machine_seed_page"] for row in retained_questions)
    assert all(row["question_review_method"] == "PROJECT_OWNER_ADOPTED_AI_ASSISTED_RECOMMENDATIONS" for row in retained_questions)


def test_retained_pool_uses_only_original_chunk_rows(original_passages, retained_passages):
    retained_ids = {row["question_id"] for row in retained_passages}
    original = {
        (row["question_id"], row["chunk_id"])
        for row in original_passages
        if row["question_id"] in retained_ids
    }
    retained = {(row["question_id"], row["chunk_id"]) for row in retained_passages}
    assert retained == original
    assert len(retained) == len(retained_passages) == 485


def test_retained_pool_preserves_frozen_passage_metadata(original_passages, retained_passages):
    fields = ["source_id", "filename", "page", "excerpt", "dense_rank", "bm25_rank", "hybrid_rank", "machine_seed_evidence", "machine_suggested_grade"]
    original = {(row["question_id"], row["chunk_id"]): row for row in original_passages}
    for row in retained_passages:
        source = original[(row["question_id"], row["chunk_id"])]
        assert {field: row[field] for field in fields} == {field: source[field] for field in fields}


def test_retained_passage_counts_match_reported_scale(retained_passages):
    counts = Counter(row["question_id"] for row in retained_passages)
    assert len(counts) == 45
    assert min(counts.values()) == 9
    assert max(counts.values()) == 14
    assert len(retained_passages) / 45 == pytest.approx(10.7777777778)


def test_no_machine_grade_is_copied_to_human_grade(retained_passages):
    assert any(row["machine_suggested_grade"] == "2" for row in retained_passages)
    assert all(row["human_grade"] == "" for row in retained_passages)


def test_all_retained_passage_statuses_remain_pending(retained_passages):
    assert all(row["human_review_status"] == "PENDING" for row in retained_passages)
    assert all(row["human_notes"] == "" for row in retained_passages)


def test_consistency_audit_is_deterministic_and_retained(retained_questions):
    rows = csv_rows(CONSISTENCY_PATH)
    expected = {"Q006", "Q012", "Q030", "Q033", "Q035", "Q037", "Q041", "Q045", "Q055", "Q056"}
    retained = {row["question_id"] for row in retained_questions}
    assert {row["question_id"] for row in rows} == expected
    assert expected <= retained
    assert expected.isdisjoint(REJECTED)


def test_consistency_audit_has_no_fabricated_grades():
    rows = csv_rows(CONSISTENCY_PATH)
    assert all(row["first_pass_grade"] == row["second_pass_grade"] == "" for row in rows)
    assert all(row["second_pass_status"] == "PENDING" for row in rows)


def test_final_packet_contains_only_45_retained_questions(retained_questions):
    packet = PACKET_PATH.read_text(encoding="utf-8")
    assert packet.count("\n## Q") == 45
    assert all(f"## {row['question_id']}\n" in packet for row in retained_questions)
    assert all(f"## {question_id}\n" not in packet for question_id in REJECTED)


def test_final_packet_deemphasizes_ranks_in_main_review():
    main, appendix = PACKET_PATH.read_text(encoding="utf-8").split("## Technical appendix", maxsplit=1)
    assert "Retrieved by:" not in main
    assert "Machine suggested grade:" not in main
    assert "| Question | Chunk | Dense | BM25 | Hybrid |" in appendix


def test_documentation_discloses_actual_review_method():
    combined = SPEC_PATH.read_text(encoding="utf-8") + "\n" + DOCUMENTATION_PATH.read_text(encoding="utf-8")
    assert "PROJECT_OWNER_ADOPTED_AI_ASSISTED_QUESTION_REVIEW" in combined
    assert "PROJECT_OWNER_ADOPTED_AI_ASSISTED_RECOMMENDATIONS" in combined
    assert "not blind, independent" in combined


def test_frozen_retrieval_and_corpus_identifiers_are_unchanged(manifest):
    assert CORPUS_VERSION == manifest["corpus_version"] == "v3-authoritative-corpus-v1"
    assert manifest["corpus_fingerprint"] == "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"
    assert RETRIEVAL_CONFIG_VERSION == manifest["retrieval_config"] == "v3-retrieval-v1"
    assert (BM25_K1, BM25_B, BM25_EPSILON, RRF_K) == (1.5, 0.75, 0.25, 60)


def test_no_reranker_was_added():
    assert not list((ROOT / "src").rglob("*rerank*"))


def test_no_final_metrics_or_result_was_generated(provenance):
    assert provenance["official_retrieval_metrics_calculated"] is False
    forbidden = [
        PHASE13 / "final_benchmark_results.json",
        PHASE13 / "retrieval_metrics.json",
        ROOT / "V3_RETRIEVAL_RESULT.md",
    ]
    assert all(not path.exists() for path in forbidden)
    assert provenance["passage_review_status"] == "WAITING_FOR_PASSAGE_RELEVANCE_REVIEW"
