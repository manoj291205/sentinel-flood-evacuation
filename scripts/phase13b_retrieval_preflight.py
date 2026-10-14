#!/usr/bin/env python3
"""Run the Phase 13B frozen-input and top-five label-coverage gate.

This module deliberately does not implement retrieval-quality metrics. If any result
used by a future metric lacks a frozen question/chunk relevance label, it writes the
required gap artifact and refuses metric calculation.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.benchmark import CanonicalChunk, chunk_catalog  # noqa: E402
from src.rag.corpus import canonical_documents, load_manifest, validate_manifest  # noqa: E402
from src.rag.ingest import PreparedCorpus, prepare_corpus  # noqa: E402
from src.rag.retrieve import (  # noqa: E402
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
    BM25Retriever,
    DenseRetriever,
    HybridRetriever,
    RetrievedChunk,
    Retriever,
    frozen_corpus_identity,
)


PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
QUESTION_PATH = PHASE13 / "retained_question_review.csv"
LABEL_PATH = PHASE13 / "ai_assisted_passage_labels.csv"
LABEL_MANIFEST_PATH = PHASE13 / "ai_assisted_label_manifest.json"
OUTPUT_PATH = PHASE13 / "phase13b_label_coverage_gaps.json"

EVALUATION_VERSION = "v3-retrieval-evaluation-ai-assisted-v1"
BENCHMARK_VERSION = "v3-retrieval-benchmark-ai-assisted-v1"
LABEL_PROTOCOL = "v3-ai-relevance-labeler-v1"
LABEL_FINGERPRINT = "bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92"
CORPUS_VERSION = "v3-authoritative-corpus-v1"
CORPUS_FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"
QUESTION_COUNT = 45
LABEL_COUNT = 485
TOP_K = 5

LABEL_FIELDS = (
    "question_id",
    "effective_question",
    "topic",
    "query_style",
    "chunk_id",
    "source_id",
    "filename",
    "page",
    "original_text",
    "ai_relevance_grade",
    "ai_relevance_status",
    "ai_relevance_rationale",
    "ai_label_confidence",
    "ai_labeler_protocol",
    "ai_benchmark_version",
)

SYSTEMS = (
    ("Dense", DENSE_METHOD_ID),
    ("BM25", BM25_METHOD_ID),
    ("Hybrid", HYBRID_METHOD_ID),
)
SYSTEM_ORDER = {name: index for index, (name, _method_id) in enumerate(SYSTEMS)}

TOPIC_COUNTS = {
    "flood_management": 9,
    "evacuation_movement": 9,
    "temporary_shelters_relief_camps": 9,
    "vulnerable_groups_accessibility": 9,
    "logistics_transport_coordination": 9,
}
STYLE_COUNTS = {
    "LEXICAL": 15,
    "SEMANTIC_PARAPHRASE": 15,
    "OPERATIONAL_TASK": 15,
}
EDITED_QUESTIONS = {
    "Q003": "Where should flood shelters and disaster relief centres be located so that they remain functional during floods?",
    "Q008": "How should flood warning information be presented to affected communities?",
    "Q016": "What personnel, equipment, and procedures are needed to move patients safely during evacuation?",
    "Q034": "What should authorities do when essential water, sanitation, or other services at a temporary shelter are disrupted?",
}


class IncompleteLabelCoverageError(RuntimeError):
    """Raised whenever official metrics are requested with incomplete top-five labels."""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def get_chunk_by_id(
    chunk_id: str,
    prepared: PreparedCorpus,
    *,
    source_id: str | None = None,
    filename: str | None = None,
    page: int | None = None,
    passage_sha256: str | None = None,
) -> CanonicalChunk:
    """Reconstruct one chunk locally and optionally verify its frozen provenance."""
    if not (
        len(prepared.ids) == len(prepared.documents) == len(prepared.metadatas)
    ):
        raise ValueError("prepared corpus arrays have inconsistent lengths")
    matches = [index for index, candidate in enumerate(prepared.ids) if candidate == chunk_id]
    if len(matches) != 1:
        raise ValueError(f"chunk ID must exist exactly once: {chunk_id}")
    index = matches[0]
    metadata = prepared.metadatas[index]
    chunk = CanonicalChunk(
        chunk_id=chunk_id,
        source_id=str(metadata["source_id"]),
        filename=str(metadata["source_document"]),
        page=int(metadata["page"]),
        text=prepared.documents[index],
    )
    expected = (source_id, filename, page)
    actual = (chunk.source_id, chunk.filename, chunk.page)
    for label, expected_value, actual_value in zip(
        ("source_id", "filename", "page"), expected, actual
    ):
        if expected_value is not None and expected_value != actual_value:
            raise ValueError(f"chunk {label} mismatch for {chunk_id}")
    digest = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
    if passage_sha256 is not None and passage_sha256 != digest:
        raise ValueError(f"chunk passage SHA-256 mismatch for {chunk_id}")
    return chunk


def canonical_label_bytes(rows: Sequence[Mapping[str, str]]) -> bytes:
    """Reproduce the frozen row-order-independent Phase 13A.2 label fingerprint."""
    serialized: list[str] = []
    for row in sorted(rows, key=lambda item: (item["question_id"], item["chunk_id"])):
        normalized = {field: str(row[field]) for field in LABEL_FIELDS}
        serialized.append(
            json.dumps(
                normalized,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )
    return ("\n".join(serialized) + "\n").encode("utf-8")


def verify_frozen_inputs() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    PreparedCorpus,
    dict[str, CanonicalChunk],
]:
    """Fail before retrieval if any frozen Phase 11/12/13 identity has drifted."""
    label_manifest = json.loads(LABEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_manifest_values = {
        "benchmark_version": BENCHMARK_VERSION,
        "label_protocol_version": LABEL_PROTOCOL,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        "question_count": QUESTION_COUNT,
        "passage_count": LABEL_COUNT,
        "label_dataset_sha256": LABEL_FINGERPRINT,
    }
    for key, expected in expected_manifest_values.items():
        if label_manifest.get(key) != expected:
            raise ValueError(f"frozen label manifest mismatch for {key}")

    questions = read_csv_rows(QUESTION_PATH)
    labels = read_csv_rows(LABEL_PATH)
    if len(questions) != QUESTION_COUNT or len(labels) != LABEL_COUNT:
        raise ValueError("frozen Phase 13 question/label counts changed")
    if not labels or tuple(labels[0]) != LABEL_FIELDS:
        raise ValueError("frozen AI label schema changed")
    question_ids = [row["question_id"] for row in questions]
    label_pairs = [(row["question_id"], row["chunk_id"]) for row in labels]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("retained question IDs are not unique")
    if len(label_pairs) != len(set(label_pairs)):
        raise ValueError("AI label question/chunk pairs are not unique")
    if set(question_ids) != {row["question_id"] for row in labels}:
        raise ValueError("retained questions and AI labels disagree")
    if Counter(row["topic"] for row in questions) != TOPIC_COUNTS:
        raise ValueError("frozen topic balance changed")
    if Counter(row["query_style"] for row in questions) != STYLE_COUNTS:
        raise ValueError("frozen query-style balance changed")
    for question_id, expected in EDITED_QUESTIONS.items():
        actual = next(row["question"] for row in questions if row["question_id"] == question_id)
        if actual != expected:
            raise ValueError(f"final edited wording changed for {question_id}")
    question_text = {row["question_id"]: row["question"] for row in questions}
    if any(row["effective_question"] != question_text[row["question_id"]] for row in labels):
        raise ValueError("AI labels do not use the final effective question text")
    if any(
        row["ai_labeler_protocol"] != LABEL_PROTOCOL
        or row["ai_benchmark_version"] != BENCHMARK_VERSION
        or row["ai_relevance_status"] != "COMPLETE"
        or row["ai_relevance_grade"] not in {"0", "1", "2"}
        for row in labels
    ):
        raise ValueError("AI label protocol, version, status, or grade changed")
    direct_questions = {
        row["question_id"] for row in labels if row["ai_relevance_grade"] == "2"
    }
    if direct_questions != set(question_ids):
        raise ValueError("every retained question must have frozen grade-2 evidence")
    fingerprint = hashlib.sha256(canonical_label_bytes(labels)).hexdigest()
    if fingerprint != LABEL_FINGERPRINT:
        raise ValueError("frozen AI label fingerprint changed")

    manifest = load_manifest()
    sources = validate_manifest(manifest)
    if len(canonical_documents(manifest)) != 3:
        raise ValueError("frozen corpus must contain exactly three canonical documents")
    if len(sources) != 3:
        raise ValueError("validated canonical document count changed")
    if frozen_corpus_identity() != (CORPUS_VERSION, CORPUS_FINGERPRINT):
        raise ValueError("frozen corpus identity changed")
    prepared = prepare_corpus()
    if len(prepared.ids) != EXPECTED_CHUNK_COUNT:
        raise ValueError("frozen canonical chunk count changed")
    catalog = chunk_catalog(prepared)
    for row in labels:
        canonical = get_chunk_by_id(
            row["chunk_id"],
            prepared,
            source_id=row["source_id"],
            filename=row["filename"],
            page=int(row["page"]),
        )
        if row["original_text"] != canonical.text:
            raise ValueError(f"AI label provenance changed for {row['chunk_id']}")

    if (
        RETRIEVAL_CONFIG_VERSION != "v3-retrieval-v1"
        or (BM25_K1, BM25_B, BM25_EPSILON) != (1.5, 0.75, 0.25)
        or TOKENIZER_VERSION != "nfkc-casefold-alphanumeric-v1"
        or (RRF_K, HYBRID_CANDIDATE_K) != (60, 20)
        or tuple(method_id for _name, method_id in SYSTEMS)
        != ("dense-minilm-v1", "bm25-okapi-v1", "hybrid-rrf-v1")
    ):
        raise ValueError("frozen retrieval configuration changed")
    return questions, labels, prepared, catalog


def construct_frozen_retrievers(prepared: PreparedCorpus) -> dict[str, Retriever]:
    dense = DenseRetriever()
    bm25 = BM25Retriever(prepared)
    return {
        "Dense": dense,
        "BM25": bm25,
        "Hybrid": HybridRetriever(dense, bm25),
    }


def _validate_result(result: RetrievedChunk, canonical: CanonicalChunk) -> None:
    if (
        result.source_id,
        result.filename,
        result.page,
        result.text,
    ) != (
        canonical.source_id,
        canonical.filename,
        canonical.page,
        canonical.text,
    ):
        raise ValueError(f"retrieved provenance mismatch for {result.chunk_id}")


def build_coverage_report(
    questions: Sequence[Mapping[str, str]],
    labels: Sequence[Mapping[str, str]],
    retrievers: Mapping[str, Retriever],
    catalog: Mapping[str, CanonicalChunk],
) -> dict:
    """Retrieve with query text only and aggregate missing labels by question/chunk."""
    if tuple(retrievers) != tuple(name for name, _method_id in SYSTEMS):
        raise ValueError("coverage requires exactly Dense, BM25, and Hybrid in frozen order")
    label_pairs = {(row["question_id"], row["chunk_id"]) for row in labels}
    top_five_pairs: set[tuple[str, str]] = set()
    gaps: dict[tuple[str, str], dict] = {}

    for question in questions:
        for system_name, expected_method_id in SYSTEMS:
            retriever = retrievers[system_name]
            if retriever.method_id != expected_method_id:
                raise ValueError(f"unexpected method ID for {system_name}")
            # Deliberate leakage firewall: ranking receives only final query text and k.
            results = retriever.retrieve(question["question"], TOP_K)
            if len(results) != TOP_K:
                raise ValueError(f"{system_name} returned {len(results)} rather than top {TOP_K}")
            result_ids = [result.chunk_id for result in results]
            if len(result_ids) != len(set(result_ids)):
                raise ValueError(f"{system_name} returned duplicate chunk IDs")
            for expected_rank, result in enumerate(results, start=1):
                if result.rank != expected_rank:
                    raise ValueError(f"{system_name} returned a non-canonical rank sequence")
                canonical = catalog.get(result.chunk_id)
                if canonical is None:
                    raise ValueError(f"retriever returned unknown chunk {result.chunk_id}")
                _validate_result(result, canonical)
                pair = (question["question_id"], result.chunk_id)
                top_five_pairs.add(pair)
                if pair in label_pairs:
                    continue
                gap = gaps.setdefault(
                    pair,
                    {
                        "question_id": question["question_id"],
                        "effective_question": question["question"],
                        "retriever": [],
                        "rank": {},
                        "method_id": {},
                        "chunk_id": canonical.chunk_id,
                        "source_id": canonical.source_id,
                        "filename": canonical.filename,
                        "page": canonical.page,
                        "corpus_version": CORPUS_VERSION,
                        "corpus_fingerprint": CORPUS_FINGERPRINT,
                        "passage_sha256": hashlib.sha256(
                            canonical.text.encode("utf-8")
                        ).hexdigest(),
                    },
                )
                gap["retriever"].append(system_name)
                gap["rank"][system_name] = expected_rank
                gap["method_id"][system_name] = expected_method_id

    ordered_gaps = sorted(gaps.values(), key=lambda row: (row["question_id"], row["chunk_id"]))
    for gap in ordered_gaps:
        gap["retriever"].sort(key=SYSTEM_ORDER.__getitem__)
        gap["rank"] = {name: gap["rank"][name] for name in gap["retriever"]}
        gap["method_id"] = {name: gap["method_id"][name] for name in gap["retriever"]}

    labeled_pairs = top_five_pairs & label_pairs
    status = "PASS" if not ordered_gaps else "FAIL"
    phase_status = "READY_FOR_EVALUATION" if status == "PASS" else "NEEDS_LABEL_COVERAGE_EXTENSION"
    affected_questions = sorted({row["question_id"] for row in ordered_gaps})
    return {
        "artifact_type": "phase13b_retrieval_label_coverage_preflight",
        "evaluation_version": EVALUATION_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "label_protocol": LABEL_PROTOCOL,
        "label_fingerprint": LABEL_FINGERPRINT,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        "question_count": len(questions),
        "top_k": TOP_K,
        "phase13b_status": phase_status,
        "coverage_gate": {
            "status": status,
            "total_unique_top5_pairs": len(top_five_pairs),
            "labeled_pairs": len(labeled_pairs),
            "unlabeled_pairs": len(ordered_gaps),
            "affected_question_count": len(affected_questions),
            "affected_question_ids": affected_questions,
        },
        "coverage_gaps": ordered_gaps,
        "official_retrieval_metrics_calculated": False,
        "missing_labels_assumed_grade_0": False,
    }


def require_complete_coverage(report: Mapping) -> None:
    """Guard every official metric path against unjudged top-five pairs."""
    gate = report.get("coverage_gate", {})
    if gate.get("status") != "PASS" or gate.get("unlabeled_pairs") != 0:
        raise IncompleteLabelCoverageError(
            "official retrieval metrics require zero unlabeled top-five question/chunk pairs"
        )


def main() -> int:
    questions, labels, prepared, catalog = verify_frozen_inputs()
    report = build_coverage_report(
        questions,
        labels,
        construct_frozen_retrievers(prepared),
        catalog,
    )
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    gate = report["coverage_gate"]
    print(f"Wrote {OUTPUT_PATH}")
    print(
        "Coverage: "
        f"{gate['labeled_pairs']}/{gate['total_unique_top5_pairs']} labeled; "
        f"{gate['unlabeled_pairs']} unlabeled"
    )
    print(f"PHASE13B_STATUS={report['phase13b_status']}")
    if gate["status"] != "PASS":
        print("NO OFFICIAL RETRIEVAL METRICS WERE CALCULATED")
        return 0
    require_complete_coverage(report)
    print("Coverage passed; the separately controlled full evaluation may proceed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
