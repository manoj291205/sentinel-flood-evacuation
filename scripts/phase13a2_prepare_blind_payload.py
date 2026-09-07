#!/usr/bin/env python3
"""Create the rank-free Phase 13A.2 AI relevance-labeling payload."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "eval_v3" / "phase13" / "retained_passage_review.csv"
OUTPUT = ROOT / "data" / "eval_v3" / "phase13" / "ai_labeling_payload.jsonl"

ALLOWED_FIELDS = (
    "question_id",
    "effective_question",
    "topic",
    "query_style",
    "chunk_id",
    "source_id",
    "filename",
    "page",
    "original_text",
)
FORBIDDEN_FRAGMENTS = (
    "rank",
    "score",
    "retriev",
    "fusion",
    "suggested_grade",
    "seed_evidence",
    "human_grade",
    "human_review",
)


def main() -> int:
    with SOURCE.open(newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    if len(source_rows) != 485:
        raise ValueError(f"expected 485 retained passages, got {len(source_rows)}")
    if any(row["human_grade"] or row["human_review_status"] != "PENDING" for row in source_rows):
        raise ValueError("human passage fields must remain blank/PENDING")

    payload = [
        {
            "question_id": row["question_id"],
            "effective_question": row["question"],
            "topic": row["topic"],
            "query_style": row["query_style"],
            "chunk_id": row["chunk_id"],
            "source_id": row["source_id"],
            "filename": row["filename"],
            "page": row["page"],
            "original_text": row["excerpt"],
        }
        for row in source_rows
    ]
    payload.sort(
        key=lambda row: hashlib.sha256(
            f"{row['question_id']}\0{row['chunk_id']}".encode()
        ).hexdigest()
    )
    if any(tuple(row) != ALLOWED_FIELDS for row in payload):
        raise ValueError("blind payload field order or membership changed")
    lowered_fields = {field.casefold() for row in payload for field in row}
    if any(fragment in field for fragment in FORBIDDEN_FRAGMENTS for field in lowered_fields):
        raise ValueError("blind payload exposes forbidden retrieval or prior-label metadata")
    if len({(row["question_id"], row["chunk_id"]) for row in payload}) != 485:
        raise ValueError("blind payload contains duplicate question/chunk pairs")

    question_rows = {row["question_id"]: row for row in payload}
    if len(question_rows) != 45:
        raise ValueError("blind payload must contain exactly 45 questions")
    if Counter(row["topic"] for row in question_rows.values()) != {
        "flood_management": 9,
        "evacuation_movement": 9,
        "temporary_shelters_relief_camps": 9,
        "vulnerable_groups_accessibility": 9,
        "logistics_transport_coordination": 9,
    }:
        raise ValueError("blind payload topic balance changed")
    if Counter(row["query_style"] for row in question_rows.values()) != {
        "LEXICAL": 15,
        "SEMANTIC_PARAPHRASE": 15,
        "OPERATIONAL_TASK": 15,
    }:
        raise ValueError("blind payload query-style balance changed")

    OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in payload))
    print(f"Wrote {len(payload)} blind question-passage pairs for {len(question_rows)} questions")
    print("Included fields: " + ", ".join(ALLOWED_FIELDS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
