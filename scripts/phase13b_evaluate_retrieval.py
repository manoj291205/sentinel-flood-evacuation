#!/usr/bin/env python3
"""Evaluate the frozen Phase 13B AI-assisted retrieval benchmark v2.

The evaluator reconstructs all rankings from the frozen retrievers, refuses to score
an unlabelled top-five question/chunk pair, and writes only compact provenance—not
authoritative passage text—to the Phase 13B result artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase13a3_extend_labels import (  # noqa: E402
    COMBINED_FIELDS,
    EXTENDED_BENCHMARK_VERSION,
    EXTENDED_LABEL_PATH,
    EXTENDED_MANIFEST_PATH,
    EXTENSION_PATH,
    HUMAN_REVIEW_FILE_SHA256,
    HUMAN_REVIEW_PATH,
    PARENT_LABEL_FILE_SHA256,
    PARENT_LABEL_FINGERPRINT,
    PARENT_LABEL_PATH,
    canonical_rows_bytes,
    file_sha256,
)
from scripts.phase13b_retrieval_preflight import (  # noqa: E402
    CORPUS_FINGERPRINT,
    CORPUS_VERSION,
    EDITED_QUESTIONS,
    IncompleteLabelCoverageError,
    LABEL_PROTOCOL,
    QUESTION_PATH,
    STYLE_COUNTS,
    SYSTEMS,
    TOPIC_COUNTS,
    TOP_K,
    construct_frozen_retrievers,
    read_csv_rows,
)
from src.rag.benchmark import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    direct_hit_at_k,
    ndcg_at_k,
    paired_bootstrap_difference,
    pooled_recall_at_k,
    reciprocal_rank_at_k,
)
from src.rag.corpus import canonical_documents, load_manifest, validate_manifest  # noqa: E402
from src.rag.ingest import prepare_corpus  # noqa: E402
from src.rag.retrieve import (  # noqa: E402
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    EXPECTED_CHUNK_COUNT,
    HYBRID_CANDIDATE_K,
    RETRIEVAL_CONFIG_VERSION,
    RRF_K,
    TOKENIZER_VERSION,
)


PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
RESULT_PATH = PHASE13 / "phase13b_retrieval_results_v2.json"
PER_QUESTION_PATH = PHASE13 / "phase13b_per_question_v2.csv"
RANKINGS_PATH = PHASE13 / "phase13b_rankings_v2.csv"
REPORT_PATH = ROOT / "V3_RETRIEVAL_EVALUATION.md"
PHASE12_PATH = ROOT / "data" / "eval_v3" / "phase12_retrieval_sanity.json"

EVALUATION_VERSION = "v3-retrieval-evaluation-ai-assisted-v2"
LABEL_FINGERPRINT = "393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7"
QUESTION_COUNT = 45
LABEL_COUNT = 504
METRICS = (
    "direct_hit_at_1",
    "direct_hit_at_3",
    "direct_hit_at_5",
    "mrr_at_5",
    "ndcg_at_5",
    "pooled_recall_at_5",
)
SYSTEM_KEYS = {"Dense": "dense", "BM25": "bm25", "Hybrid": "hybrid"}
TOPIC_LABELS = {
    "flood_management": "flood",
    "evacuation_movement": "evacuation",
    "temporary_shelters_relief_camps": "temporary_shelters",
    "vulnerable_groups_accessibility": "vulnerable_accessibility",
    "logistics_transport_coordination": "logistics_transport",
}
PER_QUESTION_FIELDS = (
    "question_id",
    "effective_question",
    "topic",
    "query_style",
    "dense_hit1",
    "dense_hit3",
    "dense_hit5",
    "dense_first_direct_rank",
    "dense_mrr5",
    "dense_ndcg5",
    "dense_pooled_recall5",
    "bm25_hit1",
    "bm25_hit3",
    "bm25_hit5",
    "bm25_first_direct_rank",
    "bm25_mrr5",
    "bm25_ndcg5",
    "bm25_pooled_recall5",
    "hybrid_hit1",
    "hybrid_hit3",
    "hybrid_hit5",
    "hybrid_first_direct_rank",
    "hybrid_mrr5",
    "hybrid_ndcg5",
    "hybrid_pooled_recall5",
)
RANKING_FIELDS = ("question_id", "method_id", "rank", "chunk_id", "source_id", "page")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen_inputs_v2() -> tuple[list[dict[str, str]], list[dict[str, str]], object]:
    """Verify every benchmark/corpus/retrieval identity before ranking."""
    manifest = json.loads(EXTENDED_MANIFEST_PATH.read_text())
    expected = {
        "benchmark_version": EXTENDED_BENCHMARK_VERSION,
        "parent_benchmark_version": "v3-retrieval-benchmark-ai-assisted-v1",
        "label_protocol": LABEL_PROTOCOL,
        "extended_label_fingerprint": LABEL_FINGERPRINT,
        "parent_label_fingerprint": PARENT_LABEL_FINGERPRINT,
        "total_rows": LABEL_COUNT,
        "questions": QUESTION_COUNT,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "canonical_chunks": EXPECTED_CHUNK_COUNT,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"extended manifest mismatch for {key}")
    if tuple(manifest["fingerprint_procedure"]["fields_included"]) != COMBINED_FIELDS:
        raise ValueError("extended label fingerprint field list changed")
    if _sha256(PARENT_LABEL_PATH) != PARENT_LABEL_FILE_SHA256:
        raise ValueError("parent 485-row label artifact changed")
    if _sha256(HUMAN_REVIEW_PATH) != HUMAN_REVIEW_FILE_SHA256:
        raise ValueError("retained passage-review artifact changed")

    questions = read_csv_rows(QUESTION_PATH)
    labels = read_csv_rows(EXTENDED_LABEL_PATH)
    if len(questions) != QUESTION_COUNT or len(labels) != LABEL_COUNT:
        raise ValueError("frozen v2 question or label count changed")
    if not labels or tuple(labels[0]) != COMBINED_FIELDS:
        raise ValueError("combined label schema changed")
    pairs = [(row["question_id"], row["chunk_id"]) for row in labels]
    if len(pairs) != len(set(pairs)):
        raise ValueError("combined labels contain duplicate question/chunk pairs")
    if hashlib.sha256(canonical_rows_bytes(labels, COMBINED_FIELDS)).hexdigest() != LABEL_FINGERPRINT:
        raise ValueError("combined label fingerprint changed")
    if Counter(row["topic"] for row in questions) != TOPIC_COUNTS:
        raise ValueError("topic balance changed")
    if Counter(row["query_style"] for row in questions) != STYLE_COUNTS:
        raise ValueError("query-style balance changed")
    question_text = {row["question_id"]: row["question"] for row in questions}
    for question_id, text in EDITED_QUESTIONS.items():
        if question_text.get(question_id) != text:
            raise ValueError(f"final wording changed for {question_id}")
    for row in labels:
        if (
            row["effective_question"] != question_text[row["question_id"]]
            or row["benchmark_version"] != EXTENDED_BENCHMARK_VERSION
            or row["ai_labeler_protocol"] != LABEL_PROTOCOL
            or row["ai_relevance_status"] != "COMPLETE"
            or row["ai_relevance_grade"] not in {"0", "1", "2"}
        ):
            raise ValueError("combined label content is not frozen v2 data")
    direct_questions = {row["question_id"] for row in labels if row["ai_relevance_grade"] == "2"}
    if direct_questions != set(question_text):
        raise ValueError("each question must have grade-2 evidence")

    corpus_manifest = load_manifest()
    sources = validate_manifest(corpus_manifest)
    if len(sources) != 3 or len(canonical_documents(corpus_manifest)) != 3:
        raise ValueError("canonical corpus document count changed")
    prepared = prepare_corpus()
    if len(prepared.ids) != EXPECTED_CHUNK_COUNT or len(set(prepared.ids)) != EXPECTED_CHUNK_COUNT:
        raise ValueError("canonical chunk set changed")
    canonical = {
        chunk_id: (str(meta["source_id"]), str(meta["source_document"]), int(meta["page"]), text)
        for chunk_id, text, meta in zip(prepared.ids, prepared.documents, prepared.metadatas)
    }
    for row in labels:
        source_id, filename, page, text = canonical[row["chunk_id"]]
        if (row["source_id"], row["filename"], int(row["page"])) != (source_id, filename, page):
            raise ValueError(f"label provenance changed for {row['chunk_id']}")
        if hashlib.sha256(text.encode("utf-8")).hexdigest() != row["source_passage_sha256"]:
            raise ValueError(f"label passage hash changed for {row['chunk_id']}")
    if (
        (BM25_K1, BM25_B, BM25_EPSILON) != (1.5, 0.75, 0.25)
        or TOKENIZER_VERSION != "nfkc-casefold-alphanumeric-v1"
        or (RRF_K, HYBRID_CANDIDATE_K) != (60, 20)
        or tuple(method_id for _name, method_id in SYSTEMS)
        != ("dense-minilm-v1", "bm25-okapi-v1", "hybrid-rrf-v1")
    ):
        raise ValueError("retrieval configuration changed")
    return questions, labels, prepared


def retrieve_rankings(questions: Sequence[Mapping[str, str]], prepared: object) -> list[dict]:
    """Construct fresh retrievers and capture compact top-five rankings."""
    retrievers = construct_frozen_retrievers(prepared)
    rows: list[dict] = []
    for question in questions:
        for system_name, method_id in SYSTEMS:
            retriever = retrievers[system_name]
            if retriever.method_id != method_id:
                raise ValueError(f"method ID changed for {system_name}")
            # Leakage firewall: only effective query text and k enter retrieval.
            results = retriever.retrieve(question["question"], TOP_K)
            if len(results) != TOP_K:
                raise ValueError(f"{system_name} did not return five results")
            ids = [result.chunk_id for result in results]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{system_name} returned duplicate chunks")
            for rank, result in enumerate(results, 1):
                if result.rank != rank or result.retrieval_method != method_id:
                    raise ValueError(f"non-canonical {system_name} ranking")
                rows.append(
                    {
                        "question_id": question["question_id"],
                        "method_id": method_id,
                        "rank": rank,
                        "chunk_id": result.chunk_id,
                        "source_id": result.source_id,
                        "page": result.page,
                    }
                )
    return rows


def coverage_gate(rankings: Sequence[Mapping], labels: Sequence[Mapping[str, str]]) -> dict:
    ranked_pairs = {(row["question_id"], row["chunk_id"]) for row in rankings}
    label_pairs = {(row["question_id"], row["chunk_id"]) for row in labels}
    missing = sorted(ranked_pairs - label_pairs)
    gate = {
        "unique_top5_pairs": len(ranked_pairs),
        "labeled": len(ranked_pairs & label_pairs),
        "unlabeled": len(missing),
        "status": "PASS" if not missing else "FAIL",
        "missing_pairs": [
            {"question_id": question_id, "chunk_id": chunk_id}
            for question_id, chunk_id in missing
        ],
    }
    if missing:
        raise IncompleteLabelCoverageError(
            f"official metrics blocked: {len(missing)} top-five pairs are unlabeled"
        )
    return gate


def metric_row(ranked_ids: Sequence[str], grades: Mapping[str, int]) -> dict[str, float | int | None]:
    """Score one question after enforcing complete coverage and unique ranks."""
    if len(ranked_ids) != TOP_K or len(set(ranked_ids)) != TOP_K:
        raise ValueError("metric input requires five distinct ranked chunks")
    missing = [chunk_id for chunk_id in ranked_ids if chunk_id not in grades]
    if missing:
        raise IncompleteLabelCoverageError("missing ranked labels must never become grade zero")
    first = next((rank for rank, chunk_id in enumerate(ranked_ids, 1) if grades[chunk_id] == 2), None)
    return {
        "direct_hit_at_1": direct_hit_at_k(ranked_ids, grades, 1),
        "direct_hit_at_3": direct_hit_at_k(ranked_ids, grades, 3),
        "direct_hit_at_5": direct_hit_at_k(ranked_ids, grades, 5),
        "first_direct_rank": first,
        "mrr_at_5": reciprocal_rank_at_k(ranked_ids, grades, 5),
        "ndcg_at_5": ndcg_at_k(ranked_ids, grades, 5),
        "pooled_recall_at_5": pooled_recall_at_k(ranked_ids, grades, 5),
    }


def hybrid_verdict(
    difference: float,
    ci_lower: float,
    hybrid_ndcg: float,
    dense_ndcg: float,
) -> tuple[str, dict[str, bool]]:
    """Apply all and only the three frozen Hybrid-support conditions."""
    conditions = {
        "effect_threshold_pass": difference >= 0.05,
        "ci_condition_pass": ci_lower > 0,
        "ndcg_guardrail_pass": hybrid_ndcg >= dense_ndcg - 0.02,
    }
    verdict = (
        "HYBRID_SUPPORTED"
        if all(conditions.values())
        else "HYBRID_NOT_SUPPORTED"
    )
    return verdict, conditions


def _aggregate(rows: Sequence[Mapping], system: str) -> dict[str, float | int]:
    prefix = SYSTEM_KEYS[system]
    mapping = {
        "direct_hit_at_1": f"{prefix}_hit1",
        "direct_hit_at_3": f"{prefix}_hit3",
        "direct_hit_at_5": f"{prefix}_hit5",
        "mrr_at_5": f"{prefix}_mrr5",
        "ndcg_at_5": f"{prefix}_ndcg5",
        "pooled_recall_at_5": f"{prefix}_pooled_recall5",
    }
    result: dict[str, float | int] = {
        metric: mean(float(row[field]) for row in rows) for metric, field in mapping.items()
    }
    result["direct_hit_at_1_count"] = sum(int(row[mapping["direct_hit_at_1"]]) for row in rows)
    result["direct_hit_at_3_count"] = sum(int(row[mapping["direct_hit_at_3"]]) for row in rows)
    result["direct_hit_at_5_count"] = sum(int(row[mapping["direct_hit_at_5"]]) for row in rows)
    result["questions"] = len(rows)
    return result


def _subgroups(per_question: Sequence[Mapping], field: str, labels: Mapping[str, str] | None = None) -> dict:
    result = {}
    for value in sorted({str(row[field]) for row in per_question}):
        subset = [row for row in per_question if row[field] == value]
        key = labels[value] if labels else value
        result[key] = {
            "group_value": value,
            "n": len(subset),
            "dense": _aggregate(subset, "Dense"),
            "bm25": _aggregate(subset, "BM25"),
            "hybrid": _aggregate(subset, "Hybrid"),
        }
    return result


def _source_distribution(rankings: Sequence[Mapping]) -> dict:
    source_names = {
        "ndma-flood-guidelines-2008": "NDMA Management of Floods",
        "ndma-national-disaster-management-plan-2019": "National Disaster Management Plan 2019",
        "ndma-temporary-shelters-2019": "National Guidelines for Temporary Shelters",
    }
    result = {}
    for system_name, method_id in SYSTEMS:
        counts = Counter(row["source_id"] for row in rankings if row["method_id"] == method_id)
        result[SYSTEM_KEYS[system_name]] = {
            source_names[source_id]: counts[source_id] for source_id in source_names
        }
    return result


def evaluate(
    questions: Sequence[Mapping[str, str]],
    labels: Sequence[Mapping[str, str]],
    rankings: Sequence[Mapping],
) -> tuple[dict, list[dict]]:
    gate = coverage_gate(rankings, labels)
    grades_by_question: dict[str, dict[str, int]] = {}
    for row in labels:
        grades_by_question.setdefault(row["question_id"], {})[row["chunk_id"]] = int(
            row["ai_relevance_grade"]
        )
    ranked: dict[tuple[str, str], list[str]] = {}
    for question in questions:
        for system_name, method_id in SYSTEMS:
            ranked[(question["question_id"], system_name)] = [
                row["chunk_id"]
                for row in rankings
                if row["question_id"] == question["question_id"] and row["method_id"] == method_id
            ]

    per_question: list[dict] = []
    score_cache: dict[tuple[str, str], dict] = {}
    for question in questions:
        question_id = question["question_id"]
        row: dict = {
            "question_id": question_id,
            "effective_question": question["question"],
            "topic": question["topic"],
            "query_style": question["query_style"],
        }
        for system_name, _method_id in SYSTEMS:
            scores = metric_row(ranked[(question_id, system_name)], grades_by_question[question_id])
            score_cache[(question_id, system_name)] = scores
            prefix = SYSTEM_KEYS[system_name]
            row.update(
                {
                    f"{prefix}_hit1": scores["direct_hit_at_1"],
                    f"{prefix}_hit3": scores["direct_hit_at_3"],
                    f"{prefix}_hit5": scores["direct_hit_at_5"],
                    f"{prefix}_first_direct_rank": scores["first_direct_rank"],
                    f"{prefix}_mrr5": scores["mrr_at_5"],
                    f"{prefix}_ndcg5": scores["ndcg_at_5"],
                    f"{prefix}_pooled_recall5": scores["pooled_recall_at_5"],
                }
            )
        per_question.append(row)

    overall = {SYSTEM_KEYS[name]: _aggregate(per_question, name) for name, _ in SYSTEMS}
    hybrid_hits = [int(row["hybrid_hit5"]) for row in per_question]
    dense_hits = [int(row["dense_hit5"]) for row in per_question]
    observed, ci = paired_bootstrap_difference(
        hybrid_hits, dense_hits, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED
    )
    verdict, conditions = hybrid_verdict(
        observed,
        ci[0],
        float(overall["hybrid"]["ndcg_at_5"]),
        float(overall["dense"]["ndcg_at_5"]),
    )

    head = Counter()
    rank_comparison = Counter()
    for row in per_question:
        dense_hit, hybrid_hit = int(row["dense_hit5"]), int(row["hybrid_hit5"])
        cell = (
            "both_hit" if dense_hit and hybrid_hit else
            "hybrid_only" if hybrid_hit else
            "dense_only" if dense_hit else
            "neither"
        )
        head[cell] += 1
        if dense_hit and hybrid_hit:
            dense_rank = int(row["dense_first_direct_rank"])
            hybrid_rank = int(row["hybrid_first_direct_rank"])
            rank_comparison[
                "hybrid_better" if hybrid_rank < dense_rank else
                "dense_better" if dense_rank < hybrid_rank else
                "same"
            ] += 1

    failure_groups: dict[str, list[dict]] = {
        "hybrid_only_successes": [],
        "dense_only_successes": [],
        "bm25_only_successes": [],
        "all_system_failures": [],
    }
    for row in per_question:
        hits = {name: int(row[f"{SYSTEM_KEYS[name]}_hit5"]) for name, _ in SYSTEMS}
        category = None
        if hits["Hybrid"] and not hits["Dense"]:
            category = "hybrid_only_successes"
        if hits["Dense"] and not hits["Hybrid"]:
            category = "dense_only_successes"
        if hits["BM25"] and not hits["Dense"] and not hits["Hybrid"]:
            category = "bm25_only_successes"
        if not any(hits.values()):
            category = "all_system_failures"
        if category:
            question_id = row["question_id"]
            direct_ids = sorted(
                chunk_id for chunk_id, grade in grades_by_question[question_id].items() if grade == 2
            )
            failure_groups[category].append(
                {
                    "question_id": question_id,
                    "effective_question": row["effective_question"],
                    "topic": row["topic"],
                    "query_style": row["query_style"],
                    "best_available_grade2_evidence_chunk": direct_ids[0],
                    "top5": {
                        SYSTEM_KEYS[name]: ranked[(question_id, name)] for name, _ in SYSTEMS
                    },
                }
            )

    phase12 = json.loads(PHASE12_PATH.read_text())
    result = {
        "evaluation_version": EVALUATION_VERSION,
        "benchmark_version": EXTENDED_BENCHMARK_VERSION,
        "label_protocol": LABEL_PROTOCOL,
        "label_fingerprint": LABEL_FINGERPRINT,
        "parent_label_fingerprint": PARENT_LABEL_FINGERPRINT,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        "question_count": QUESTION_COUNT,
        "coverage_gate": gate,
        "overall": overall,
        "principal_comparison": {
            "hybrid_minus_dense_directhit5": observed,
            "equivalent_question_difference": sum(hybrid_hits) - sum(dense_hits),
            "bootstrap_samples": BOOTSTRAP_RESAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "ci95": {"lower": ci[0], "upper": ci[1], "method": "paired percentile bootstrap"},
            "effect_threshold": 0.05,
            **conditions,
            "final_verdict": verdict,
        },
        "secondary_comparisons": {
            "bm25_minus_dense": {
                metric: float(overall["bm25"][metric]) - float(overall["dense"][metric])
                for metric in METRICS
            },
            "hybrid_minus_bm25": {
                metric: float(overall["hybrid"][metric]) - float(overall["bm25"][metric])
                for metric in METRICS
            },
        },
        "topic_subgroups": _subgroups(per_question, "topic", TOPIC_LABELS),
        "query_style_subgroups": _subgroups(per_question, "query_style"),
        "head_to_head": {key: head[key] for key in ("both_hit", "hybrid_only", "dense_only", "neither")},
        "first_direct_rank_comparison": {
            key: rank_comparison[key] for key in ("hybrid_better", "same", "dense_better")
        },
        "failure_summary": failure_groups,
        "source_distribution_top5": _source_distribution(rankings),
        "latency_context_phase12": {
            "scope": phase12["latency_scope"],
            "dense": phase12["latency"]["dense"],
            "bm25": phase12["latency"]["bm25"],
            "hybrid": phase12["latency"]["hybrid"],
            "phase13_remeasured": False,
        },
        "benchmark_provenance": {
            "independently_human_annotated": False,
            "ai_assisted_relevance_labels": True,
            "project_owner_adopted_question_review": True,
            "pre_metric_coverage_extension_pairs": 19,
            "labels_changed_after_metrics": False,
        },
        "retrieval_integrity": {
            "dense_unchanged": True,
            "bm25_unchanged": True,
            "hybrid_unchanged": True,
            "corpus_unchanged": True,
            "labels_unchanged": True,
            "reranker_added": False,
        },
    }
    return result, per_question


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def render_report(result: Mapping) -> str:
    overall = result["overall"]
    comparison = result["principal_comparison"]
    supported = comparison["final_verdict"] == "HYBRID_SUPPORTED"
    interpretation = (
        "Hybrid retrieval was supported over the frozen Dense baseline under the pre-registered "
        "Phase 13 criteria on this AI-assisted benchmark."
        if supported else
        "Hybrid retrieval was not supported over the frozen Dense baseline under the pre-registered "
        "Phase 13 criteria on this AI-assisted benchmark."
    )
    lines = [
        "# Sentinel-Agent V3 — Phase 13B Retrieval Evaluation",
        "",
        "## 1. Executive result",
        "",
        f"Formal verdict: `{comparison['final_verdict']}`. {interpretation}",
        "",
        "## 2. Research question",
        "",
        "Does frozen Hybrid RRF improve DirectHit@5 over the frozen Dense MiniLM baseline under the pre-registered rule? BM25 comparisons are secondary and descriptive.",
        "",
        "## 3. Benchmark provenance",
        "",
        "Question selection was project-owner adopted with disclosed AI assistance. Passage relevance judgments were generated using a blind AI-assisted labeling protocol. Nineteen additional question/chunk pairs were blindly labeled before retrieval metrics were calculated after the pre-registered label-coverage gate identified missing annotations caused by edited final queries. The benchmark must not be represented as independently human-annotated gold data.",
        "",
        "## 4. Why coverage extension was required",
        "",
        "Final edits to Q003, Q008, Q016, and Q034 changed top-five membership. The pre-metric gate froze all 19 missing pairs before any quality metric; every pair was then blindly labeled without retriever identity or rank.",
        "",
        "## 5. Frozen 504-label benchmark",
        "",
        f"The authoritative benchmark is `{EXTENDED_BENCHMARK_VERSION}`: 504 unique labels for 45 questions, fingerprint `{LABEL_FINGERPRINT}`, with unchanged 485-label parent `{PARENT_LABEL_FINGERPRINT}`.",
        "",
        "## 6. Retrieval systems",
        "",
        "Dense `dense-minilm-v1`, BM25 `bm25-okapi-v1` (`k1=1.5`, `b=0.75`, `epsilon=0.25`), and Hybrid `hybrid-rrf-v1` (`RRF_K=60`, candidate depth `max(20,k)`) were rerun unchanged at k=5. No reranker was added.",
        "",
        "## 7. Coverage gate",
        "",
        f"Fresh coverage was {result['coverage_gate']['labeled']}/{result['coverage_gate']['unique_top5_pairs']}; unlabeled pairs: {result['coverage_gate']['unlabeled']}; status: `{result['coverage_gate']['status']}`.",
        "",
        "## 8. Metrics",
        "",
        "DirectHit and MRR count only grade 2. nDCG uses gains `2^rel-1` and an ideal ranking from all 504 pooled labels for each question. PooledRecall@5 divides distinct retrieved grade-2 chunks by all grade-2 chunks in that question's annotated pool; it is not exhaustive corpus recall.",
        "",
        "## 9. Overall results",
        "",
        "| Retriever | DirectHit@1 | DirectHit@3 | DirectHit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid")):
        metric = overall[key]
        lines.append("| " + " | ".join([
            label,
            _fmt(metric["direct_hit_at_1"]), _fmt(metric["direct_hit_at_3"]),
            _fmt(metric["direct_hit_at_5"]), _fmt(metric["mrr_at_5"]),
            _fmt(metric["ndcg_at_5"]), _fmt(metric["pooled_recall_at_5"]),
        ]) + " |")
    lines.extend([
        "",
        "Raw DirectHit@5 counts: " + ", ".join(
            f"{name} {overall[key]['direct_hit_at_5_count']}/45"
            for key, name in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid"))
        ) + ".",
        "",
        "## 10. Hybrid-vs-Dense paired bootstrap",
        "",
        f"Observed DirectHit@5 difference: {_fmt(comparison['hybrid_minus_dense_directhit5'])} ({comparison['equivalent_question_difference']:+d} net questions). The 10,000-resample, seed-131313 paired question-level percentile bootstrap 95% CI is [{_fmt(comparison['ci95']['lower'])}, {_fmt(comparison['ci95']['upper'])}].",
        "",
        "## 11. Frozen decision rule",
        "",
        f"All three conditions are required: difference >=0.05 ({comparison['effect_threshold_pass']}), CI lower bound >0 ({comparison['ci_condition_pass']}), and Hybrid nDCG@5 >= Dense nDCG@5 - 0.02 ({comparison['ndcg_guardrail_pass']}). With n=45, one question is 0.02222, two are 0.04444, and three are 0.06667, so the effect condition requires at least a three-question net advantage.",
        "",
        "## 12. Formal verdict",
        "",
        f"`{comparison['final_verdict']}` — {interpretation}",
        "",
        "The secondary comparisons below are descriptive deltas; positive values favor the first-named system.",
        "",
        "| Comparison | DirectHit@1 | DirectHit@3 | DirectHit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| BM25 - Dense | " + " | ".join(
            _fmt(result["secondary_comparisons"]["bm25_minus_dense"][metric])
            for metric in METRICS
        ) + " |",
        "| Hybrid - BM25 | " + " | ".join(
            _fmt(result["secondary_comparisons"]["hybrid_minus_bm25"][metric])
            for metric in METRICS
        ) + " |",
        "",
        "## 13. Topic analysis",
        "",
        "Each topic has n=9. All results are descriptive; no subgroup significance is claimed.",
        "",
        "| Topic | Retriever | Hit@1 | Hit@3 | Hit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, group in result["topic_subgroups"].items():
        for system, label in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid")):
            metric = group[system]
            lines.append(
                f"| {name} | {label} | "
                + " | ".join(_fmt(metric[key]) for key in METRICS)
                + " |"
            )
    lines.extend([
        "",
        "## 14. Query-style analysis",
        "",
        "Each style has n=15. All six metrics are descriptive.",
        "",
        "| Query style | Retriever | Hit@1 | Hit@3 | Hit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, group in result["query_style_subgroups"].items():
        for system, label in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid")):
            metric = group[system]
            lines.append(
                f"| {name} | {label} | "
                + " | ".join(_fmt(metric[key]) for key in METRICS)
                + " |"
            )
    head = result["head_to_head"]
    rank = result["first_direct_rank_comparison"]
    failure = result["failure_summary"]
    lines.extend([
        "",
        "## 15. Head-to-head analysis",
        "",
        f"DirectHit@5: both hit {head['both_hit']}, Hybrid only {head['hybrid_only']}, Dense only {head['dense_only']}, neither {head['neither']} (sum 45).",
        "",
        "## 16. Rank analysis",
        "",
        f"Among questions where both hit, Hybrid's first direct-evidence rank was better on {rank['hybrid_better']}, the same on {rank['same']}, and worse on {rank['dense_better']}.",
        "",
        "## 17. Failure analysis",
        "",
        f"Hybrid-only successes: {', '.join(x['question_id'] for x in failure['hybrid_only_successes']) or 'none'}. Dense-only successes: {', '.join(x['question_id'] for x in failure['dense_only_successes']) or 'none'}. BM25-only successes: {', '.join(x['question_id'] for x in failure['bm25_only_successes']) or 'none'}. All-system failures: {', '.join(x['question_id'] for x in failure['all_system_failures']) or 'none'}.",
        "",
        "For each case below, the evidence field is a deterministic representative from the available grade-2 label pool. Ranked IDs are shown in order.",
        "",
        "| Case | Question | Topic/style | Grade-2 evidence | Dense top 5 | BM25 top 5 | Hybrid top 5 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    for category, cases in failure.items():
        for case in cases:
            lines.append(
                "| "
                + " | ".join(
                    [
                        category.replace("_", " "),
                        f"{case['question_id']}: {case['effective_question']}",
                        f"{case['topic']} / {case['query_style']}",
                        f"`{case['best_available_grade2_evidence_chunk']}`",
                        "<br>".join(f"`{item}`" for item in case["top5"]["dense"]),
                        "<br>".join(f"`{item}`" for item in case["top5"]["bm25"]),
                        "<br>".join(f"`{item}`" for item in case["top5"]["hybrid"]),
                    ]
                )
                + " |"
            )
    lines.extend([
        "",
        "The main observed failure pattern was broad same-topic material displacing the directly answering chunk below rank five. Semantic paraphrases were especially visible in Q020 and Q056, while Q039 exposed a chunk-boundary/adjacency problem: systems retrieved the contextual `p115-c0` chunk but missed the directly useful neighboring `p115-c1`. Q002 likewise retrieved forecasting context without the more specific requested information. Hybrid-only successes generally arose when lexical evidence promoted an otherwise missed direct chunk into the fused top five. These are post-metric diagnostics; retrieval was not altered.",
        "",
        "## 18. Source distribution",
        "",
        "Top-five source counts are descriptive; no source-diversity constraint was imposed and concentration alone is not a quality failure.",
        "",
        "| Retriever | Floods | National Plan | Temporary Shelters |",
        "| --- | ---: | ---: | ---: |",
    ])
    for key, label in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid")):
        dist = result["source_distribution_top5"][key]
        lines.append(f"| {label} | {dist['NDMA Management of Floods']} | {dist['National Disaster Management Plan 2019']} | {dist['National Guidelines for Temporary Shelters']} |")
    latency = result["latency_context_phase12"]
    lines.extend([
        "",
        "## 19. Latency context",
        "",
        f"Frozen Phase 12 warmed medians were Dense {_fmt(latency['dense']['median_ms'])} ms, BM25 {_fmt(latency['bm25']['median_ms'])} ms, and Hybrid {_fmt(latency['hybrid']['median_ms'])} ms. Startup/model load/index construction were excluded. Phase 13 did not remeasure latency or use it to change the verdict.",
        "",
        "## 20. Reproducibility",
        "",
        "The full benchmark ran twice from fresh retriever objects. Rankings, coverage, per-question and overall metrics, bootstrap interval, and verdict were identical. Retrieval received only effective query text and k; labels, seed evidence, topic, and query style never entered ranking. Ranking and result artifacts contain no full passage text.",
        "",
        "## 21. Limitations",
        "",
        "This is a small, three-document, single-publisher, AI-assisted pooled benchmark—not independently human-gold data or exhaustive corpus recall. Relevance does not establish claim entailment and retrieval quality does not establish safer decisions or improved real-world outcomes.",
        "",
        "## 22. Implications for Phase 14",
        "",
        "Phase 14 may separately evaluate claim support and entailment; it has not been started. Phase 13 has no authority to revise the frozen Phase 10 RL usefulness result, which remains `NO`.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    questions, labels, prepared = verify_frozen_inputs_v2()
    first_rankings = retrieve_rankings(questions, prepared)
    first_result, first_per_question = evaluate(questions, labels, first_rankings)
    second_rankings = retrieve_rankings(questions, prepared)
    second_result, second_per_question = evaluate(questions, labels, second_rankings)
    if first_rankings != second_rankings:
        raise AssertionError("repeat top-five rankings differ")
    if first_per_question != second_per_question:
        raise AssertionError("repeat per-question metrics differ")
    if first_result != second_result:
        raise AssertionError("repeat aggregate/bootstrap/verdict differs")
    first_result["determinism"] = {
        "repeat_rankings_identical": True,
        "repeat_coverage_identical": True,
        "repeat_per_question_metrics_identical": True,
        "repeat_overall_metrics_identical": True,
        "repeat_bootstrap_identical": True,
        "repeat_verdict_identical": True,
    }
    RESULT_PATH.write_text(json.dumps(first_result, indent=2, ensure_ascii=False) + "\n")
    csv_rows = []
    for row in first_per_question:
        csv_rows.append({
            field: (
                "" if row[field] is None else
                f"{row[field]:.12f}" if isinstance(row[field], float) else
                row[field]
            )
            for field in PER_QUESTION_FIELDS
        })
    _write_csv(PER_QUESTION_PATH, PER_QUESTION_FIELDS, csv_rows)
    _write_csv(RANKINGS_PATH, RANKING_FIELDS, first_rankings)
    REPORT_PATH.write_text(render_report(first_result))
    print(f"Coverage: {first_result['coverage_gate']['labeled']}/{first_result['coverage_gate']['unique_top5_pairs']}")
    print(json.dumps(first_result["overall"], indent=2))
    print(json.dumps(first_result["principal_comparison"], indent=2))
    print(f"Wrote {RESULT_PATH}, {PER_QUESTION_PATH}, {RANKINGS_PATH}, and {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
