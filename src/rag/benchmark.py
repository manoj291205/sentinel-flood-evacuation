"""Phase 13A benchmark preparation, review safety, and synthetic metric helpers.

This module prepares machine proposals for human review. It deliberately contains no
path that turns machine suggestions into human labels or computes official corpus
metrics before review is complete.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .ingest import PreparedCorpus
from .retrieve import RetrievedChunk, Retriever

BENCHMARK_SPEC_VERSION = "v3-retrieval-benchmark-spec-v1"
CANDIDATE_BENCHMARK_VERSION = "v3-retrieval-benchmark-candidate-v1"
FUTURE_GOLD_VERSION = "v3-retrieval-benchmark-gold-v1"
TARGET_ACCEPTED_QUESTIONS = 45
TARGET_PER_TOPIC = 9
TARGET_PER_STYLE = 15
CANDIDATE_MINIMUM = 60
POOL_DEPTH = 10
POOL_ALWAYS_KEEP_DEPTH = 5
POOL_CAP = 18
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 131_313

TOPICS = (
    "flood_management",
    "evacuation_movement",
    "temporary_shelters_relief_camps",
    "vulnerable_groups_accessibility",
    "logistics_transport_coordination",
)
QUERY_STYLES = ("LEXICAL", "SEMANTIC_PARAPHRASE", "OPERATIONAL_TASK")
HUMAN_QUESTION_STATUSES = ("ACCEPT", "EDIT", "REJECT")
HUMAN_RELEVANCE_GRADES = (0, 1, 2)


@dataclass(frozen=True)
class CanonicalChunk:
    chunk_id: str
    source_id: str
    filename: str
    page: int
    text: str


def chunk_catalog(prepared: PreparedCorpus) -> dict[str, CanonicalChunk]:
    if not (len(prepared.ids) == len(prepared.documents) == len(prepared.metadatas)):
        raise ValueError("prepared corpus arrays have inconsistent lengths")
    catalog: dict[str, CanonicalChunk] = {}
    for chunk_id, text, metadata in zip(
        prepared.ids, prepared.documents, prepared.metadatas
    ):
        if chunk_id in catalog:
            raise ValueError(f"duplicate canonical chunk ID: {chunk_id}")
        catalog[chunk_id] = CanonicalChunk(
            chunk_id=chunk_id,
            source_id=str(metadata["source_id"]),
            filename=str(metadata["source_document"]),
            page=int(metadata["page"]),
            text=text,
        )
    return catalog


def validate_candidate_manifest(manifest: dict, catalog: Mapping[str, CanonicalChunk]) -> None:
    if manifest.get("benchmark_spec_version") != BENCHMARK_SPEC_VERSION:
        raise ValueError("unexpected benchmark specification version")
    if manifest.get("candidate_benchmark_version") != CANDIDATE_BENCHMARK_VERSION:
        raise ValueError("unexpected candidate benchmark version")
    candidates = manifest.get("candidates", [])
    if len(candidates) < CANDIDATE_MINIMUM:
        raise ValueError("candidate benchmark requires at least 60 questions")
    ids = [item["candidate_question_id"] for item in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate question IDs must be unique")
    normalized_questions = [" ".join(item["question"].casefold().split()) for item in candidates]
    if len(normalized_questions) != len(set(normalized_questions)):
        raise ValueError("candidate questions must be unique after normalization")
    if set(item["primary_topic"] for item in candidates) != set(TOPICS):
        raise ValueError("candidate questions must represent all frozen topics")
    if set(item["query_style"] for item in candidates) != set(QUERY_STYLES):
        raise ValueError("candidate questions must represent all frozen query styles")
    for item in candidates:
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"empty question: {item['candidate_question_id']}")
        if item["primary_topic"] not in TOPICS or item["query_style"] not in QUERY_STYLES:
            raise ValueError(f"invalid balance category: {item['candidate_question_id']}")
        seed = catalog.get(item.get("machine_proposed_chunk_id"))
        if seed is None:
            raise ValueError(f"unknown seed chunk: {item['candidate_question_id']}")
        expected = (
            seed.source_id,
            seed.filename,
            seed.page,
        )
        actual = (
            item.get("machine_proposed_source_id"),
            item.get("machine_proposed_filename"),
            item.get("machine_proposed_page"),
        )
        if actual != expected:
            raise ValueError(f"seed provenance mismatch: {item['candidate_question_id']}")
        excerpt = item.get("machine_proposed_supporting_excerpt", "")
        if not excerpt or excerpt not in seed.text:
            raise ValueError(f"seed excerpt is not verbatim: {item['candidate_question_id']}")
        if not str(item.get("machine_explanation", "")).strip():
            raise ValueError(f"missing machine explanation: {item['candidate_question_id']}")


def _validate_retrieved_chunk(result: RetrievedChunk, canonical: CanonicalChunk) -> None:
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
        raise ValueError(f"retrieval provenance mismatch for {result.chunk_id}")


def pool_question(
    question: dict,
    catalog: Mapping[str, CanonicalChunk],
    retrievers: Mapping[str, Retriever],
) -> list[dict]:
    """Apply the frozen top-10 union/reduction rule and force seed inclusion."""
    expected_names = {"dense", "bm25", "hybrid"}
    if set(retrievers) != expected_names:
        raise ValueError(f"retrievers must be exactly {sorted(expected_names)}")
    pooled: dict[str, dict] = {}
    for name in ("dense", "bm25", "hybrid"):
        results = retrievers[name].retrieve(question["question"], POOL_DEPTH)
        seen: set[str] = set()
        for rank, result in enumerate(results, start=1):
            if result.chunk_id in seen:
                raise ValueError(f"duplicate {name} pool result: {result.chunk_id}")
            seen.add(result.chunk_id)
            canonical = catalog.get(result.chunk_id)
            if canonical is None:
                raise ValueError(f"retriever returned non-canonical chunk: {result.chunk_id}")
            _validate_retrieved_chunk(result, canonical)
            entry = pooled.setdefault(
                result.chunk_id,
                {
                    "chunk_id": canonical.chunk_id,
                    "source_id": canonical.source_id,
                    "filename": canonical.filename,
                    "page": canonical.page,
                    "excerpt": canonical.text,
                    "dense_rank": None,
                    "bm25_rank": None,
                    "hybrid_rank": None,
                    "machine_seed_evidence": False,
                    "machine_suggested_grade": "",
                },
            )
            entry[f"{name}_rank"] = rank

    seed_id = question["machine_proposed_chunk_id"]
    seed = catalog[seed_id]
    seed_entry = pooled.setdefault(
        seed_id,
        {
            "chunk_id": seed.chunk_id,
            "source_id": seed.source_id,
            "filename": seed.filename,
            "page": seed.page,
            "excerpt": seed.text,
            "dense_rank": None,
            "bm25_rank": None,
            "hybrid_rank": None,
            "machine_seed_evidence": False,
            "machine_suggested_grade": "",
        },
    )
    seed_entry["machine_seed_evidence"] = True
    seed_entry["machine_suggested_grade"] = "2"

    eligible: list[dict] = []
    for entry in pooled.values():
        ranks = [entry[f"{name}_rank"] for name in ("dense", "bm25", "hybrid")]
        appearances = sum(rank is not None for rank in ranks)
        top_five = any(rank is not None and rank <= POOL_ALWAYS_KEEP_DEPTH for rank in ranks)
        if entry["machine_seed_evidence"] or appearances >= 2 or top_five:
            entry["retrieved_by"] = [
                name for name in ("dense", "bm25", "hybrid")
                if entry[f"{name}_rank"] is not None
            ]
            entry["best_pooled_rank"] = min(
                (rank for rank in ranks if rank is not None), default=POOL_DEPTH + 1
            )
            eligible.append(entry)
    eligible.sort(
        key=lambda entry: (
            0 if entry["machine_seed_evidence"] else 1,
            entry["best_pooled_rank"],
            entry["chunk_id"],
        )
    )
    selected = eligible[:POOL_CAP]
    if seed_id not in {entry["chunk_id"] for entry in selected}:
        raise AssertionError("frozen pool rule failed to retain seed evidence")
    if len({entry["chunk_id"] for entry in selected}) != len(selected):
        raise AssertionError("review pool contains duplicate chunks")
    return selected


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def assert_phase13b_ready(
    question_rows: Sequence[Mapping[str, str]],
    passage_rows: Sequence[Mapping[str, str]],
) -> list[str]:
    """Return accepted IDs or fail; never infer/edit/fill a human judgment."""
    accepted: list[str] = []
    accepted_rows: list[Mapping[str, str]] = []
    for row in question_rows:
        status = row.get("human_question_status", "")
        if status == "PENDING" or status == "":
            raise ValueError("human question review is incomplete")
        if status not in HUMAN_QUESTION_STATUSES:
            raise ValueError(f"invalid human question status: {status!r}")
        if status == "EDIT" and not row.get("human_edited_question", "").strip():
            raise ValueError("EDIT requires a human-edited question")
        if status in {"ACCEPT", "EDIT"}:
            accepted.append(row["question_id"])
            accepted_rows.append(row)
    if len(accepted) != TARGET_ACCEPTED_QUESTIONS:
        raise ValueError("exactly 45 human-accepted/edited questions are required")
    topic_counts = Counter(row["topic"] for row in accepted_rows)
    style_counts = Counter(row["query_style"] for row in accepted_rows)
    if any(topic_counts[topic] != TARGET_PER_TOPIC for topic in TOPICS):
        raise ValueError("human-retained questions must include exactly nine per topic")
    if any(style_counts[style] != TARGET_PER_STYLE for style in QUERY_STYLES):
        raise ValueError("human-retained questions must include exactly fifteen per query style")

    by_question: dict[str, list[int]] = {question_id: [] for question_id in accepted}
    direct_sources: dict[str, set[str]] = {question_id: set() for question_id in accepted}
    for row in passage_rows:
        if row["question_id"] not in by_question:
            continue
        status = row.get("human_review_status", "")
        grade_text = row.get("human_grade", "").strip()
        if status != "COMPLETE" or grade_text == "":
            raise ValueError("human passage review is incomplete")
        try:
            grade = int(grade_text)
        except ValueError as exc:
            raise ValueError(f"invalid human relevance grade: {grade_text!r}") from exc
        if grade not in HUMAN_RELEVANCE_GRADES:
            raise ValueError(f"invalid human relevance grade: {grade}")
        by_question[row["question_id"]].append(grade)
        if grade == 2:
            direct_sources[row["question_id"]].add(row["source_id"])
    if any(2 not in grades for grades in by_question.values()):
        raise ValueError("every retained question requires a human grade-2 passage")
    source_counts = Counter(
        source_id for sources in direct_sources.values() for source_id in sources
    )
    if len(source_counts) < 3 or any(count < 8 for count in source_counts.values()):
        raise ValueError("each canonical source requires grade-2 evidence for eight questions")
    if sum(len(sources) >= 2 for sources in direct_sources.values()) < 8:
        raise ValueError("at least eight retained questions require multi-source grade-2 evidence")
    return accepted


def select_consistency_questions(question_ids: Sequence[str]) -> list[str]:
    if len(question_ids) < 10:
        raise ValueError("consistency audit requires at least ten accepted questions")
    rng = random.Random(BOOTSTRAP_SEED)
    return sorted(rng.sample(sorted(question_ids), 10))


def direct_hit_at_k(ranked_ids: Sequence[str], grades: Mapping[str, int], k: int) -> int:
    return int(any(grades.get(chunk_id) == 2 for chunk_id in ranked_ids[:k]))


def reciprocal_rank_at_k(
    ranked_ids: Sequence[str], grades: Mapping[str, int], k: int
) -> float:
    for rank, chunk_id in enumerate(ranked_ids[:k], start=1):
        if grades.get(chunk_id) == 2:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], grades: Mapping[str, int], k: int) -> float:
    def dcg(values: Iterable[int]) -> float:
        return sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(values, 1))

    actual = [grades.get(chunk_id, 0) for chunk_id in ranked_ids[:k]]
    ideal = sorted(grades.values(), reverse=True)[:k]
    ideal_score = dcg(ideal)
    return dcg(actual) / ideal_score if ideal_score else 0.0


def pooled_recall_at_k(
    ranked_ids: Sequence[str], grades: Mapping[str, int], k: int
) -> float:
    gold = {chunk_id for chunk_id, grade in grades.items() if grade == 2}
    if not gold:
        raise ValueError("pooled recall requires at least one grade-2 chunk")
    return len(gold & set(ranked_ids[:k])) / len(gold)


def paired_bootstrap_difference(
    treatment: Sequence[float],
    baseline: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, tuple[float, float]]:
    """Question-level paired percentile bootstrap for synthetic tests/future Phase 13B."""
    if len(treatment) != len(baseline) or not treatment:
        raise ValueError("paired non-empty question-level samples are required")
    differences = [left - right for left, right in zip(treatment, baseline)]
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        indices = [rng.randrange(len(differences)) for _ in differences]
        draws.append(sum(differences[index] for index in indices) / len(indices))
    draws.sort()
    lower = draws[int(0.025 * (resamples - 1))]
    upper = draws[int(0.975 * (resamples - 1))]
    return sum(differences) / len(differences), (lower, upper)


def stable_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate_manifest(path: Path) -> dict:
    return json.loads(path.read_text())
