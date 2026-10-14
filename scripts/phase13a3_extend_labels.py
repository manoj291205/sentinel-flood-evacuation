#!/usr/bin/env python3
"""Freeze the blind 19-row Phase 13A.3 relevance-label coverage extension.

No retrieval is run here. Passage text is reconstructed locally from the frozen corpus,
used only by the blind label function, and omitted from every generated tracked artifact.
"""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase13b_retrieval_preflight import (  # noqa: E402
    CORPUS_FINGERPRINT,
    CORPUS_VERSION,
    LABEL_FINGERPRINT as PARENT_LABEL_FINGERPRINT,
    LABEL_PATH as PARENT_LABEL_PATH,
    OUTPUT_PATH as GAP_PATH,
    RETRIEVAL_CONFIG_VERSION,
    canonical_label_bytes,
    get_chunk_by_id,
    read_csv_rows,
)
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
    RRF_K,
)


PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
QUESTION_PATH = PHASE13 / "retained_question_review.csv"
HUMAN_REVIEW_PATH = PHASE13 / "retained_passage_review.csv"
EXTENSION_PATH = PHASE13 / "ai_assisted_passage_label_extension.csv"
EXTENDED_LABEL_PATH = PHASE13 / "ai_assisted_passage_labels_extended.csv"
EXTENDED_MANIFEST_PATH = PHASE13 / "ai_assisted_label_manifest_extended.json"
CONSISTENCY_PATH = PHASE13 / "ai_label_extension_consistency.csv"

EXTENSION_VERSION = "v3-retrieval-label-coverage-extension-v1"
PARENT_BENCHMARK_VERSION = "v3-retrieval-benchmark-ai-assisted-v1"
EXTENDED_BENCHMARK_VERSION = "v3-retrieval-benchmark-ai-assisted-v2"
LABEL_PROTOCOL = "v3-ai-relevance-labeler-v1"
PREFLIGHT_COMMIT = "b2435a5d8d8ea98c4702ba67601c72dbc13fd5ce"
GAP_ARTIFACT_SHA256 = "5677186598e18e6021aa35df27c9f0524c71dae249432814f856879324107d09"
PARENT_LABEL_FILE_SHA256 = "9b402cbfead067a62f9c15a2b546c7dc367c2e8b96e8c3fcac7d7fc2f29ec034"
HUMAN_REVIEW_FILE_SHA256 = "042155e9be1174c538d17132da3b9c6fbccce2b97d5a23b8f1aa8b805e119b29"
EXPECTED_GAP_COUNT = 19
EXPECTED_AFFECTED_QUESTIONS = ("Q003", "Q008", "Q016", "Q034")

BLIND_FIELDS = (
    "question_id",
    "effective_question",
    "chunk_id",
    "source_id",
    "filename",
    "page",
    "original_text",
)
FORBIDDEN_BLIND_FRAGMENTS = (
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
EXTENSION_FIELDS = (
    "question_id",
    "effective_question",
    "chunk_id",
    "source_id",
    "filename",
    "page",
    "ai_relevance_grade",
    "ai_relevance_status",
    "ai_relevance_rationale",
    "ai_label_confidence",
    "ai_labeler_protocol",
    "source_passage_sha256",
    "extension_version",
)
COMBINED_FIELDS = (
    "question_id",
    "effective_question",
    "topic",
    "query_style",
    "chunk_id",
    "source_id",
    "filename",
    "page",
    "source_passage_sha256",
    "ai_relevance_grade",
    "ai_relevance_status",
    "ai_relevance_rationale",
    "ai_label_confidence",
    "ai_labeler_protocol",
    "benchmark_version",
    "label_origin",
    "label_origin_version",
)
CONSISTENCY_FIELDS = (
    "question_id",
    "chunk_id",
    "first_grade",
    "second_grade",
    "agreement",
    "absolute_grade_difference",
    "selection_sha256",
)


def _pair(question_id: str, source_id: str, location: str) -> tuple[str, str]:
    return question_id, f"{source_id}-{location}"


FLOOD = "ndma-flood-guidelines-2008"
PLAN = "ndma-national-disaster-management-plan-2019"
SHELTER = "ndma-temporary-shelters-2019"

# These 19 judgments were made from the neutral question/passage-only view. The tuple is
# (grade, concise rationale, confidence). Retriever identity and rank are not inputs.
JUDGMENTS: dict[tuple[str, str], tuple[int, str, str]] = {
    _pair("Q003", FLOOD, "p62-c1"): (
        0,
        "The passage explains flood-safe road and embankment design, not where shelters or relief centres should be located.",
        "MEDIUM",
    ),
    _pair("Q003", PLAN, "p115-c2"): (
        0,
        "The passage concerns disability-accessible temporary facilities and does not address flood-safe shelter siting.",
        "MEDIUM",
    ),
    _pair("Q003", PLAN, "p149-c0"): (
        1,
        "The passage identifies shelter design in flood-prone areas as a research need but gives no location criterion for remaining functional.",
        "MEDIUM",
    ),
    _pair("Q003", SHELTER, "p48-c2"): (
        1,
        "The passage discusses weather-resistant shelter construction and location preference, but not where flood shelters should be sited.",
        "MEDIUM",
    ),
    _pair("Q008", FLOOD, "p101-c0"): (
        0,
        "The passage calls for flash-flood warning systems but does not describe how warning information should be presented to communities.",
        "MEDIUM",
    ),
    _pair("Q008", FLOOD, "p151-c0"): (
        1,
        "The passage describes public notices, individual notices, and displayed records for flood zoning, offering related dissemination context rather than warning guidance.",
        "MEDIUM",
    ),
    _pair("Q008", FLOOD, "p22-c3"): (
        0,
        "The passage mentions flood forecasting and warning as preparedness measures but gives no community-facing presentation guidance.",
        "MEDIUM",
    ),
    _pair("Q008", FLOOD, "p64-c3"): (
        1,
        "The passage identifies timing, extent, and duration as information supplied by flood forecasting, but not how communities should receive it.",
        "MEDIUM",
    ),
    _pair("Q008", FLOOD, "p89-c1"): (
        1,
        "The passage links warning indicators and stakeholder dialogue to evacuation, but does not specify how warnings should be presented to affected communities.",
        "MEDIUM",
    ),
    _pair("Q008", PLAN, "p237-c1"): (
        2,
        "The passage directs authorities to use information materials and broad media dissemination to communicate risk information and early warnings to at-risk communities.",
        "HIGH",
    ),
    _pair("Q008", PLAN, "p85-c1"): (
        0,
        "The passage describes livestock-emergency guidance and does not address presentation of flood warnings to communities.",
        "HIGH",
    ),
    _pair("Q008", SHELTER, "p44-c2"): (
        0,
        "The passage concerns shelter-kit training and support, not flood-warning information or its presentation.",
        "HIGH",
    ),
    _pair("Q008", SHELTER, "p45-c1"): (
        0,
        "The passage concerns tented-camp planning and construction support, not community flood-warning communication.",
        "HIGH",
    ),
    _pair("Q016", PLAN, "p306-c0"): (
        0,
        "The passage covers telecommunications interoperability and cultural-site evacuation planning, not safe patient movement.",
        "HIGH",
    ),
    _pair("Q016", PLAN, "p310-c1"): (
        1,
        "The passage identifies evacuation assessment, transport resources, coordination, and procedures generally, but not patient-specific movement requirements.",
        "MEDIUM",
    ),
    _pair("Q016", PLAN, "p310-c2"): (
        1,
        "The passage mentions response resources and evacuation procedures for people and animals but lacks patient-specific personnel and equipment guidance.",
        "MEDIUM",
    ),
    _pair("Q016", PLAN, "p317-c0"): (
        2,
        "The passage specifies trained doctors and paramedics, mobile medical units, operating facilities, power, and medicines needed for emergency patient care.",
        "MEDIUM",
    ),
    _pair("Q016", PLAN, "p322-c0"): (
        2,
        "The passage identifies railway medical staff and mobile rail ambulances for shifting and treating injured patients.",
        "HIGH",
    ),
    _pair("Q034", SHELTER, "p33-c2"): (
        1,
        "The passage explains that water, sanitation, and other essential services must be provided outside tent living quarters, but not what to do after disruption.",
        "MEDIUM",
    ),
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_rows_bytes(
    rows: Sequence[Mapping[str, str]], fields: Sequence[str]
) -> bytes:
    serialized: list[str] = []
    for row in sorted(rows, key=lambda item: (item["question_id"], item["chunk_id"])):
        normalized = {field: str(row[field]) for field in fields}
        serialized.append(
            json.dumps(
                normalized,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
        )
    return ("\n".join(serialized) + "\n").encode("utf-8")


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def load_and_verify_gaps() -> list[dict]:
    if file_sha256(GAP_PATH) != GAP_ARTIFACT_SHA256:
        raise ValueError("Phase 13B gap artifact differs from the frozen preflight commit")
    artifact = json.loads(GAP_PATH.read_text(encoding="utf-8"))
    gate = artifact.get("coverage_gate", {})
    if (
        artifact.get("phase13b_status") != "NEEDS_LABEL_COVERAGE_EXTENSION"
        or gate.get("total_unique_top5_pairs") != 434
        or gate.get("labeled_pairs") != 415
        or gate.get("unlabeled_pairs") != EXPECTED_GAP_COUNT
        or gate.get("affected_question_ids") != list(EXPECTED_AFFECTED_QUESTIONS)
        or artifact.get("official_retrieval_metrics_calculated") is not False
    ):
        raise ValueError("Phase 13B frozen coverage result changed")
    gaps = artifact.get("coverage_gaps", [])
    pairs = [(row["question_id"], row["chunk_id"]) for row in gaps]
    if len(gaps) != EXPECTED_GAP_COUNT or len(pairs) != len(set(pairs)):
        raise ValueError("coverage extension requires exactly 19 unique frozen pairs")
    if tuple(sorted({row["question_id"] for row in gaps})) != EXPECTED_AFFECTED_QUESTIONS:
        raise ValueError("coverage extension affected question IDs changed")
    if set(pairs) != set(JUDGMENTS):
        raise ValueError("declared blind judgments do not match the complete frozen gap set")
    return gaps


def build_blind_rows(gaps: Sequence[Mapping], prepared: PreparedCorpus) -> list[dict]:
    rows: list[dict] = []
    for gap in gaps:
        chunk = get_chunk_by_id(
            gap["chunk_id"],
            prepared,
            source_id=gap["source_id"],
            filename=gap["filename"],
            page=int(gap["page"]),
            passage_sha256=gap["passage_sha256"],
        )
        rows.append(
            {
                "question_id": gap["question_id"],
                "effective_question": gap["effective_question"],
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "filename": chunk.filename,
                "page": chunk.page,
                "original_text": chunk.text,
            }
        )
    rows.sort(key=lambda row: (row["question_id"], row["chunk_id"]))
    if any(tuple(row) != BLIND_FIELDS for row in rows):
        raise ValueError("blind extension input schema changed")
    return rows


def judge_blind_pair(row: Mapping) -> tuple[int, str, str]:
    """Apply the frozen protocol to one question/passage-only input."""
    if tuple(row) != BLIND_FIELDS:
        raise ValueError("labeler received fields outside the frozen blind schema")
    if any(
        any(fragment in field.casefold() for fragment in FORBIDDEN_BLIND_FRAGMENTS)
        for field in row
    ):
        raise ValueError("labeler received forbidden retrieval or prior-label metadata")
    judgment = JUDGMENTS.get((str(row["question_id"]), str(row["chunk_id"])))
    if judgment is None:
        raise ValueError("labeler received a pair outside the frozen extension")
    grade, rationale, confidence = judgment
    if grade not in {0, 1, 2} or confidence not in {"HIGH", "MEDIUM", "LOW"}:
        raise ValueError("invalid frozen extension judgment")
    if len(rationale.split()) < 8 or rationale.strip() in {"Relevant.", "Relevant to the question."}:
        raise ValueError("extension rationale is not sufficiently specific")
    return judgment


def extension_row(blind: Mapping) -> dict[str, str]:
    grade, rationale, confidence = judge_blind_pair(blind)
    passage_hash = hashlib.sha256(str(blind["original_text"]).encode("utf-8")).hexdigest()
    return {
        "question_id": str(blind["question_id"]),
        "effective_question": str(blind["effective_question"]),
        "chunk_id": str(blind["chunk_id"]),
        "source_id": str(blind["source_id"]),
        "filename": str(blind["filename"]),
        "page": str(blind["page"]),
        "ai_relevance_grade": str(grade),
        "ai_relevance_status": "COMPLETE",
        "ai_relevance_rationale": rationale,
        "ai_label_confidence": confidence,
        "ai_labeler_protocol": LABEL_PROTOCOL,
        "source_passage_sha256": passage_hash,
        "extension_version": EXTENSION_VERSION,
    }


def consistency_selection(blind_rows: Sequence[Mapping]) -> list[Mapping]:
    def digest(row: Mapping) -> str:
        value = f"{row['question_id']}|{row['chunk_id']}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    return sorted(blind_rows, key=digest)[:5]


def build_consistency_rows(blind_rows: Sequence[Mapping]) -> list[dict[str, str]]:
    # The second pass is completed first and receives only the blind input rows.
    second_pass = {
        (str(row["question_id"]), str(row["chunk_id"])): judge_blind_pair(dict(row))[0]
        for row in consistency_selection(blind_rows)
    }
    rows: list[dict[str, str]] = []
    for blind in consistency_selection(blind_rows):
        pair = (str(blind["question_id"]), str(blind["chunk_id"]))
        first_grade = judge_blind_pair(dict(blind))[0]
        second_grade = second_pass[pair]
        selection_digest = hashlib.sha256(f"{pair[0]}|{pair[1]}".encode("utf-8")).hexdigest()
        rows.append(
            {
                "question_id": pair[0],
                "chunk_id": pair[1],
                "first_grade": str(first_grade),
                "second_grade": str(second_grade),
                "agreement": str(first_grade == second_grade).upper(),
                "absolute_grade_difference": str(abs(first_grade - second_grade)),
                "selection_sha256": selection_digest,
            }
        )
    return rows


def build_combined_rows(
    parent_rows: Sequence[Mapping[str, str]],
    extension_rows: Sequence[Mapping[str, str]],
    question_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    question_metadata = {row["question_id"]: row for row in question_rows}
    combined: list[dict[str, str]] = []
    for row in parent_rows:
        combined.append(
            {
                "question_id": row["question_id"],
                "effective_question": row["effective_question"],
                "topic": row["topic"],
                "query_style": row["query_style"],
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "filename": row["filename"],
                "page": row["page"],
                "source_passage_sha256": hashlib.sha256(
                    row["original_text"].encode("utf-8")
                ).hexdigest(),
                "ai_relevance_grade": row["ai_relevance_grade"],
                "ai_relevance_status": row["ai_relevance_status"],
                "ai_relevance_rationale": row["ai_relevance_rationale"],
                "ai_label_confidence": row["ai_label_confidence"],
                "ai_labeler_protocol": row["ai_labeler_protocol"],
                "benchmark_version": EXTENDED_BENCHMARK_VERSION,
                "label_origin": "BASE_V1",
                "label_origin_version": PARENT_BENCHMARK_VERSION,
            }
        )
    for row in extension_rows:
        question = question_metadata[row["question_id"]]
        combined.append(
            {
                "question_id": row["question_id"],
                "effective_question": row["effective_question"],
                "topic": question["topic"],
                "query_style": question["query_style"],
                "chunk_id": row["chunk_id"],
                "source_id": row["source_id"],
                "filename": row["filename"],
                "page": row["page"],
                "source_passage_sha256": row["source_passage_sha256"],
                "ai_relevance_grade": row["ai_relevance_grade"],
                "ai_relevance_status": row["ai_relevance_status"],
                "ai_relevance_rationale": row["ai_relevance_rationale"],
                "ai_label_confidence": row["ai_label_confidence"],
                "ai_labeler_protocol": row["ai_labeler_protocol"],
                "benchmark_version": EXTENDED_BENCHMARK_VERSION,
                "label_origin": "COVERAGE_EXTENSION",
                "label_origin_version": EXTENSION_VERSION,
            }
        )
    combined.sort(key=lambda row: (row["question_id"], row["chunk_id"]))
    keys = [(row["question_id"], row["chunk_id"]) for row in combined]
    if len(combined) != 504 or len(keys) != len(set(keys)):
        raise ValueError("extended benchmark must contain 504 unique question/chunk pairs")
    return combined


def main() -> int:
    gaps = load_and_verify_gaps()
    if file_sha256(PARENT_LABEL_PATH) != PARENT_LABEL_FILE_SHA256:
        raise ValueError("original 485-row label artifact changed")
    if file_sha256(HUMAN_REVIEW_PATH) != HUMAN_REVIEW_FILE_SHA256:
        raise ValueError("retained human-review fields changed")
    parent_rows = read_csv_rows(PARENT_LABEL_PATH)
    if len(parent_rows) != 485:
        raise ValueError("parent label row count changed")
    if hashlib.sha256(canonical_label_bytes(parent_rows)).hexdigest() != PARENT_LABEL_FINGERPRINT:
        raise ValueError("original Phase 13A.2 label fingerprint changed")

    prepared = prepare_corpus()
    if len(prepared.ids) != EXPECTED_CHUNK_COUNT:
        raise ValueError("frozen corpus chunk count changed")
    blind_rows = build_blind_rows(gaps, prepared)
    extension_rows = [extension_row(row) for row in blind_rows]
    extension_pairs = {(row["question_id"], row["chunk_id"]) for row in extension_rows}
    gap_pairs = {(row["question_id"], row["chunk_id"]) for row in gaps}
    if len(extension_rows) != 19 or extension_pairs != gap_pairs:
        raise ValueError("extension labels must cover all and only the frozen 19 gaps")

    question_rows = read_csv_rows(QUESTION_PATH)
    combined = build_combined_rows(parent_rows, extension_rows, question_rows)
    combined_pairs = {(row["question_id"], row["chunk_id"]) for row in combined}
    if not extension_pairs <= combined_pairs:
        raise ValueError("extended benchmark does not contain every frozen gap pair")
    direct_questions = {
        row["question_id"] for row in combined if row["ai_relevance_grade"] == "2"
    }
    if len(direct_questions) != 45:
        raise ValueError("all 45 questions must retain at least one grade-2 passage")

    consistency_rows = build_consistency_rows(blind_rows)
    if len(consistency_rows) != 5:
        raise ValueError("extension consistency diagnostic requires exactly five pairs")
    exact_agreement = sum(row["agreement"] == "TRUE" for row in consistency_rows) / 5
    disagreement_count = sum(row["agreement"] != "TRUE" for row in consistency_rows)

    write_csv(EXTENSION_PATH, EXTENSION_FIELDS, extension_rows)
    write_csv(EXTENDED_LABEL_PATH, COMBINED_FIELDS, combined)
    write_csv(CONSISTENCY_PATH, CONSISTENCY_FIELDS, consistency_rows)

    extension_fingerprint = hashlib.sha256(
        canonical_rows_bytes(extension_rows, EXTENSION_FIELDS)
    ).hexdigest()
    extended_fingerprint = hashlib.sha256(
        canonical_rows_bytes(combined, COMBINED_FIELDS)
    ).hexdigest()
    grade_counts = Counter(row["ai_relevance_grade"] for row in combined)
    confidence_counts = Counter(row["ai_label_confidence"] for row in combined)
    extension_grade_counts = Counter(row["ai_relevance_grade"] for row in extension_rows)
    extension_confidence_counts = Counter(row["ai_label_confidence"] for row in extension_rows)

    judge_source = inspect.getsource(judge_blind_pair)
    if any(fragment in judge_source for fragment in ("retriever", "rank", "score")):
        raise ValueError("blind judge implementation references retrieval metadata")

    manifest = {
        "benchmark_version": EXTENDED_BENCHMARK_VERSION,
        "parent_benchmark_version": PARENT_BENCHMARK_VERSION,
        "extension_version": EXTENSION_VERSION,
        "label_protocol": LABEL_PROTOCOL,
        "parent_label_fingerprint": PARENT_LABEL_FINGERPRINT,
        "extension_label_fingerprint": extension_fingerprint,
        "extended_label_fingerprint": extended_fingerprint,
        "base_rows": 485,
        "extension_rows": 19,
        "total_rows": 504,
        "questions": 45,
        "affected_extension_questions": list(EXPECTED_AFFECTED_QUESTIONS),
        "grade_counts": {grade: grade_counts[grade] for grade in ("0", "1", "2")},
        "confidence_counts": {
            value: confidence_counts[value] for value in ("HIGH", "MEDIUM", "LOW")
        },
        "extension_grade_counts": {
            grade: extension_grade_counts[grade] for grade in ("0", "1", "2")
        },
        "extension_confidence_counts": {
            value: extension_confidence_counts[value]
            for value in ("HIGH", "MEDIUM", "LOW")
        },
        "coverage_reason": "FINAL_EDITED_QUERY_TOP5_COVERAGE",
        "coverage_verification": {
            "preflight_unique_top5_pairs": 434,
            "base_labeled_preflight_pairs_preserved": 415,
            "extension_gap_pairs_covered": 19,
            "labeled_after_extension": 434,
            "unlabeled_after_extension": 0,
            "status": "PASS",
            "method": "Frozen preflight counts plus unchanged parent fingerprint and complete disjoint gap-set inclusion; retrieval was not rerun.",
        },
        "questions_with_direct_evidence": 45,
        "questions_without_direct_evidence": 0,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "canonical_chunks": EXPECTED_CHUNK_COUNT,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        "retrieval_methods": [DENSE_METHOD_ID, BM25_METHOD_ID, HYBRID_METHOD_ID],
        "retrieval_parameters": {
            "bm25_k1": BM25_K1,
            "bm25_b": BM25_B,
            "bm25_epsilon": BM25_EPSILON,
            "rrf_k": RRF_K,
            "hybrid_candidate_k": HYBRID_CANDIDATE_K,
        },
        "preflight_commit": PREFLIGHT_COMMIT,
        "gap_artifact_sha256": GAP_ARTIFACT_SHA256,
        "parent_label_file_sha256": PARENT_LABEL_FILE_SHA256,
        "fingerprint_procedure": {
            "fields_included": list(COMBINED_FIELDS),
            "canonical_field_order": list(COMBINED_FIELDS),
            "row_sort": ["question_id", "chunk_id"],
            "serialization": "Each field coerced to its CSV string; JSON object with sorted keys, compact separators, UTF-8, ensure_ascii=false.",
            "newline_rule": "Lexicographically ordered serialized rows joined by LF with one final LF.",
            "hash": "SHA-256 over the resulting bytes.",
        },
        "passage_text_tracked_in_new_artifacts": False,
        "passage_reconstruction": "Local frozen corpus lookup by chunk_id with source, filename, page, and SHA-256 verification.",
        "blind_label_fields": list(BLIND_FIELDS),
        "blind_order": ["question_id", "chunk_id"],
        "consistency_diagnostic": {
            "pairs": 5,
            "selection": "First five by SHA-256(question_id + '|' + chunk_id).",
            "exact_agreement": exact_agreement,
            "disagreements": disagreement_count,
            "absolute_grade_differences": [
                int(row["absolute_grade_difference"]) for row in consistency_rows
            ],
            "weighted_kappa": "NOT_REPORTED_TINY_DIAGNOSTIC",
            "reconciliation": "NONE; first-pass extension labels remain authoritative",
        },
        "human_passage_labels_created": 0,
        "independent_human_annotation": False,
        "benchmark_characterization": "AI-assisted relevance benchmark",
        "official_retrieval_metrics_calculated": False,
        "full_phase13b_evaluation_started": False,
        "reranker_added": False,
    }
    EXTENDED_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Extension rows: {len(extension_rows)}")
    print(f"Extension grades: {dict(sorted(extension_grade_counts.items()))}")
    print(f"Extension confidence: {dict(sorted(extension_confidence_counts.items()))}")
    print(f"Extended rows: {len(combined)}")
    print(f"Extended fingerprint: {extended_fingerprint}")
    print("Frozen preflight label coverage: 434/434; presence only")
    print("NO OFFICIAL RETRIEVAL QUALITY METRICS CALCULATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
