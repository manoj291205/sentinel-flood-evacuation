"""Phase 13A candidate provenance, pooling, human-label safety, and metric math."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from src.rag.benchmark import (
    BENCHMARK_SPEC_VERSION,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CANDIDATE_BENCHMARK_VERSION,
    FUTURE_GOLD_VERSION,
    POOL_CAP,
    POOL_DEPTH,
    QUERY_STYLES,
    TARGET_ACCEPTED_QUESTIONS,
    TARGET_PER_STYLE,
    TARGET_PER_TOPIC,
    TOPICS,
    CanonicalChunk,
    assert_phase13b_ready,
    chunk_catalog,
    direct_hit_at_k,
    ndcg_at_k,
    paired_bootstrap_difference,
    pooled_recall_at_k,
    reciprocal_rank_at_k,
    select_consistency_questions,
    validate_candidate_manifest,
)
from src.rag.corpus import CORPUS_VERSION, load_manifest
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
    TOKENIZER_VERSION,
)

PHASE13_DIR = Path("data/eval_v3/phase13")
MANIFEST_PATH = PHASE13_DIR / "candidate_question_manifest.json"
QUESTION_REVIEW_PATH = PHASE13_DIR / "question_review.csv"
PASSAGE_REVIEW_PATH = PHASE13_DIR / "human_review.csv"
CONSISTENCY_PATH = PHASE13_DIR / "review_consistency.csv"
PACKET_PATH = Path("V3_RETRIEVAL_HUMAN_REVIEW.md")
SPEC_PATH = Path("V3_RETRIEVAL_BENCHMARK_SPEC.md")
FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"


@pytest.fixture(scope="module")
def prepared() -> PreparedCorpus:
    return prepare_corpus()


@pytest.fixture(scope="module")
def catalog(prepared: PreparedCorpus) -> dict[str, CanonicalChunk]:
    return chunk_catalog(prepared)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


@pytest.fixture(scope="module")
def question_rows() -> list[dict[str, str]]:
    with QUESTION_REVIEW_PATH.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def passage_rows() -> list[dict[str, str]]:
    with PASSAGE_REVIEW_PATH.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_candidate_and_future_gold_versions_are_distinct(manifest: dict):
    assert manifest["benchmark_spec_version"] == BENCHMARK_SPEC_VERSION
    assert manifest["candidate_benchmark_version"] == CANDIDATE_BENCHMARK_VERSION
    assert manifest["future_human_gold_version_reserved"] == FUTURE_GOLD_VERSION
    assert CANDIDATE_BENCHMARK_VERSION != FUTURE_GOLD_VERSION


def test_corpus_version_and_fingerprint_are_exact(manifest: dict):
    assert manifest["corpus_version"] == CORPUS_VERSION
    assert manifest["corpus_fingerprint"] == load_manifest()["fingerprint"] == FINGERPRINT


def test_retrieval_configuration_is_frozen(manifest: dict):
    assert manifest["retrieval_config"] == RETRIEVAL_CONFIG_VERSION == "v3-retrieval-v1"
    assert manifest["retrieval_methods"] == [
        DENSE_METHOD_ID, BM25_METHOD_ID, HYBRID_METHOD_ID
    ]
    assert (BM25_K1, BM25_B, BM25_EPSILON) == (1.5, 0.75, 0.25)
    assert (RRF_K, HYBRID_CANDIDATE_K) == (60, 20)
    assert TOKENIZER_VERSION == "nfkc-casefold-alphanumeric-v1"


def test_target_final_count_and_balances_are_frozen(manifest: dict):
    assert manifest["target_human_accepted_count"] == TARGET_ACCEPTED_QUESTIONS == 45
    assert manifest["target_final_topic_count_each"] == TARGET_PER_TOPIC == 9
    assert manifest["target_final_query_style_count_each"] == TARGET_PER_STYLE == 15


def test_candidate_count_is_sixty(manifest: dict):
    assert manifest["candidate_count"] == len(manifest["candidates"]) == 60


def test_candidate_topic_balance_is_exact(manifest: dict):
    assert manifest["candidate_topic_counts"] == {topic: 12 for topic in TOPICS}


def test_candidate_query_style_balance_is_exact(manifest: dict):
    assert manifest["candidate_query_style_counts"] == {
        style: 20 for style in QUERY_STYLES
    }


def test_candidate_ids_are_unique_and_sequential(manifest: dict):
    ids = [item["candidate_question_id"] for item in manifest["candidates"]]
    assert ids == [f"Q{index:03d}" for index in range(1, 61)]


def test_questions_are_nonempty_and_normalized_unique(manifest: dict):
    questions = [item["question"] for item in manifest["candidates"]]
    assert all(question.strip().endswith("?") for question in questions)
    normalized = [" ".join(question.casefold().split()) for question in questions]
    assert len(normalized) == len(set(normalized))


def test_questions_do_not_contain_explicit_page_references(manifest: dict):
    pattern = re.compile(r"\b(?:page|p\.)\s*\d+", flags=re.IGNORECASE)
    assert all(not pattern.search(item["question"]) for item in manifest["candidates"])


def test_every_seed_chunk_and_excerpt_is_canonical(manifest: dict, catalog):
    validate_candidate_manifest(manifest, catalog)
    for item in manifest["candidates"]:
        chunk = catalog[item["machine_proposed_chunk_id"]]
        assert item["machine_proposed_supporting_excerpt"] in chunk.text
        assert item["machine_proposed_page"] == chunk.page


def test_seed_evidence_covers_all_sources_with_minimum_depth(manifest: dict):
    counts = Counter(item["machine_proposed_source_id"] for item in manifest["candidates"])
    assert counts == {
        "ndma-flood-guidelines-2008": 20,
        "ndma-national-disaster-management-plan-2019": 19,
        "ndma-temporary-shelters-2019": 21,
    }
    assert min(counts.values()) >= 8


def test_machine_proposed_multi_source_candidates_are_explicit(manifest: dict, passage_rows):
    proposed = [item for item in manifest["candidates"] if item["machine_proposed_multi_source"]]
    assert len(proposed) == manifest["machine_proposed_multi_source_candidate_count"] == 28
    assert all(len(item["machine_proposed_supporting_source_ids"]) >= 2 for item in proposed)
    pooled_sources: dict[str, set[str]] = defaultdict(set)
    for row in passage_rows:
        pooled_sources[row["question_id"]].add(row["source_id"])
    assert all(
        set(item["machine_proposed_supporting_source_ids"])
        <= pooled_sources[item["candidate_question_id"]]
        for item in proposed
    )


def test_every_proposal_is_explicitly_machine_only(manifest: dict):
    assert all(item["proposal_status"] == "MACHINE_PROPOSED" for item in manifest["candidates"])
    assert manifest["official_retrieval_metrics_calculated"] is False


def test_question_review_sheet_has_all_candidates(question_rows, manifest):
    assert len(question_rows) == 60
    assert [row["question_id"] for row in question_rows] == [
        item["candidate_question_id"] for item in manifest["candidates"]
    ]


def test_all_human_question_fields_are_pending_or_blank(question_rows):
    assert all(row["human_question_status"] == "PENDING" for row in question_rows)
    assert all(row["human_edited_question"] == "" for row in question_rows)
    assert all(row["human_notes"] == "" for row in question_rows)
    assert all(row["machine_proposed_answerable"] == "MACHINE_PROPOSED_TRUE" for row in question_rows)


def test_passage_review_has_rows_for_every_question(passage_rows):
    grouped = Counter(row["question_id"] for row in passage_rows)
    assert len(grouped) == 60
    assert sum(grouped.values()) == len(passage_rows) == 647
    assert all(1 <= count <= POOL_CAP for count in grouped.values())


def test_pooled_chunks_are_deduplicated_by_question(passage_rows):
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in passage_rows:
        grouped[row["question_id"]].append(row["chunk_id"])
    assert all(len(ids) == len(set(ids)) for ids in grouped.values())


def test_seed_evidence_is_always_in_each_pool(passage_rows):
    grouped = defaultdict(list)
    for row in passage_rows:
        grouped[row["question_id"]].append(row)
    assert all(sum(row["machine_seed_evidence"] == "TRUE" for row in rows) == 1 for rows in grouped.values())


def test_each_retriever_top_five_is_retained(passage_rows):
    grouped = defaultdict(list)
    for row in passage_rows:
        grouped[row["question_id"]].append(row)
    for rows in grouped.values():
        for name in ("dense", "bm25", "hybrid"):
            ranks = {int(row[f"{name}_rank"]) for row in rows if row[f"{name}_rank"]}
            assert set(range(1, 6)) <= ranks


def test_pool_rank_metadata_obeys_top_ten_depth(passage_rows):
    for row in passage_rows:
        ranks = [row["dense_rank"], row["bm25_rank"], row["hybrid_rank"]]
        assert any(ranks) or row["machine_seed_evidence"] == "TRUE"
        assert all(not rank or 1 <= int(rank) <= POOL_DEPTH for rank in ranks)


def test_pool_source_page_text_integrity(passage_rows, catalog):
    for row in passage_rows:
        chunk = catalog[row["chunk_id"]]
        assert (row["source_id"], row["filename"], int(row["page"]), row["excerpt"]) == (
            chunk.source_id, chunk.filename, chunk.page, chunk.text
        )


def test_machine_grade_is_only_a_seed_suggestion(passage_rows):
    assert sum(row["machine_suggested_grade"] == "2" for row in passage_rows) == 60
    assert all(
        row["machine_suggested_grade"] == ("2" if row["machine_seed_evidence"] == "TRUE" else "")
        for row in passage_rows
    )


def test_all_human_passage_fields_are_pending_or_blank(passage_rows):
    assert all(row["human_grade"] == "" for row in passage_rows)
    assert all(row["human_review_status"] == "PENDING" for row in passage_rows)
    assert all(row["human_notes"] == "" for row in passage_rows)


def test_no_human_confirmation_is_fabricated():
    paths = [MANIFEST_PATH, QUESTION_REVIEW_PATH, PASSAGE_REVIEW_PATH, PACKET_PATH]
    combined = "\n".join(path.read_text() for path in paths)
    assert "HUMAN_CONFIRMED" not in combined
    assert "human_verified" not in combined


def test_consistency_audit_waits_for_accepted_questions():
    with CONSISTENCY_PATH.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []
    assert "second_pass_grade" in CONSISTENCY_PATH.read_text().splitlines()[0]


def test_human_packet_contains_all_questions_and_grade_definitions(manifest):
    packet = PACKET_PATH.read_text()
    assert packet.count("— MACHINE_PROPOSED") == 60
    assert "2 — DIRECTLY RELEVANT" in packet
    assert "1 — PARTIALLY RELEVANT" in packet
    assert "0 — NOT RELEVANT" in packet
    assert "WAITING FOR HUMAN REVIEW" in packet


def test_pending_review_cannot_become_gold(question_rows, passage_rows):
    with pytest.raises(ValueError, match="question review is incomplete"):
        assert_phase13b_ready(question_rows, passage_rows)


def complete_review_fixture():
    questions = []
    passages = []
    for index in range(45):
        question_id = f"G{index:03d}"
        topic = TOPICS[index // 9]
        style = QUERY_STYLES[index % 3]
        questions.append({
            "question_id": question_id,
            "topic": topic,
            "query_style": style,
            "human_question_status": "ACCEPT",
            "human_edited_question": "",
        })
        primary_source = f"source-{index % 3}"
        passages.append({
            "question_id": question_id,
            "source_id": primary_source,
            "human_grade": "2",
            "human_review_status": "COMPLETE",
        })
        if index < 8:
            passages.append({
                "question_id": question_id,
                "source_id": f"source-{(index + 1) % 3}",
                "human_grade": "2",
                "human_review_status": "COMPLETE",
            })
    return questions, passages


def test_complete_balanced_human_fixture_is_ready():
    questions, passages = complete_review_fixture()
    assert len(assert_phase13b_ready(questions, passages)) == 45


def test_fewer_than_forty_five_questions_is_rejected():
    questions, passages = complete_review_fixture()
    with pytest.raises(ValueError, match="exactly 45"):
        assert_phase13b_ready(questions[:-1], passages)


def test_missing_human_passage_grade_is_rejected():
    questions, passages = complete_review_fixture()
    passages[0] = {**passages[0], "human_grade": "", "human_review_status": "PENDING"}
    with pytest.raises(ValueError, match="passage review is incomplete"):
        assert_phase13b_ready(questions, passages)


def test_question_without_direct_evidence_is_rejected():
    questions, passages = complete_review_fixture()
    passages = [
        {**row, "human_grade": "1"} if row["question_id"] == "G000" else row
        for row in passages
    ]
    with pytest.raises(ValueError, match="grade-2 passage"):
        assert_phase13b_ready(questions, passages)


def test_edited_question_requires_human_wording():
    questions, passages = complete_review_fixture()
    questions[0] = {**questions[0], "human_question_status": "EDIT"}
    with pytest.raises(ValueError, match="human-edited"):
        assert_phase13b_ready(questions, passages)


def test_final_topic_balance_is_required():
    questions, passages = complete_review_fixture()
    questions[0] = {**questions[0], "topic": TOPICS[1]}
    with pytest.raises(ValueError, match="nine per topic"):
        assert_phase13b_ready(questions, passages)


def test_consistency_selection_is_deterministic_and_ten_questions():
    ids = [f"Q{index:03d}" for index in range(1, 46)]
    first = select_consistency_questions(ids)
    second = select_consistency_questions(ids)
    assert first == second and len(first) == len(set(first)) == 10


def test_direct_hit_synthetic_fixture():
    grades = {"A": 2, "B": 1, "C": 0}
    assert direct_hit_at_k(["B", "A", "C"], grades, 1) == 0
    assert direct_hit_at_k(["B", "A", "C"], grades, 3) == 1


def test_mrr_synthetic_fixture():
    assert reciprocal_rank_at_k(["B", "A", "C"], {"A": 2}, 5) == 0.5
    assert reciprocal_rank_at_k(["B", "C"], {"A": 2}, 5) == 0.0


def test_ndcg_synthetic_fixture():
    grades = {"A": 2, "B": 1, "C": 0}
    assert ndcg_at_k(["A", "B", "C"], grades, 3) == pytest.approx(1.0)
    assert 0 < ndcg_at_k(["B", "C", "A"], grades, 3) < 1


def test_pooled_recall_synthetic_fixture():
    grades = {"A": 2, "B": 2, "C": 1}
    assert pooled_recall_at_k(["A", "C"], grades, 5) == 0.5


def test_paired_bootstrap_is_question_level_and_deterministic():
    hybrid = [1, 1, 0, 1, 0]
    dense = [0, 1, 0, 0, 0]
    first = paired_bootstrap_difference(hybrid, dense, resamples=1000)
    second = paired_bootstrap_difference(hybrid, dense, resamples=1000)
    assert first == second
    assert first[0] == pytest.approx(0.4)
    assert BOOTSTRAP_RESAMPLES == 10_000 and BOOTSTRAP_SEED == 131_313


def test_spec_freezes_primary_secondary_metrics_and_claim_rule():
    spec = SPEC_PATH.read_text()
    assert "DirectHit@5" in spec
    assert all(metric in spec for metric in ("DirectHit@1", "DirectHit@3", "MRR@5", "nDCG@5", "pooled Recall@5"))
    assert "10,000" in spec and "131313" in spec
    assert "HYBRID_SUPPORTED" in spec and "0.05" in spec and "0.02" in spec


def test_no_official_result_or_reranker_artifact_exists(manifest: dict):
    assert not (PHASE13_DIR / "final_benchmark_results.json").exists()
    assert all("rerank" not in method.casefold() for method in manifest["retrieval_methods"])
    assert manifest["official_retrieval_metrics_calculated"] is False


def test_canonical_corpus_size_remains_unchanged(prepared: PreparedCorpus):
    assert len(prepared.ids) == EXPECTED_CHUNK_COUNT == 1797
