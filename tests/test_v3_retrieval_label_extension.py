"""Phase 13A.3 blind pre-metric relevance-label coverage extension."""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from scripts.phase13a3_extend_labels import (
    BLIND_FIELDS,
    COMBINED_FIELDS,
    CONSISTENCY_FIELDS,
    CONSISTENCY_PATH,
    EXTENDED_BENCHMARK_VERSION,
    EXTENDED_LABEL_PATH,
    EXTENDED_MANIFEST_PATH,
    EXTENSION_FIELDS,
    EXTENSION_PATH,
    EXTENSION_VERSION,
    GAP_ARTIFACT_SHA256,
    GAP_PATH,
    HUMAN_REVIEW_FILE_SHA256,
    HUMAN_REVIEW_PATH,
    JUDGMENTS,
    LABEL_PROTOCOL,
    PARENT_BENCHMARK_VERSION,
    PARENT_LABEL_FILE_SHA256,
    PARENT_LABEL_FINGERPRINT,
    PARENT_LABEL_PATH,
    build_blind_rows,
    build_consistency_rows,
    canonical_rows_bytes,
    consistency_selection,
    file_sha256,
    judge_blind_pair,
    load_and_verify_gaps,
)
from scripts.phase13b_retrieval_preflight import get_chunk_by_id
from src.rag.ingest import PreparedCorpus, prepare_corpus
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
)


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT_PATH = ROOT / "V3_RETRIEVAL_BENCHMARK_AI_AMENDMENT.md"
DOCUMENTATION_PATH = ROOT / "DOCUMENTATION.md"
EXPECTED_QUESTIONS = {"Q003", "Q008", "Q016", "Q034"}
EXTENDED_FINGERPRINT = "393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7"
EXTENSION_FINGERPRINT = "df1d939661fa6a44bee9e6978326e79f1a136b00cf210299563742c39e751208"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def gaps() -> list[dict]:
    return load_and_verify_gaps()


@pytest.fixture(scope="module")
def extension() -> list[dict[str, str]]:
    return csv_rows(EXTENSION_PATH)


@pytest.fixture(scope="module")
def combined() -> list[dict[str, str]]:
    return csv_rows(EXTENDED_LABEL_PATH)


@pytest.fixture(scope="module")
def parent() -> list[dict[str, str]]:
    return csv_rows(PARENT_LABEL_PATH)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(EXTENDED_MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def consistency() -> list[dict[str, str]]:
    return csv_rows(CONSISTENCY_PATH)


@pytest.fixture(scope="module")
def prepared() -> PreparedCorpus:
    return prepare_corpus()


@pytest.fixture(scope="module")
def blind(gaps, prepared) -> list[dict]:
    return build_blind_rows(gaps, prepared)


def test_frozen_gap_artifact_is_exact(gaps):
    assert file_sha256(GAP_PATH) == GAP_ARTIFACT_SHA256
    assert len(gaps) == 19


def test_gap_affected_questions_are_exact(gaps):
    assert {row["question_id"] for row in gaps} == EXPECTED_QUESTIONS


def test_gap_pair_keys_are_unique_and_match_declared_judgments(gaps):
    pairs = [(row["question_id"], row["chunk_id"]) for row in gaps]
    assert len(pairs) == len(set(pairs)) == 19
    assert set(pairs) == set(JUDGMENTS)


def test_gap_artifact_has_hashes_and_no_passage_text(gaps):
    forbidden = {"text", "original_text", "excerpt", "passage_text"}
    assert all(len(row["passage_sha256"]) == 64 for row in gaps)
    assert all(forbidden.isdisjoint(row) for row in gaps)


def test_all_gap_chunks_reconstruct_exactly_once_with_verified_metadata(gaps, prepared):
    assert len(prepared.ids) == len(set(prepared.ids)) == EXPECTED_CHUNK_COUNT == 1797
    for row in gaps:
        chunk = get_chunk_by_id(
            row["chunk_id"],
            prepared,
            source_id=row["source_id"],
            filename=row["filename"],
            page=row["page"],
            passage_sha256=row["passage_sha256"],
        )
        assert chunk.chunk_id == row["chunk_id"]


def test_blind_labeling_input_has_only_seven_allowed_fields(blind):
    assert all(tuple(row) == BLIND_FIELDS for row in blind)
    assert BLIND_FIELDS == (
        "question_id",
        "effective_question",
        "chunk_id",
        "source_id",
        "filename",
        "page",
        "original_text",
    )


def test_blind_labeling_excludes_retriever_rank_score_seed_and_prior_labels(blind):
    forbidden = (
        "retriever",
        "rank",
        "score",
        "retrieved_by",
        "suggested",
        "seed",
        "coverage_gap",
        "first_grade",
        "previous_label",
    )
    fields = {field.casefold() for row in blind for field in row}
    assert all(not any(fragment in field for fragment in forbidden) for field in fields)


def test_blind_payload_uses_neutral_question_chunk_order(blind):
    assert blind == sorted(blind, key=lambda row: (row["question_id"], row["chunk_id"]))


def test_blind_judge_rejects_any_extra_metadata(blind):
    contaminated = dict(blind[0])
    contaminated["retriever"] = "Hybrid"
    with pytest.raises(ValueError, match="outside the frozen blind schema"):
        judge_blind_pair(contaminated)
    contaminated = dict(blind[0])
    contaminated["first_grade"] = "2"
    with pytest.raises(ValueError, match="outside the frozen blind schema"):
        judge_blind_pair(contaminated)


def test_label_script_does_not_run_retrieval():
    source = (ROOT / "scripts" / "phase13a3_extend_labels.py").read_text(encoding="utf-8")
    assert "get_retriever" not in source
    assert ".retrieve(" not in source


def test_extension_has_exact_schema_and_nineteen_rows(extension):
    assert len(extension) == 19
    assert tuple(extension[0]) == EXTENSION_FIELDS


def test_extension_contains_all_and_only_gap_pairs(extension, gaps):
    extension_pairs = {(row["question_id"], row["chunk_id"]) for row in extension}
    gap_pairs = {(row["question_id"], row["chunk_id"]) for row in gaps}
    assert extension_pairs == gap_pairs


def test_extension_grade_distribution_is_frozen(extension):
    assert Counter(row["ai_relevance_grade"] for row in extension) == {
        "0": 8,
        "1": 8,
        "2": 3,
    }


def test_extension_status_rationale_confidence_and_protocol(extension):
    assert {row["ai_relevance_status"] for row in extension} == {"COMPLETE"}
    assert all(len(row["ai_relevance_rationale"].split()) >= 8 for row in extension)
    assert Counter(row["ai_label_confidence"] for row in extension) == {
        "HIGH": 6,
        "MEDIUM": 13,
    }
    assert {row["ai_labeler_protocol"] for row in extension} == {LABEL_PROTOCOL}
    assert {row["extension_version"] for row in extension} == {EXTENSION_VERSION}


def test_extension_stores_hash_not_full_source_text(extension, prepared):
    serialized = EXTENSION_PATH.read_text(encoding="utf-8")
    assert all(field not in extension[0] for field in ("text", "original_text", "excerpt"))
    for row in extension:
        chunk = get_chunk_by_id(row["chunk_id"], prepared)
        assert row["source_passage_sha256"] == hashlib.sha256(chunk.text.encode()).hexdigest()
        assert chunk.text not in serialized


def test_original_485_row_file_and_fingerprint_are_unchanged(parent):
    assert len(parent) == 485
    assert file_sha256(PARENT_LABEL_PATH) == PARENT_LABEL_FILE_SHA256
    from scripts.phase13b_retrieval_preflight import canonical_label_bytes

    assert hashlib.sha256(canonical_label_bytes(parent)).hexdigest() == PARENT_LABEL_FINGERPRINT


def test_combined_dataset_has_504_unique_pairs(combined):
    pairs = [(row["question_id"], row["chunk_id"]) for row in combined]
    assert len(combined) == len(set(pairs)) == 504
    assert tuple(combined[0]) == COMBINED_FIELDS


def test_combined_dataset_has_exact_origins_and_v2_version(combined):
    assert Counter(row["label_origin"] for row in combined) == {
        "BASE_V1": 485,
        "COVERAGE_EXTENSION": 19,
    }
    assert {row["benchmark_version"] for row in combined} == {EXTENDED_BENCHMARK_VERSION}


def test_parent_labels_are_semantically_unchanged_inside_combined(parent, combined):
    base = {
        (row["question_id"], row["chunk_id"]): row
        for row in combined
        if row["label_origin"] == "BASE_V1"
    }
    fields = (
        "effective_question",
        "topic",
        "query_style",
        "source_id",
        "filename",
        "page",
        "ai_relevance_grade",
        "ai_relevance_status",
        "ai_relevance_rationale",
        "ai_label_confidence",
        "ai_labeler_protocol",
    )
    for row in parent:
        copy = base[(row["question_id"], row["chunk_id"])]
        assert {field: copy[field] for field in fields} == {
            field: row[field] for field in fields
        }
        assert copy["source_passage_sha256"] == hashlib.sha256(
            row["original_text"].encode()
        ).hexdigest()


def test_extended_fingerprint_is_exact_and_deterministic(combined, manifest):
    forward = hashlib.sha256(canonical_rows_bytes(combined, COMBINED_FIELDS)).hexdigest()
    reverse = hashlib.sha256(
        canonical_rows_bytes(list(reversed(combined)), COMBINED_FIELDS)
    ).hexdigest()
    assert forward == reverse == manifest["extended_label_fingerprint"] == EXTENDED_FINGERPRINT


def test_extension_fingerprint_is_exact(extension, manifest):
    actual = hashlib.sha256(canonical_rows_bytes(extension, EXTENSION_FIELDS)).hexdigest()
    assert actual == manifest["extension_label_fingerprint"] == EXTENSION_FINGERPRINT


def test_manifest_versions_counts_parent_and_reason_are_exact(manifest):
    assert manifest["benchmark_version"] == EXTENDED_BENCHMARK_VERSION
    assert manifest["parent_benchmark_version"] == PARENT_BENCHMARK_VERSION
    assert manifest["parent_label_fingerprint"] == PARENT_LABEL_FINGERPRINT
    assert (manifest["base_rows"], manifest["extension_rows"], manifest["total_rows"]) == (
        485,
        19,
        504,
    )
    assert manifest["questions"] == 45
    assert set(manifest["affected_extension_questions"]) == EXPECTED_QUESTIONS
    assert manifest["coverage_reason"] == "FINAL_EDITED_QUERY_TOP5_COVERAGE"


def test_combined_grade_and_confidence_counts_match_manifest(combined, manifest):
    grades = Counter(row["ai_relevance_grade"] for row in combined)
    confidence = Counter(row["ai_label_confidence"] for row in combined)
    assert {grade: grades[grade] for grade in ("0", "1", "2")} == manifest["grade_counts"]
    assert {
        value: confidence[value] for value in ("HIGH", "MEDIUM", "LOW")
    } == manifest["confidence_counts"]


def test_all_434_frozen_preflight_pairs_are_covered_without_retrieval_rerun(manifest):
    assert manifest["coverage_verification"] == {
        "preflight_unique_top5_pairs": 434,
        "base_labeled_preflight_pairs_preserved": 415,
        "extension_gap_pairs_covered": 19,
        "labeled_after_extension": 434,
        "unlabeled_after_extension": 0,
        "status": "PASS",
        "method": "Frozen preflight counts plus unchanged parent fingerprint and complete disjoint gap-set inclusion; retrieval was not rerun.",
    }


def test_every_question_still_has_direct_evidence(combined, manifest):
    question_ids = {row["question_id"] for row in combined}
    direct_ids = {
        row["question_id"] for row in combined if row["ai_relevance_grade"] == "2"
    }
    assert len(question_ids) == len(direct_ids) == 45
    assert manifest["questions_with_direct_evidence"] == 45
    assert manifest["questions_without_direct_evidence"] == 0


def test_consistency_selection_is_exactly_five_and_neutral(blind, consistency):
    selected = consistency_selection(blind)
    expected = [(row["question_id"], row["chunk_id"]) for row in selected]
    actual = [(row["question_id"], row["chunk_id"]) for row in consistency]
    assert len(actual) == 5
    assert actual == expected
    assert tuple(consistency[0]) == CONSISTENCY_FIELDS


def test_consistency_second_pass_has_no_first_pass_input(blind):
    source = inspect.getsource(build_consistency_rows)
    assert "extension_rows" not in source
    assert "ai_relevance_grade" not in source
    assert all(tuple(row) == BLIND_FIELDS for row in consistency_selection(blind))


def test_consistency_diagnostic_is_exact_without_reconciliation(consistency, manifest):
    assert all(row["agreement"] == "TRUE" for row in consistency)
    assert all(row["absolute_grade_difference"] == "0" for row in consistency)
    diagnostic = manifest["consistency_diagnostic"]
    assert diagnostic["pairs"] == 5
    assert diagnostic["exact_agreement"] == 1.0
    assert diagnostic["disagreements"] == 0
    assert diagnostic["reconciliation"].startswith("NONE")


def test_new_tracked_artifacts_contain_no_full_passage_text(prepared):
    paths = (EXTENSION_PATH, EXTENDED_LABEL_PATH, EXTENDED_MANIFEST_PATH, CONSISTENCY_PATH)
    serialized = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "original_text" not in EXTENSION_PATH.read_text(encoding="utf-8").splitlines()[0]
    assert "original_text" not in EXTENDED_LABEL_PATH.read_text(encoding="utf-8").splitlines()[0]
    gap_ids = [pair[1] for pair in JUDGMENTS]
    for chunk_id in gap_ids:
        assert get_chunk_by_id(chunk_id, prepared).text not in serialized


def test_no_retrieval_quality_metric_or_verdict_was_created(manifest):
    paths = (EXTENSION_PATH, EXTENDED_LABEL_PATH, EXTENDED_MANIFEST_PATH, CONSISTENCY_PATH)
    content = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert all(
        token not in content
        for token in (
            "DirectHit@",
            "MRR@",
            "nDCG@",
            "PooledRecall@",
            "HYBRID_SUPPORTED",
            "HYBRID_NOT_SUPPORTED",
            "bootstrap_samples",
        )
    )
    assert manifest["official_retrieval_metrics_calculated"] is False
    assert manifest["full_phase13b_evaluation_started"] is False


def test_frozen_retrieval_and_corpus_integrity(manifest):
    assert manifest["corpus_version"] == "v3-authoritative-corpus-v1"
    assert manifest["corpus_fingerprint"] == "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"
    assert manifest["canonical_chunks"] == EXPECTED_CHUNK_COUNT == 1797
    assert manifest["retrieval_config_version"] == RETRIEVAL_CONFIG_VERSION == "v3-retrieval-v1"
    assert manifest["retrieval_methods"] == [
        DENSE_METHOD_ID,
        BM25_METHOD_ID,
        HYBRID_METHOD_ID,
    ]
    assert (BM25_K1, BM25_B, BM25_EPSILON, RRF_K, HYBRID_CANDIDATE_K) == (
        1.5,
        0.75,
        0.25,
        60,
        20,
    )
    assert manifest["reranker_added"] is False
    assert not list((ROOT / "src").rglob("*rerank*"))


def test_human_passage_fields_remain_untouched(manifest):
    assert file_sha256(HUMAN_REVIEW_PATH) == HUMAN_REVIEW_FILE_SHA256
    rows = csv_rows(HUMAN_REVIEW_PATH)
    assert all(row["human_grade"] == "" for row in rows)
    assert all(row["human_review_status"] == "PENDING" for row in rows)
    assert manifest["human_passage_labels_created"] == 0
    assert manifest["independent_human_annotation"] is False
    assert manifest["benchmark_characterization"] == "AI-assisted relevance benchmark"


def test_documentation_discloses_coverage_extension_and_ai_assisted_status():
    content = AMENDMENT_PATH.read_text(encoding="utf-8") + "\n" + DOCUMENTATION_PATH.read_text(encoding="utf-8")
    assert "Phase 13A.3" in content
    assert "v3-retrieval-benchmark-ai-assisted-v2" in content
    assert "AI-assisted" in content
    assert "not independently human annotated" in content
    assert "reconstructed locally from the frozen corpus" in content
