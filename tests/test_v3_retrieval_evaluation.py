"""Phase 13B frozen top-five coverage gate and metric-refusal behavior."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts.phase13b_retrieval_preflight import (
    BENCHMARK_VERSION,
    CORPUS_FINGERPRINT,
    CORPUS_VERSION,
    EDITED_QUESTIONS,
    EVALUATION_VERSION,
    LABEL_FINGERPRINT,
    LABEL_PATH,
    LABEL_PROTOCOL,
    OUTPUT_PATH,
    SYSTEMS,
    CanonicalChunk,
    IncompleteLabelCoverageError,
    build_coverage_report,
    canonical_label_bytes,
    get_chunk_by_id,
    require_complete_coverage,
)
from src.rag.benchmark import chunk_catalog
from src.rag.ingest import PreparedCorpus, prepare_corpus
from src.rag.retrieve import (
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    EXPECTED_CHUNK_COUNT,
    HYBRID_CANDIDATE_K,
    RETRIEVAL_CONFIG_VERSION,
    RRF_K,
    RetrievedChunk,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
QUESTION_PATH = PHASE13 / "retained_question_review.csv"
RETAINED_PASSAGE_PATH = PHASE13 / "retained_passage_review.csv"
RESULT_PATH = PHASE13 / "phase13b_retrieval_results.json"
PER_QUESTION_PATH = PHASE13 / "phase13b_per_question.csv"
REPORT_PATH = ROOT / "V3_RETRIEVAL_EVALUATION.md"

LABEL_FILE_SHA256 = "9b402cbfead067a62f9c15a2b546c7dc367c2e8b96e8c3fcac7d7fc2f29ec034"
RETAINED_PASSAGE_SHA256 = "042155e9be1174c538d17132da3b9c6fbccce2b97d5a23b8f1aa8b805e119b29"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(OUTPUT_PATH.read_text())


@pytest.fixture(scope="module")
def labels() -> list[dict[str, str]]:
    return csv_rows(LABEL_PATH)


@pytest.fixture(scope="module")
def prepared() -> PreparedCorpus:
    return prepare_corpus()


@pytest.fixture(scope="module")
def catalog(prepared: PreparedCorpus) -> dict[str, CanonicalChunk]:
    return chunk_catalog(prepared)


def test_frozen_phase13b_identities_are_exact(artifact):
    assert artifact["evaluation_version"] == EVALUATION_VERSION == "v3-retrieval-evaluation-ai-assisted-v1"
    assert artifact["benchmark_version"] == BENCHMARK_VERSION == "v3-retrieval-benchmark-ai-assisted-v1"
    assert artifact["label_protocol"] == LABEL_PROTOCOL == "v3-ai-relevance-labeler-v1"
    assert artifact["label_fingerprint"] == LABEL_FINGERPRINT
    assert artifact["corpus_version"] == CORPUS_VERSION == "v3-authoritative-corpus-v1"
    assert artifact["corpus_fingerprint"] == CORPUS_FINGERPRINT


def test_retrieval_configuration_remains_frozen(artifact):
    assert artifact["retrieval_config_version"] == RETRIEVAL_CONFIG_VERSION == "v3-retrieval-v1"
    assert tuple(method_id for _name, method_id in SYSTEMS) == (
        "dense-minilm-v1",
        "bm25-okapi-v1",
        "hybrid-rrf-v1",
    )
    assert (BM25_K1, BM25_B, BM25_EPSILON) == (1.5, 0.75, 0.25)
    assert (RRF_K, HYBRID_CANDIDATE_K) == (60, 20)


def test_frozen_question_and_corpus_counts_are_exact(artifact, catalog):
    assert artifact["question_count"] == 45
    assert len(catalog) == EXPECTED_CHUNK_COUNT == 1797
    assert len({chunk.source_id for chunk in catalog.values()}) == 3


def test_final_edited_query_text_is_used(artifact):
    gap_questions = {
        row["question_id"]: row["effective_question"] for row in artifact["coverage_gaps"]
    }
    assert gap_questions == EDITED_QUESTIONS
    retained = {row["question_id"]: row["question"] for row in csv_rows(QUESTION_PATH)}
    assert all(retained[question_id] == text for question_id, text in EDITED_QUESTIONS.items())


def test_coverage_gate_stops_with_exact_observed_counts(artifact):
    assert artifact["coverage_gate"] == {
        "status": "FAIL",
        "total_unique_top5_pairs": 434,
        "labeled_pairs": 415,
        "unlabeled_pairs": 19,
        "affected_question_count": 4,
        "affected_question_ids": ["Q003", "Q008", "Q016", "Q034"],
    }
    assert artifact["phase13b_status"] == "NEEDS_LABEL_COVERAGE_EXTENSION"


def test_gap_rows_are_deduplicated_by_question_and_chunk(artifact):
    pairs = [
        (row["question_id"], row["chunk_id"]) for row in artifact["coverage_gaps"]
    ]
    assert len(pairs) == len(set(pairs)) == 19


def test_every_gap_has_required_traceability_fields(artifact):
    required = {
        "question_id",
        "effective_question",
        "retriever",
        "rank",
        "chunk_id",
        "source_id",
        "filename",
        "page",
        "corpus_version",
        "corpus_fingerprint",
        "passage_sha256",
    }
    assert all(required <= set(row) for row in artifact["coverage_gaps"])
    assert all(row["passage_sha256"] and row["source_id"] and row["filename"] for row in artifact["coverage_gaps"])


def test_gap_artifact_contains_no_full_passage_text_field(artifact):
    forbidden = {"text", "original_text", "excerpt", "passage_text"}
    assert all(forbidden.isdisjoint(row) for row in artifact["coverage_gaps"])


def test_gap_retriever_occurrences_cover_only_frozen_top_five(artifact):
    expected_ids = dict(SYSTEMS)
    for row in artifact["coverage_gaps"]:
        assert row["retriever"]
        assert set(row["retriever"]) == set(row["rank"]) == set(row["method_id"])
        assert all(1 <= row["rank"][name] <= 5 for name in row["retriever"])
        assert all(row["method_id"][name] == expected_ids[name] for name in row["retriever"])


def test_cross_retriever_gap_occurrences_are_aggregated_not_duplicated(artifact):
    shared = [row for row in artifact["coverage_gaps"] if len(row["retriever"]) > 1]
    assert shared
    assert any(set(row["retriever"]) == {"Dense", "BM25", "Hybrid"} for row in shared)


def test_gap_join_is_question_id_plus_chunk_id(artifact, labels):
    labeled_pairs = {(row["question_id"], row["chunk_id"]) for row in labels}
    assert all(
        (row["question_id"], row["chunk_id"]) not in labeled_pairs
        for row in artifact["coverage_gaps"]
    )
    # Some gap chunks are labeled for another question; chunk ID alone is invalid.
    labeled_chunk_ids = {row["chunk_id"] for row in labels}
    assert any(row["chunk_id"] in labeled_chunk_ids for row in artifact["coverage_gaps"])


def test_every_gap_matches_the_frozen_canonical_corpus(artifact, catalog):
    for row in artifact["coverage_gaps"]:
        chunk = catalog[row["chunk_id"]]
        assert (row["source_id"], row["filename"], row["page"]) == (
            chunk.source_id,
            chunk.filename,
            chunk.page,
        )
        assert row["corpus_version"] == CORPUS_VERSION
        assert row["corpus_fingerprint"] == CORPUS_FINGERPRINT
        assert row["passage_sha256"] == hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()


def test_local_chunk_reconstruction_verifies_all_gap_metadata(artifact, prepared):
    for row in artifact["coverage_gaps"]:
        chunk = get_chunk_by_id(
            row["chunk_id"],
            prepared,
            source_id=row["source_id"],
            filename=row["filename"],
            page=row["page"],
            passage_sha256=row["passage_sha256"],
        )
        assert chunk.chunk_id == row["chunk_id"]


def test_local_chunk_reconstruction_rejects_missing_duplicate_and_mismatch():
    prepared = PreparedCorpus(
        documents=["first", "second"],
        metadatas=[
            {"source_id": "S", "source_document": "s.pdf", "page": 1},
            {"source_id": "S", "source_document": "s.pdf", "page": 2},
        ],
        ids=["duplicate", "duplicate"],
        source_chunk_counts={},
        page_count=2,
        text_page_count=2,
    )
    with pytest.raises(ValueError, match="exactly once"):
        get_chunk_by_id("duplicate", prepared)
    with pytest.raises(ValueError, match="exactly once"):
        get_chunk_by_id("missing", prepared)
    unique = PreparedCorpus(
        documents=["first"],
        metadatas=[{"source_id": "S", "source_document": "s.pdf", "page": 1}],
        ids=["unique"],
        source_chunk_counts={},
        page_count=1,
        text_page_count=1,
    )
    with pytest.raises(ValueError, match="source_id mismatch"):
        get_chunk_by_id("unique", unique, source_id="wrong")
    with pytest.raises(ValueError, match="passage SHA-256 mismatch"):
        get_chunk_by_id("unique", unique, passage_sha256="0" * 64)


def test_label_fingerprint_is_recomputed_from_all_frozen_rows(labels):
    assert len(labels) == 485
    assert hashlib.sha256(canonical_label_bytes(labels)).hexdigest() == LABEL_FINGERPRINT


def test_relevance_labels_and_retained_pool_are_byte_unchanged():
    assert hashlib.sha256(LABEL_PATH.read_bytes()).hexdigest() == LABEL_FILE_SHA256
    assert hashlib.sha256(RETAINED_PASSAGE_PATH.read_bytes()).hexdigest() == RETAINED_PASSAGE_SHA256


def test_missing_labels_are_never_assumed_grade_zero(artifact):
    assert artifact["missing_labels_assumed_grade_0"] is False
    assert all("ai_relevance_grade" not in row for row in artifact["coverage_gaps"])


def test_metric_guard_refuses_incomplete_coverage(artifact):
    with pytest.raises(IncompleteLabelCoverageError, match="zero unlabeled"):
        require_complete_coverage(artifact)


def test_complete_coverage_permits_the_separate_evaluation_path():
    require_complete_coverage(
        {"coverage_gate": {"status": "PASS", "unlabeled_pairs": 0}}
    )


def test_no_official_metric_or_report_artifact_was_created(artifact):
    assert artifact["official_retrieval_metrics_calculated"] is False
    assert not RESULT_PATH.exists()
    assert not PER_QUESTION_PATH.exists()
    assert not REPORT_PATH.exists()
    assert "overall" not in artifact and "principal_comparison" not in artifact


def test_no_other_phase13b_artifact_contains_retrieved_passage_text():
    data_artifacts = sorted(PHASE13.glob("phase13b*.json"))
    assert data_artifacts == [OUTPUT_PATH]
    for path in data_artifacts:
        payload = json.loads(path.read_text())
        assert '"text"' not in json.dumps(payload)
        assert '"original_text"' not in json.dumps(payload)
    assert not list(PHASE13.glob("phase13b*.csv"))


def test_no_reranker_was_added():
    assert not list((ROOT / "src").rglob("*rerank*"))


class SpyRetriever:
    def __init__(self, method_id: str, results: list[RetrievedChunk]):
        self.method_id = method_id
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        self.calls.append((query, k))
        return self.results[:k]


def fake_fixture():
    method_ids = dict(SYSTEMS)
    catalog = {
        f"C{index}": CanonicalChunk(
            chunk_id=f"C{index}",
            source_id="source",
            filename="source.pdf",
            page=index,
            text=f"text {index}",
        )
        for index in range(1, 8)
    }

    def result(chunk_id: str, rank: int, method_id: str) -> RetrievedChunk:
        chunk = catalog[chunk_id]
        return RetrievedChunk(
            text=chunk.text,
            source_document=chunk.filename,
            source_id=chunk.source_id,
            page=chunk.page,
            score=float(rank),
            chunk_id=chunk_id,
            retrieval_method=method_id,
            rank=rank,
        )

    rankings = {
        "Dense": ["C1", "C2", "C3", "C4", "C7"],
        "BM25": ["C1", "C2", "C3", "C5", "C6"],
        "Hybrid": ["C1", "C2", "C3", "C4", "C7"],
    }
    retrievers = {
        name: SpyRetriever(
            method_ids[name],
            [result(chunk_id, rank, method_ids[name]) for rank, chunk_id in enumerate(ids, 1)],
        )
        for name, ids in rankings.items()
    }
    question = {
        "question_id": "QX",
        "question": "query text",
        "topic": "must not leak",
        "query_style": "must not leak",
        "seed_chunk": "must not leak",
    }
    labels = [{"question_id": "QX", "chunk_id": f"C{index}"} for index in range(1, 7)]
    return question, labels, retrievers, catalog


def test_top_five_union_uses_all_three_retrievers_and_detects_missing_pair():
    question, labels, retrievers, catalog = fake_fixture()
    report = build_coverage_report([question], labels, retrievers, catalog)
    assert report["coverage_gate"]["total_unique_top5_pairs"] == 7
    assert report["coverage_gate"]["labeled_pairs"] == 6
    assert report["coverage_gate"]["unlabeled_pairs"] == 1
    assert report["coverage_gaps"][0]["chunk_id"] == "C7"
    assert report["coverage_gaps"][0]["retriever"] == ["Dense", "Hybrid"]


def test_retrievers_receive_only_query_and_k_without_analysis_or_label_fields():
    question, labels, retrievers, catalog = fake_fixture()
    build_coverage_report([question], labels, retrievers, catalog)
    assert all(retriever.calls == [("query text", 5)] for retriever in retrievers.values())


def test_coverage_report_is_deterministic_on_identical_input():
    first = fake_fixture()
    second = fake_fixture()
    assert build_coverage_report([first[0]], first[1], first[2], first[3]) == build_coverage_report(
        [second[0]], second[1], second[2], second[3]
    )


def test_synthetic_complete_coverage_reports_pass():
    question, labels, retrievers, catalog = fake_fixture()
    labels.append({"question_id": "QX", "chunk_id": "C7"})
    report = build_coverage_report([question], labels, retrievers, catalog)
    assert report["coverage_gate"]["status"] == "PASS"
    assert report["coverage_gate"]["unlabeled_pairs"] == 0
    assert report["phase13b_status"] == "READY_FOR_EVALUATION"
    require_complete_coverage(report)
