#!/usr/bin/env python3
"""Apply the project owner's adopted Phase 13A.1 question decisions.

This script deliberately does not assign passage relevance or calculate retrieval
metrics. It derives a retained review set from the frozen Phase 13A artifacts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE13_DIR = PROJECT_ROOT / "data" / "eval_v3" / "phase13"
CANDIDATE_MANIFEST_PATH = PHASE13_DIR / "candidate_question_manifest.json"
QUESTION_REVIEW_PATH = PHASE13_DIR / "question_review.csv"
ORIGINAL_PASSAGE_REVIEW_PATH = PHASE13_DIR / "human_review.csv"
RETAINED_QUESTION_PATH = PHASE13_DIR / "retained_question_review.csv"
RETAINED_PASSAGE_PATH = PHASE13_DIR / "retained_passage_review.csv"
CONSISTENCY_PATH = PHASE13_DIR / "review_consistency.csv"
PROVENANCE_PATH = PHASE13_DIR / "question_review_provenance.json"
FINAL_PACKET_PATH = PROJECT_ROOT / "V3_RETRIEVAL_FINAL_PASSAGE_REVIEW.md"

ORIGINAL_MANIFEST_SHA256 = "e7ed5e22aaba57dda174de6865e242789cbb611fc2a9e515c78729b05c02952f"
QUESTION_REVIEW_STATUS = "PROJECT_OWNER_ADOPTED_AI_ASSISTED_QUESTION_REVIEW"
QUESTION_REVIEW_METHOD = "PROJECT_OWNER_ADOPTED_AI_ASSISTED_RECOMMENDATIONS"
REVIEWER_ROLE = "project_owner"
PASSAGE_REVIEW_STATUS = "WAITING_FOR_PASSAGE_RELEVANCE_REVIEW"
CONSISTENCY_SEED = 131313

ACCEPTED_IDS = {
    "Q001", "Q002", "Q005", "Q006", "Q009", "Q010", "Q012",
    "Q013", "Q015", "Q017", "Q018", "Q020", "Q021", "Q022", "Q023",
    "Q025", "Q026", "Q028", "Q029", "Q030", "Q031", "Q033", "Q035",
    "Q037", "Q039", "Q040", "Q041", "Q043", "Q044", "Q045", "Q046", "Q048",
    "Q049", "Q050", "Q051", "Q054", "Q055", "Q056", "Q057", "Q058", "Q060",
}

EDITED_QUESTIONS = {
    "Q003": "Where should flood shelters and disaster relief centres be located so that they remain functional during floods?",
    "Q008": "How should flood warning information be presented to affected communities?",
    "Q016": "What personnel, equipment, and procedures are needed to move patients safely during evacuation?",
    "Q034": "What should authorities do when essential water, sanitation, or other services at a temporary shelter are disrupted?",
}

REJECTED_IDS = {
    "Q004", "Q007", "Q011", "Q014", "Q019", "Q024", "Q027", "Q032",
    "Q036", "Q038", "Q042", "Q047", "Q052", "Q053", "Q059",
}

EXPECTED_TOPICS = {
    "flood_management": 9,
    "evacuation_movement": 9,
    "temporary_shelters_relief_camps": 9,
    "vulnerable_groups_accessibility": 9,
    "logistics_transport_coordination": 9,
}
EXPECTED_STYLES = {"LEXICAL": 15, "SEMANTIC_PARAPHRASE": 15, "OPERATIONAL_TASK": 15}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify_frozen_inputs(question_rows: list[dict[str, str]], passage_rows: list[dict[str, str]]) -> None:
    digest = hashlib.sha256(CANDIDATE_MANIFEST_PATH.read_bytes()).hexdigest()
    if digest != ORIGINAL_MANIFEST_SHA256:
        raise ValueError("the frozen 60-question candidate manifest changed")
    all_ids = {f"Q{index:03d}" for index in range(1, 61)}
    if ACCEPTED_IDS | set(EDITED_QUESTIONS) | REJECTED_IDS != all_ids:
        raise ValueError("question decisions must cover Q001 through Q060 exactly")
    if (ACCEPTED_IDS & set(EDITED_QUESTIONS)) or (ACCEPTED_IDS & REJECTED_IDS) or (set(EDITED_QUESTIONS) & REJECTED_IDS):
        raise ValueError("question decision groups must be disjoint")
    if {row["question_id"] for row in question_rows} != all_ids:
        raise ValueError("question_review.csv must contain the original 60 candidates")
    if {row["question_id"] for row in passage_rows} != all_ids:
        raise ValueError("human_review.csv must contain pools for all 60 candidates")
    if any(row["human_grade"].strip() for row in passage_rows):
        raise ValueError("unexpected human passage grade; Phase 13A.1 cannot overwrite review")
    if any(row["human_review_status"] != "PENDING" for row in passage_rows):
        raise ValueError("unexpected completed passage review; Phase 13A.1 expects pending rows")


def apply_decisions(question_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for original in question_rows:
        row: dict[str, object] = dict(original)
        question_id = original["question_id"]
        if question_id in ACCEPTED_IDS:
            status, edited = "ACCEPT", ""
        elif question_id in EDITED_QUESTIONS:
            status, edited = "EDIT", EDITED_QUESTIONS[question_id]
        else:
            status, edited = "REJECT", ""
        row.update({
            "human_question_status": status,
            "human_edited_question": edited,
            "human_notes": "",
            "question_review_method": QUESTION_REVIEW_METHOD,
            "reviewer_role": REVIEWER_ROLE,
            "ai_assistance": "true",
        })
        output.append(row)
    return output


def validate_balance(retained: list[dict[str, object]]) -> None:
    if len(retained) != 45:
        raise ValueError(f"expected exactly 45 retained questions, got {len(retained)}")
    topics = Counter(str(row["topic"]) for row in retained)
    styles = Counter(str(row["query_style"]) for row in retained)
    if topics != EXPECTED_TOPICS:
        raise ValueError(f"retained topic balance differs: {dict(topics)}")
    if styles != EXPECTED_STYLES:
        raise ValueError(f"retained query-style balance differs: {dict(styles)}")


def build_retained_questions(decided_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    retained = []
    for row in decided_rows:
        if row["human_question_status"] not in {"ACCEPT", "EDIT"}:
            continue
        final_text = str(row["human_edited_question"] or row["question"])
        retained.append({
            "question_id": row["question_id"],
            "question": final_text,
            "original_question": row["question"],
            "topic": row["topic"],
            "query_style": row["query_style"],
            "question_review_status": row["human_question_status"],
            "machine_proposed_answerable": row["machine_proposed_answerable"],
            "machine_seed_source": row["machine_seed_source"],
            "machine_seed_page": row["machine_seed_page"],
            "question_review_method": QUESTION_REVIEW_METHOD,
            "reviewer_role": REVIEWER_ROLE,
            "ai_assistance": "true",
        })
    validate_balance(retained)
    return retained


def build_retained_passages(
    retained_questions: list[dict[str, object]], passage_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    questions = {str(row["question_id"]): row for row in retained_questions}
    retained = []
    for original in passage_rows:
        question = questions.get(original["question_id"])
        if question is None:
            continue
        retained.append({
            "question_id": original["question_id"],
            "question": question["question"],
            "original_question": original["question"],
            "topic": original["topic"],
            "query_style": original["query_style"],
            "chunk_id": original["chunk_id"],
            "source_id": original["source_id"],
            "filename": original["filename"],
            "page": original["page"],
            "excerpt": original["excerpt"],
            "dense_rank": original["dense_rank"],
            "bm25_rank": original["bm25_rank"],
            "hybrid_rank": original["hybrid_rank"],
            "machine_seed_evidence": original["machine_seed_evidence"],
            "machine_suggested_grade": original["machine_suggested_grade"],
            "human_grade": "",
            "human_review_status": "PENDING",
            "human_notes": "",
        })
    if any(row["human_grade"] for row in retained):
        raise ValueError("Phase 13A.1 must not populate human passage grades")
    return retained


def select_consistency_ids(retained_ids: list[str]) -> list[str]:
    rng = random.Random(CONSISTENCY_SEED)
    return sorted(rng.sample(sorted(retained_ids), 10))


def write_packet(
    retained_questions: list[dict[str, object]], retained_passages: list[dict[str, object]]
) -> None:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in retained_passages:
        grouped[str(row["question_id"])].append(row)
    counts = [len(grouped[str(row["question_id"])]) for row in retained_questions]
    lines = [
        "# Sentinel-Agent V3 — Final Passage Relevance Review",
        "",
        f"> **STATUS: {PASSAGE_REVIEW_STATUS}.** Question selection used",
        f"> `{QUESTION_REVIEW_METHOD}`. The project owner adopted AI-assisted question",
        "> recommendations; this was not blind, independent, or multi-reviewer annotation.",
        "> No machine-proposed passage grade has been converted into a human grade.",
        "",
        "## Review scale",
        "",
        "- **2 — DIRECTLY RELEVANT:** The passage directly answers or materially supports",
        "  the exact question and could reasonably be cited.",
        "- **1 — PARTIALLY RELEVANT:** The passage provides useful context but is",
        "  insufficient by itself to answer the core question.",
        "- **0 — NOT RELEVANT:** The passage does not materially help answer the exact",
        "  question.",
        "",
        "Judge the passage against the exact question. The main review view intentionally",
        "omits retriever identities, ranks, seed flags, and machine grade suggestions.",
        "Those frozen values remain in the technical appendix and machine-readable CSV.",
        "",
        "## Review-set summary",
        "",
        f"- Retained questions: {len(retained_questions)}",
        f"- Retained passage rows: {len(retained_passages)}",
        f"- Mean passages/question: {sum(counts) / len(counts):.2f}",
        f"- Minimum passages/question: {min(counts)}",
        f"- Maximum passages/question: {max(counts)}",
        "- Human passage grades completed: 0",
        "",
    ]
    for question in retained_questions:
        question_id = str(question["question_id"])
        lines.extend([
            f"## {question_id}",
            "",
            f"**Effective final question:** {question['question']}",
            "",
            f"- Topic: `{question['topic']}`",
            f"- Query style: `{question['query_style']}`",
            f"- Question decision: `{question['question_review_status']}`",
            "",
            "### Candidate passages",
            "",
        ])
        exact_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
        for passage in grouped[question_id]:
            exact_groups[str(passage["excerpt"])].append(passage)
        for number, records in enumerate(exact_groups.values(), start=1):
            representative = records[0]
            chunk_ids = ", ".join(f"`{row['chunk_id']}`" for row in records)
            lines.extend([
                f"#### Passage {number}",
                "",
                f"- Chunk ID{'s' if len(records) > 1 else ''}: {chunk_ids}",
                f"- Document: `{representative['filename']}`",
                f"- PDF page: {representative['page']}",
            ])
            if len(records) > 1:
                lines.append(f"- Presentation group: {len(records)} identical-text underlying rows")
            lines.extend([
                "",
                "> " + str(representative["excerpt"]).replace("\n", " ").rstrip(),
                "",
                "**GRADE:**",
                "",
                "- [ ] 2 DIRECTLY RELEVANT",
                "- [ ] 1 PARTIALLY RELEVANT",
                "- [ ] 0 NOT RELEVANT",
                "",
            ])
    lines.extend([
        "## Technical appendix — frozen retrieval metadata",
        "",
        "Ranks, seed flags, and machine suggestions are shown only here to reduce bias in",
        "the main review view. Blank rank means the method did not return that chunk in its",
        "frozen top-10 pool.",
        "",
        "| Question | Chunk | Dense | BM25 | Hybrid | Seed | Machine suggestion |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: |",
    ])
    for row in retained_passages:
        lines.append(
            f"| {row['question_id']} | `{row['chunk_id']}` | {row['dense_rank'] or '—'} | "
            f"{row['bm25_rank'] or '—'} | {row['hybrid_rank'] or '—'} | "
            f"{row['machine_seed_evidence']} | {row['machine_suggested_grade'] or '—'} |"
        )
    FINAL_PACKET_PATH.write_text("\n".join(lines).rstrip() + "\n")


def main() -> int:
    question_rows = read_csv(QUESTION_REVIEW_PATH)
    passage_rows = read_csv(ORIGINAL_PASSAGE_REVIEW_PATH)
    verify_frozen_inputs(question_rows, passage_rows)
    decided = apply_decisions(question_rows)
    retained_questions = build_retained_questions(decided)
    retained_passages = build_retained_passages(retained_questions, passage_rows)

    question_fields = list(question_rows[0])
    for field in ("question_review_method", "reviewer_role", "ai_assistance"):
        if field not in question_fields:
            question_fields.append(field)
    write_csv(QUESTION_REVIEW_PATH, question_fields, decided)
    retained_question_fields = list(retained_questions[0])
    write_csv(RETAINED_QUESTION_PATH, retained_question_fields, retained_questions)
    retained_passage_fields = list(retained_passages[0])
    write_csv(RETAINED_PASSAGE_PATH, retained_passage_fields, retained_passages)

    retained_ids = [str(row["question_id"]) for row in retained_questions]
    consistency_ids = select_consistency_ids(retained_ids)
    consistency_rows = [
        {
            "question_id": row["question_id"],
            "chunk_id": row["chunk_id"],
            "first_pass_grade": "",
            "second_pass_grade": "",
            "second_pass_status": "PENDING",
            "consistency_notes": "",
        }
        for row in retained_passages
        if row["question_id"] in consistency_ids
    ]
    write_csv(
        CONSISTENCY_PATH,
        ["question_id", "chunk_id", "first_pass_grade", "second_pass_grade", "second_pass_status", "consistency_notes"],
        consistency_rows,
    )

    counts = Counter(str(row["question_id"]) for row in retained_passages)
    provenance = {
        "question_review_status": QUESTION_REVIEW_STATUS,
        "question_review_method": QUESTION_REVIEW_METHOD,
        "reviewer_role": REVIEWER_ROLE,
        "ai_assistance": True,
        "independent_human_review": False,
        "blind_human_annotation": False,
        "multi_reviewer_review": False,
        "original_candidate_manifest_sha256": ORIGINAL_MANIFEST_SHA256,
        "original_candidate_count": 60,
        "accepted_without_edit_count": len(ACCEPTED_IDS),
        "edited_count": len(EDITED_QUESTIONS),
        "rejected_count": len(REJECTED_IDS),
        "retained_count": len(retained_questions),
        "retained_passage_rows": len(retained_passages),
        "mean_passages_per_question": round(len(retained_passages) / 45, 6),
        "minimum_passages_per_question": min(counts.values()),
        "maximum_passages_per_question": max(counts.values()),
        "human_passage_grades_completed": 0,
        "passage_review_status": PASSAGE_REVIEW_STATUS,
        "consistency_seed": CONSISTENCY_SEED,
        "consistency_question_ids": consistency_ids,
        "official_retrieval_metrics_calculated": False,
    }
    PROVENANCE_PATH.write_text(json.dumps(provenance, indent=2) + "\n")
    write_packet(retained_questions, retained_passages)

    print(f"Retained questions: {len(retained_questions)}")
    print(f"Decision counts: ACCEPT={len(ACCEPTED_IDS)}, EDIT={len(EDITED_QUESTIONS)}, REJECT={len(REJECTED_IDS)}")
    print(f"Topic counts: {dict(Counter(str(row['topic']) for row in retained_questions))}")
    print(f"Style counts: {dict(Counter(str(row['query_style']) for row in retained_questions))}")
    print(f"Retained passage rows: {len(retained_passages)}")
    print(f"Passages/question: mean={len(retained_passages) / 45:.2f}, min={min(counts.values())}, max={max(counts.values())}")
    print(f"Consistency questions: {', '.join(consistency_ids)}")
    print("Human passage grades completed: 0")
    print(f"Status: {PASSAGE_REVIEW_STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
