"""Phase 13B frozen AI-assisted retrieval evaluation regression tests."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pytest

from scripts.phase13a3_extend_labels import (
    COMBINED_FIELDS,
    EXTENDED_LABEL_PATH,
    EXTENDED_MANIFEST_PATH,
    EXTENSION_PATH,
    PARENT_LABEL_PATH,
    canonical_rows_bytes,
)
from scripts.phase13b_evaluate_retrieval import (
    EVALUATION_VERSION,
    LABEL_COUNT,
    LABEL_FINGERPRINT,
    PER_QUESTION_FIELDS,
    PER_QUESTION_PATH,
    QUESTION_COUNT,
    RANKING_FIELDS,
    RANKINGS_PATH,
    REPORT_PATH,
    RESULT_PATH,
    coverage_gate,
    hybrid_verdict,
    metric_row,
    retrieve_rankings,
    verify_frozen_inputs_v2,
)
from scripts.phase13b_retrieval_preflight import (
    CORPUS_FINGERPRINT,
    CORPUS_VERSION,
    EDITED_QUESTIONS,
    IncompleteLabelCoverageError,
    LABEL_PROTOCOL,
    SYSTEMS,
)
from src.rag.benchmark import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    ndcg_at_k,
    paired_bootstrap_difference,
    pooled_recall_at_k,
    reciprocal_rank_at_k,
)
from src.rag.retrieve import (
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    HYBRID_CANDIDATE_K,
    RETRIEVAL_CONFIG_VERSION,
    RRF_K,
    RetrievedChunk,
)


ROOT = Path(__file__).resolve().parents[1]
PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
PARENT_SHA256 = "9b402cbfead067a62f9c15a2b546c7dc367c2e8b96e8c3fcac7d7fc2f29ec034"
EXTENSION_SHA256 = "2e1784984b59a6d34cbe33ca03f70d1d38c9980cebbead6d12c54ba5067be1c2"
COMBINED_SHA256 = "3bbaf030673b76e573c6f721142ac39f8f8f98a2a5985f55b8c6d1210bfa2129"


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def result() -> dict:
    return json.loads(RESULT_PATH.read_text())


@pytest.fixture(scope="module")
def labels() -> list[dict[str, str]]:
    return csv_rows(EXTENDED_LABEL_PATH)


@pytest.fixture(scope="module")
def per_question() -> list[dict[str, str]]:
    return csv_rows(PER_QUESTION_PATH)


@pytest.fixture(scope="module")
def rankings() -> list[dict[str, str]]:
    return csv_rows(RANKINGS_PATH)


def test_benchmark_version_and_evaluation_version_are_exact(result):
    assert result["evaluation_version"] == EVALUATION_VERSION == "v3-retrieval-evaluation-ai-assisted-v2"
    assert result["benchmark_version"] == "v3-retrieval-benchmark-ai-assisted-v2"


def test_label_fingerprints_and_protocol_are_exact(result):
    assert result["label_fingerprint"] == LABEL_FINGERPRINT
    assert result["parent_label_fingerprint"] == "bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92"
    assert result["label_protocol"] == LABEL_PROTOCOL == "v3-ai-relevance-labeler-v1"


def test_combined_label_count_schema_uniqueness_and_fingerprint(labels):
    assert len(labels) == LABEL_COUNT == 504
    assert tuple(labels[0]) == COMBINED_FIELDS
    pairs = [(row["question_id"], row["chunk_id"]) for row in labels]
    assert len(pairs) == len(set(pairs))
    assert hashlib.sha256(canonical_rows_bytes(labels, COMBINED_FIELDS)).hexdigest() == LABEL_FINGERPRINT


def test_question_count_and_final_effective_edits_are_exact(labels):
    assert len({row["question_id"] for row in labels}) == QUESTION_COUNT == 45
    actual = {
        row["question_id"]: row["effective_question"]
        for row in labels if row["question_id"] in EDITED_QUESTIONS
    }
    assert actual == EDITED_QUESTIONS


def test_corpus_and_retrieval_configuration_are_exact(result):
    assert result["corpus_version"] == CORPUS_VERSION == "v3-authoritative-corpus-v1"
    assert result["corpus_fingerprint"] == CORPUS_FINGERPRINT
    assert result["retrieval_config_version"] == RETRIEVAL_CONFIG_VERSION == "v3-retrieval-v1"
    assert (BM25_K1, BM25_B, BM25_EPSILON, RRF_K, HYBRID_CANDIDATE_K) == (1.5, 0.75, 0.25, 60, 20)


def test_full_frozen_input_verifier_accepts_current_v2_state():
    questions, labels, prepared = verify_frozen_inputs_v2()
    assert (len(questions), len(labels), len(prepared.ids)) == (45, 504, 1797)


def test_rankings_include_every_question_method_and_top_five(rankings):
    assert len(rankings) == 45 * 3 * 5
    counts = Counter((row["question_id"], row["method_id"]) for row in rankings)
    assert len(counts) == 45 * 3 and set(counts.values()) == {5}
    assert set(row["method_id"] for row in rankings) == {method_id for _name, method_id in SYSTEMS}
    assert all(
        {int(row["rank"]) for row in rankings if row["question_id"] == q and row["method_id"] == m}
        == {1, 2, 3, 4, 5}
        for q, m in counts
    )


def test_coverage_join_uses_question_and_chunk_composite_key():
    rankings = [{"question_id": "Q1", "chunk_id": "C"}, {"question_id": "Q2", "chunk_id": "C"}]
    labels = [{"question_id": "Q1", "chunk_id": "C"}, {"question_id": "Q2", "chunk_id": "C"}]
    assert coverage_gate(rankings, labels)["unique_top5_pairs"] == 2


def test_actual_coverage_gate_passes_with_all_434_pairs(result):
    assert result["coverage_gate"] == {
        "unique_top5_pairs": 434,
        "labeled": 434,
        "unlabeled": 0,
        "status": "PASS",
        "missing_pairs": [],
    }


def test_missing_label_causes_hard_stop_and_is_never_zero():
    with pytest.raises(IncompleteLabelCoverageError, match="unlabeled"):
        coverage_gate([{"question_id": "Q", "chunk_id": "missing"}], [])
    with pytest.raises(IncompleteLabelCoverageError, match="never become grade zero"):
        metric_row(["A", "B", "C", "D", "E"], {"A": 0, "B": 0, "C": 0, "D": 0})


def test_direct_hit_cutoffs_and_first_rank_fixture():
    grades = {"A": 0, "B": 1, "C": 2, "D": 0, "E": 0}
    score = metric_row(list(grades), grades)
    assert score["direct_hit_at_1"] == 0
    assert score["direct_hit_at_3"] == 1
    assert score["direct_hit_at_5"] == 1
    assert score["first_direct_rank"] == 3


def test_mrr_fixture():
    grades = {"A": 0, "B": 1, "C": 2, "D": 0, "E": 0}
    assert reciprocal_rank_at_k(list(grades), grades, 5) == pytest.approx(1 / 3)


def test_ndcg_and_idcg_use_all_pooled_grades_fixture():
    ranked = ["A", "B", "C", "D", "E"]
    grades = {"A": 1, "B": 0, "C": 2, "D": 0, "E": 0, "F": 2}
    dcg = 1 / math.log2(2) + 3 / math.log2(4)
    idcg = 3 / math.log2(2) + 3 / math.log2(3) + 1 / math.log2(4)
    assert ndcg_at_k(ranked, grades, 5) == pytest.approx(dcg / idcg)


def test_pooled_recall_fixture_and_duplicates_do_not_double_count():
    grades = {"A": 2, "B": 2, "C": 0}
    assert pooled_recall_at_k(["A", "A", "C"], grades, 3) == 0.5


def test_metric_row_rejects_duplicate_ranked_chunks():
    with pytest.raises(ValueError, match="distinct"):
        metric_row(["A", "A", "B", "C", "D"], {"A": 2, "B": 0, "C": 0, "D": 0})


def test_bootstrap_configuration_and_deterministic_percentile_fixture():
    assert (BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED) == (10_000, 131_313)
    treatment = [1, 1, 0, 1, 0]
    baseline = [0, 1, 0, 0, 1]
    first = paired_bootstrap_difference(treatment, baseline)
    assert first == paired_bootstrap_difference(treatment, baseline)
    assert first[0] == pytest.approx(0.2)
    assert first[1][0] <= first[0] <= first[1][1]


@pytest.mark.parametrize(
    ("difference", "lower", "hybrid_ndcg", "dense_ndcg", "expected"),
    [
        (0.05, 0.001, 0.58, 0.60, "HYBRID_SUPPORTED"),
        (0.049, 0.001, 0.60, 0.60, "HYBRID_NOT_SUPPORTED"),
        (0.05, 0.0, 0.60, 0.60, "HYBRID_NOT_SUPPORTED"),
        (0.05, 0.001, 0.579, 0.60, "HYBRID_NOT_SUPPORTED"),
    ],
)
def test_frozen_verdict_requires_all_three_conditions(difference, lower, hybrid_ndcg, dense_ndcg, expected):
    verdict, conditions = hybrid_verdict(difference, lower, hybrid_ndcg, dense_ndcg)
    assert verdict == expected
    assert (verdict == "HYBRID_SUPPORTED") == all(conditions.values())


def test_actual_principal_comparison_is_exact(result):
    comparison = result["principal_comparison"]
    assert comparison["bootstrap_samples"] == 10_000
    assert comparison["bootstrap_seed"] == 131_313
    assert comparison["hybrid_minus_dense_directhit5"] == pytest.approx(0.2)
    assert comparison["equivalent_question_difference"] == 9
    assert comparison["ci95"]["lower"] == pytest.approx(4 / 45)
    assert comparison["ci95"]["upper"] == pytest.approx(14 / 45)
    assert comparison["final_verdict"] == "HYBRID_SUPPORTED"


def test_overall_metrics_are_finite_and_have_raw_counts(result):
    for system in ("dense", "bm25", "hybrid"):
        metrics = result["overall"][system]
        keys = ("direct_hit_at_1", "direct_hit_at_3", "direct_hit_at_5", "mrr_at_5", "ndcg_at_5", "pooled_recall_at_5")
        assert all(math.isfinite(float(metrics[key])) and 0 <= float(metrics[key]) <= 1 for key in keys)
        assert metrics["direct_hit_at_5_count"] == round(metrics["direct_hit_at_5"] * 45)


def test_topic_groups_are_five_balanced_groups(result):
    assert len(result["topic_subgroups"]) == 5
    assert {group["n"] for group in result["topic_subgroups"].values()} == {9}


def test_query_style_groups_are_three_balanced_groups(result):
    assert set(result["query_style_subgroups"]) == {"LEXICAL", "SEMANTIC_PARAPHRASE", "OPERATIONAL_TASK"}
    assert {group["n"] for group in result["query_style_subgroups"].values()} == {15}


def test_head_to_head_cells_sum_to_45(result):
    assert set(result["head_to_head"]) == {"both_hit", "hybrid_only", "dense_only", "neither"}
    assert sum(result["head_to_head"].values()) == 45


def test_first_direct_rank_diagnostic_is_scoped_to_both_hits(result):
    assert sum(result["first_direct_rank_comparison"].values()) == result["head_to_head"]["both_hit"]


class SpyRetriever:
    def __init__(self, method_id: str, results: list[RetrievedChunk]):
        self.method_id = method_id
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        self.calls.append((query, k))
        return self.results[:k]


def test_retrieval_receives_only_effective_query_and_k(monkeypatch):
    question = {"question_id": "QX", "question": "effective query", "topic": "SECRET", "query_style": "SECRET", "seed": "SECRET"}
    retrievers = {}
    for system, method_id in SYSTEMS:
        results = [
            RetrievedChunk(text=f"t{i}", source_document="f.pdf", page=i, score=1.0, source_id="S", chunk_id=f"{system}{i}", retrieval_method=method_id, rank=i)
            for i in range(1, 6)
        ]
        retrievers[system] = SpyRetriever(method_id, results)
    monkeypatch.setattr("scripts.phase13b_evaluate_retrieval.construct_frozen_retrievers", lambda _prepared: retrievers)
    rows = retrieve_rankings([question], object())
    assert len(rows) == 15
    assert all(retriever.calls == [("effective query", 5)] for retriever in retrievers.values())


def test_per_question_artifact_has_exact_schema_and_45_rows(per_question):
    assert len(per_question) == 45
    assert tuple(per_question[0]) == PER_QUESTION_FIELDS
    assert len({row["question_id"] for row in per_question}) == 45


def test_ranking_artifact_is_compact_and_contains_no_passage_text(rankings):
    assert tuple(rankings[0]) == RANKING_FIELDS
    forbidden = {"text", "original_text", "passage_text", "excerpt", "score", "relevance"}
    assert forbidden.isdisjoint(rankings[0])


def test_no_phase13b_output_duplicates_full_passage_text():
    for path in PHASE13.glob("phase13b*.*"):
        if path.suffix not in {".json", ".csv"}:
            continue
        payload = path.read_text()
        assert '"original_text"' not in payload
        assert '"passage_text"' not in payload
        if path.name != "phase13b_label_coverage_gaps.json":
            assert '"text"' not in payload


def test_result_uses_extended_fingerprint_and_determinism_is_complete(result):
    assert result["label_fingerprint"] == LABEL_FINGERPRINT
    assert result["determinism"] and all(result["determinism"].values())


def test_parent_extension_and_combined_label_files_are_unchanged():
    assert hashlib.sha256(PARENT_LABEL_PATH.read_bytes()).hexdigest() == PARENT_SHA256
    assert hashlib.sha256(EXTENSION_PATH.read_bytes()).hexdigest() == EXTENSION_SHA256
    assert hashlib.sha256(EXTENDED_LABEL_PATH.read_bytes()).hexdigest() == COMBINED_SHA256


def test_extended_manifest_still_denies_human_gold_and_metric_execution():
    manifest = json.loads(EXTENDED_MANIFEST_PATH.read_text())
    assert manifest["independent_human_annotation"] is False
    assert manifest["human_passage_labels_created"] == 0
    assert manifest["official_retrieval_metrics_calculated"] is False


def test_retrieval_and_corpus_integrity_flags_and_no_reranker(result):
    integrity = result["retrieval_integrity"]
    assert all(
        integrity[key]
        for key in (
            "dense_unchanged",
            "bm25_unchanged",
            "hybrid_unchanged",
            "corpus_unchanged",
            "labels_unchanged",
        )
    )
    assert integrity["reranker_added"] is False
    assert not list((ROOT / "src").rglob("*rerank*"))


def test_failure_analysis_contains_required_compact_fields(result):
    required = {"question_id", "effective_question", "topic", "query_style", "best_available_grade2_evidence_chunk", "top5"}
    for cases in result["failure_summary"].values():
        assert all(required == set(case) for case in cases)
        assert all(set(case["top5"]) == {"dense", "bm25", "hybrid"} for case in cases)


def test_source_distributions_each_cover_225_ranked_results(result):
    assert all(sum(counts.values()) == 225 for counts in result["source_distribution_top5"].values())


def test_report_states_scientific_boundaries_and_phase10_freeze():
    report = REPORT_PATH.read_text()
    for phrase in (
        "not be represented as independently human-annotated gold data",
        "PooledRecall@5",
        "not exhaustive corpus recall",
        "Relevance does not establish claim entailment",
        "Phase 10 RL usefulness result, which remains `NO`",
        "Phase 14",
    ):
        assert phrase in report
