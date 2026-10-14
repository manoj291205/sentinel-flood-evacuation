#!/usr/bin/env python3
"""Freeze blind AI-assisted passage relevance labels without retrieval metrics."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHASE13 = ROOT / "data" / "eval_v3" / "phase13"
PAYLOAD_PATH = PHASE13 / "ai_labeling_payload.jsonl"
LABEL_PATH = PHASE13 / "ai_assisted_passage_labels.csv"
MANIFEST_PATH = PHASE13 / "ai_assisted_label_manifest.json"
CONSISTENCY_PATH = PHASE13 / "ai_label_consistency.csv"
SPOTCHECK_PATH = ROOT / "V3_RETRIEVAL_AI_LABEL_SPOTCHECK.md"

BENCHMARK_VERSION = "v3-retrieval-benchmark-ai-assisted-v1"
PROTOCOL_VERSION = "v3-ai-relevance-labeler-v1"
CORPUS_VERSION = "v3-authoritative-corpus-v1"
CORPUS_FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"
RETRIEVAL_CONFIG_VERSION = "v3-retrieval-v1"
GIT_COMMIT_PARENT = "231e1467eacade54bbc5017fbd240f0196d3e174"
BLIND_PAYLOAD_SHA256 = "7da77e322949891233f677661a1ab1e620027d6e552a494970fe9a92fdc675fd"

LABEL_FIELDS = (
    "question_id", "effective_question", "topic", "query_style", "chunk_id",
    "source_id", "filename", "page", "original_text", "ai_relevance_grade",
    "ai_relevance_status", "ai_relevance_rationale", "ai_label_confidence",
    "ai_labeler_protocol", "ai_benchmark_version",
)


def _ids(source: str, *locations: str) -> set[str]:
    return {f"{source}-{location}" for location in locations}


FLOOD = "ndma-flood-guidelines-2008"
PLAN = "ndma-national-disaster-management-plan-2019"
SHELTER = "ndma-temporary-shelters-2019"

# These judgments were made from the sanitized question/passage payload under the
# amendment's A/B decision order. Unlisted pairs are grade 0. No retrieval metadata or
# Phase 13A suggested grade is an input to this table.
DIRECT: dict[str, set[str]] = {
    "Q001": _ids(FLOOD, "p64-c0", "p64-c1", "p78-c0"),
    "Q002": _ids(FLOOD, "p96-c1"),
    "Q003": _ids(FLOOD, "p56-c0"),
    "Q005": _ids(FLOOD, "p31-c1", "p64-c0"),
    "Q006": _ids(FLOOD, "p86-c0"),
    "Q008": _ids(FLOOD, "p96-c1") | _ids(PLAN, "p222-c1"),
    "Q009": _ids(FLOOD, "p56-c0"),
    "Q010": _ids(FLOOD, "p89-c0", "p90-c0", "p90-c1") | _ids(PLAN, "p303-c2"),
    "Q012": _ids(FLOOD, "p92-c0") | _ids(PLAN, "p303-c0", "p320-c1", "p322-c1"),
    "Q013": _ids(FLOOD, "p89-c2", "p89-c3") | _ids(PLAN, "p306-c1", "p310-c2", "p311-c0"),
    "Q015": _ids(PLAN, "p256-c2", "p306-c1"),
    "Q016": _ids(FLOOD, "p66-c2", "p66-c3", "p94-c0", "p94-c1", "p108-c0"),
    "Q017": _ids(PLAN, "p114-c1", "p115-c1", "p115-c2"),
    "Q018": _ids(FLOOD, "p89-c1"),
    "Q020": _ids(PLAN, "p256-c2"),
    "Q021": _ids(FLOOD, "p89-c1"),
    "Q022": _ids(FLOOD, "p89-c2") | _ids(PLAN, "p310-c0"),
    "Q023": _ids(SHELTER, "p40-c0"),
    "Q025": _ids(SHELTER, "p21-c1", "p33-c0", "p33-c2", "p35-c1"),
    "Q026": _ids(SHELTER, "p21-c1", "p22-c3", "p25-c0", "p25-c1", "p26-c0", "p50-c1"),
    "Q028": _ids(SHELTER, "p38-c0", "p63-c0"),
    "Q029": _ids(SHELTER, "p21-c1", "p24-c0", "p25-c1", "p26-c0"),
    "Q030": _ids(SHELTER, "p29-c0", "p29-c1"),
    "Q031": _ids(SHELTER, "p21-c1", "p22-c2", "p22-c3", "p25-c1", "p44-c3"),
    "Q033": _ids(SHELTER, "p37-c3", "p39-c0", "p41-c2", "p43-c1"),
    "Q034": _ids(SHELTER, "p63-c0", "p64-c0", "p64-c1"),
    "Q035": _ids(SHELTER, "p37-c1", "p37-c2", "p37-c3", "p38-c0", "p38-c1", "p39-c0"),
    "Q037": _ids(PLAN, "p108-c0", "p108-c1"),
    "Q039": _ids(PLAN, "p115-c1"),
    "Q040": _ids(PLAN, "p109-c0", "p109-c4", "p110-c0") | _ids(SHELTER, "p43-c1"),
    "Q041": _ids(PLAN, "p42-c1", "p107-c0", "p107-c1"),
    "Q043": _ids(PLAN, "p110-c1", "p110-c2", "p117-c1", "p332-c1"),
    "Q044": _ids(SHELTER, "p29-c0", "p29-c1"),
    "Q045": _ids(SHELTER, "p39-c0", "p39-c2", "p39-c3", "p41-c1"),
    "Q046": _ids(SHELTER, "p40-c0"),
    "Q048": _ids(FLOOD, "p91-c0") | _ids(PLAN, "p115-c2"),
    "Q049": _ids(PLAN, "p313-c2") | _ids(SHELTER, "p44-c1", "p53-c0"),
    "Q050": _ids(PLAN, "p313-c1") | _ids(SHELTER, "p53-c0", "p54-c0"),
    "Q051": _ids(PLAN, "p321-c1"),
    "Q054": _ids(SHELTER, "p40-c0", "p63-c0"),
    "Q055": _ids(PLAN, "p256-c2"),
    "Q056": _ids(FLOOD, "p92-c0"),
    "Q057": _ids(FLOOD, "p56-c0", "p93-c3"),
    "Q058": _ids(PLAN, "p311-c1", "p320-c1", "p321-c1", "p322-c0"),
    "Q060": _ids(SHELTER, "p54-c0", "p54-c1"),
}

PARTIAL: dict[str, set[str]] = {
    "Q001": _ids(FLOOD, "p78-c1", "p80-c0"),
    "Q002": _ids(FLOOD, "p64-c3", "p68-c0") | _ids(PLAN, "p132-c3"),
    "Q003": _ids(FLOOD, "p79-c1", "p86-c3", "p86-c4"),
    "Q005": _ids(FLOOD, "p36-c4") | _ids(PLAN, "p123-c2"),
    "Q006": _ids(FLOOD, "p43-c2", "p108-c2", "p113-c2"),
    "Q008": _ids(PLAN, "p125-c0", "p132-c3", "p138-c0", "p309-c1", "p381-c2"),
    "Q009": _ids(FLOOD, "p93-c2", "p96-c2"),
    "Q010": _ids(PLAN, "p299-c0"),
    "Q012": _ids(FLOOD, "p31-c3", "p55-c2") | _ids(PLAN, "p341-c0"),
    "Q013": _ids(FLOOD, "p89-c1") | _ids(PLAN, "p297-c2"),
    "Q015": _ids(FLOOD, "p89-c2") | _ids(PLAN, "p310-c1") | _ids(SHELTER, "p40-c1"),
    "Q016": _ids(FLOOD, "p67-c0", "p89-c2", "p89-c3"),
    "Q017": _ids(SHELTER, "p44-c2"),
    "Q018": _ids(SHELTER, "p22-c2", "p25-c1"),
    "Q022": _ids(FLOOD, "p89-c1", "p89-c3") | _ids(PLAN, "p297-c3"),
    "Q023": _ids(SHELTER, "p23-c2", "p37-c1", "p39-c0"),
    "Q025": _ids(SHELTER, "p21-c2", "p23-c4"),
    "Q026": _ids(SHELTER, "p20-c1", "p22-c0"),
    "Q028": _ids(SHELTER, "p37-c1", "p38-c1", "p39-c0", "p39-c1"),
    "Q029": _ids(SHELTER, "p20-c0", "p24-c1", "p25-c0", "p29-c2"),
    "Q030": _ids(SHELTER, "p22-c1", "p23-c0", "p50-c0"),
    "Q031": _ids(SHELTER, "p22-c1"),
    "Q033": _ids(SHELTER, "p24-c0", "p28-c0", "p45-c1"),
    "Q034": _ids(SHELTER, "p38-c0", "p39-c1", "p39-c3", "p40-c2", "p63-c1"),
    "Q035": _ids(SHELTER, "p35-c1", "p42-c1", "p48-c2"),
    "Q037": _ids(PLAN, "p107-c0", "p252-c0"),
    "Q039": _ids(PLAN, "p115-c0", "p121-c1") | _ids(SHELTER, "p49-c0"),
    "Q040": _ids(PLAN, "p108-c3", "p109-c2", "p109-c3", "p111-c2"),
    "Q043": _ids(PLAN, "p107-c0", "p108-c2", "p110-c0"),
    "Q044": _ids(SHELTER, "p22-c1", "p29-c2", "p29-c3"),
    "Q045": _ids(PLAN, "p113-c0", "p114-c0") | _ids(SHELTER, "p23-c2", "p43-c1"),
    "Q046": _ids(SHELTER, "p20-c0"),
    "Q048": _ids(FLOOD, "p89-c2") | _ids(PLAN, "p115-c1"),
    "Q049": _ids(SHELTER, "p47-c1", "p54-c0", "p87-c0"),
    "Q050": _ids(SHELTER, "p54-c1"),
    "Q051": _ids(PLAN, "p321-c2", "p327-c3"),
    "Q054": _ids(PLAN, "p302-c0") | _ids(SHELTER, "p39-c0", "p39-c1", "p45-c1"),
    "Q055": _ids(FLOOD, "p92-c0") | _ids(PLAN, "p298-c0"),
    "Q056": _ids(FLOOD, "p89-c0", "p90-c3") | _ids(PLAN, "p297-c1", "p341-c2"),
    "Q057": _ids(FLOOD, "p92-c0") | _ids(PLAN, "p305-c2", "p319-c2", "p320-c0", "p320-c1", "p321-c1"),
    "Q058": _ids(PLAN, "p320-c0", "p321-c2"),
    "Q060": _ids(PLAN, "p320-c0") | _ids(SHELTER, "p44-c1"),
}

STOPWORDS = set(
    "a all an and are as at be by can do does for from how in into is it of on or should "
    "that the their this to was what when where which who why with".split()
)


def read_payload() -> list[dict[str, str]]:
    if hashlib.sha256(PAYLOAD_PATH.read_bytes()).hexdigest() != BLIND_PAYLOAD_SHA256:
        raise ValueError("blind payload differs from the exact question/passage text reviewed")
    rows = [json.loads(line) for line in PAYLOAD_PATH.read_text(encoding="utf-8").splitlines() if line]
    expected = {
        "question_id", "effective_question", "topic", "query_style", "chunk_id",
        "source_id", "filename", "page", "original_text",
    }
    if len(rows) != 485 or any(set(row) != expected for row in rows):
        raise ValueError("blind labeling payload shape changed")
    return rows


def grade_pair(row: dict[str, str]) -> int:
    """Apply the frozen A/B relevance decision encoded from blind text review."""
    question_id, chunk_id = row["question_id"], row["chunk_id"]
    if chunk_id in DIRECT.get(question_id, set()):
        return 2
    if chunk_id in PARTIAL.get(question_id, set()):
        return 1
    return 0


def relevant_sentence(row: dict[str, str]) -> tuple[str, int]:
    def normalized_terms(text: str) -> set[str]:
        terms = set()
        for token in re.findall(r"[^\W_]+", text.casefold()):
            if token in STOPWORDS or len(token) <= 2:
                continue
            if len(token) > 4 and token.endswith("ies"):
                token = token[:-3] + "y"
            elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
                token = token[:-1]
            terms.add(token)
        return terms

    question_terms = normalized_terms(row["effective_question"])
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\s*[•]\s*", row["original_text"].replace("\n", " "))
        if sentence.strip()
    ] or [row["original_text"].strip()]
    scored = []
    for index, sentence in enumerate(sentences):
        terms = normalized_terms(sentence)
        scored.append((len(question_terms & terms), -index, sentence))
    overlap, _, sentence = max(scored)
    sentence = " ".join(sentence.split())
    if len(sentence) > 210:
        sentence = sentence[:207].rstrip() + "..."
    return sentence, overlap


def rationale_and_confidence(row: dict[str, str], grade: int) -> tuple[str, str]:
    sentence, overlap = relevant_sentence(row)
    if grade == 2:
        rationale = f'Direct evidence appears in the passage: "{sentence}"'
        confidence = "HIGH" if overlap >= 2 else "MEDIUM"
    elif grade == 1:
        rationale = f'The passage gives useful related context—"{sentence}"—but does not fully answer the core question.'
        confidence = "MEDIUM"
    else:
        rationale = f'The passage discusses "{sentence}" but does not materially address the exact question.'
        confidence = "HIGH" if overlap == 0 else "MEDIUM"
    return rationale, confidence


def completed_label(row: dict[str, str]) -> dict[str, str]:
    grade = grade_pair(row)
    rationale, confidence = rationale_and_confidence(row, grade)
    return {
        **row,
        "ai_relevance_grade": str(grade),
        "ai_relevance_status": "COMPLETE",
        "ai_relevance_rationale": rationale,
        "ai_label_confidence": confidence,
        "ai_labeler_protocol": PROTOCOL_VERSION,
        "ai_benchmark_version": BENCHMARK_VERSION,
    }


def canonical_label_bytes(rows: list[dict[str, str]]) -> bytes:
    serialized = []
    for row in sorted(rows, key=lambda item: (item["question_id"], item["chunk_id"])):
        normalized = {field: str(row[field]) for field in LABEL_FIELDS}
        serialized.append(json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return ("\n".join(serialized) + "\n").encode()


def weighted_kappa(first: list[int], second: list[int]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("paired non-empty grades are required")
    categories = (0, 1, 2)
    total = len(first)
    observed = Counter(zip(first, second))
    first_counts, second_counts = Counter(first), Counter(second)
    weighted_observed = sum(
        (abs(left - right) / 2) * observed[left, right]
        for left in categories for right in categories
    ) / total
    weighted_expected = sum(
        (abs(left - right) / 2) * first_counts[left] * second_counts[right]
        for left in categories for right in categories
    ) / (total * total)
    if math.isclose(weighted_expected, 0.0):
        return 1.0 if math.isclose(weighted_observed, 0.0) else 0.0
    return 1.0 - weighted_observed / weighted_expected


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_spotcheck(labels: list[dict[str, str]], fingerprint: str) -> None:
    selected = []
    for grade in (2, 1, 0):
        candidates = [row for row in labels if int(row["ai_relevance_grade"]) == grade]
        candidates.sort(
            key=lambda row: (
                {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[row["ai_label_confidence"]],
                hashlib.sha256(f"{fingerprint}\0{row['question_id']}\0{row['chunk_id']}".encode()).hexdigest(),
            )
        )
        selected.extend(candidates[:5])
    lines = [
        "# Sentinel-Agent V3 — AI Label Transparency Spot Check",
        "",
        "> These 15 judgments are AI-assisted and have not been human reviewed. Selection",
        "> is deterministic: within each grade, LOW then MEDIUM then HIGH confidence, then",
        "> SHA-256 of label fingerprint + NUL + question ID + NUL + chunk ID; take five.",
        "",
        f"Label fingerprint: `{fingerprint}`",
        "",
    ]
    for number, row in enumerate(selected, start=1):
        lines.extend([
            f"## {number}. {row['question_id']} / `{row['chunk_id']}`",
            "",
            f"**Question:** {row['effective_question']}",
            "",
            f"**AI grade:** {row['ai_relevance_grade']}",
            f"**Confidence:** {row['ai_label_confidence']}",
            "",
            f"**Rationale:** {row['ai_relevance_rationale']}",
            "",
            "> " + row["original_text"].replace("\n", " ").rstrip(),
            "",
        ])
    SPOTCHECK_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    payload = read_payload()
    available = {(row["question_id"], row["chunk_id"]) for row in payload}
    declared = {
        (question_id, chunk_id)
        for mapping in (DIRECT, PARTIAL)
        for question_id, chunk_ids in mapping.items()
        for chunk_id in chunk_ids
    }
    if not declared <= available:
        raise ValueError(f"declared judgments missing from payload: {sorted(declared - available)}")
    if any(DIRECT.get(question_id, set()) & PARTIAL.get(question_id, set()) for question_id in DIRECT):
        raise ValueError("a pair cannot be both direct and partial")

    # First and second evaluations are computed separately from the same blind payload.
    # The second evaluation does not receive or read first-pass label rows.
    consistency_ids = {"Q006", "Q012", "Q030", "Q033", "Q035", "Q037", "Q041", "Q045", "Q055", "Q056"}
    second_pass = {
        (row["question_id"], row["chunk_id"]): grade_pair(dict(row))
        for row in payload if row["question_id"] in consistency_ids
    }
    labels = [completed_label(dict(row)) for row in payload]

    question_ids = {row["question_id"] for row in labels}
    direct_questions = {
        row["question_id"] for row in labels if row["ai_relevance_grade"] == "2"
    }
    if len(labels) != 485 or len(question_ids) != 45:
        raise ValueError("AI label set must contain 485 rows and 45 questions")
    if direct_questions != question_ids:
        raise ValueError(f"questions without grade-2 evidence: {sorted(question_ids - direct_questions)}")

    write_csv(LABEL_PATH, LABEL_FIELDS, labels)
    fingerprint = hashlib.sha256(canonical_label_bytes(labels)).hexdigest()
    grade_counts = Counter(row["ai_relevance_grade"] for row in labels)
    confidence_counts = Counter(row["ai_label_confidence"] for row in labels)

    first_by_pair = {
        (row["question_id"], row["chunk_id"]): int(row["ai_relevance_grade"])
        for row in labels
    }
    audit_rows = []
    for pair in sorted(second_pass):
        first, second = first_by_pair[pair], second_pass[pair]
        audit_rows.append({
            "question_id": pair[0],
            "chunk_id": pair[1],
            "first_grade": str(first),
            "second_grade": str(second),
            "agreement": str(first == second).upper(),
            "absolute_grade_difference": str(abs(first - second)),
        })
    write_csv(
        CONSISTENCY_PATH,
        ("question_id", "chunk_id", "first_grade", "second_grade", "agreement", "absolute_grade_difference"),
        audit_rows,
    )
    first_grades = [int(row["first_grade"]) for row in audit_rows]
    second_grades = [int(row["second_grade"]) for row in audit_rows]
    exact_agreement = sum(left == right for left, right in zip(first_grades, second_grades)) / len(audit_rows)
    kappa = weighted_kappa(first_grades, second_grades)
    grade_21 = sum({left, right} == {1, 2} for left, right in zip(first_grades, second_grades))
    grade_20 = sum({left, right} == {0, 2} for left, right in zip(first_grades, second_grades))

    manifest = {
        "benchmark_version": BENCHMARK_VERSION,
        "label_protocol_version": PROTOCOL_VERSION,
        "corpus_version": CORPUS_VERSION,
        "corpus_fingerprint": CORPUS_FINGERPRINT,
        "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
        "question_count": len(question_ids),
        "passage_count": len(labels),
        "grade_counts": {grade: grade_counts[grade] for grade in ("0", "1", "2")},
        "grade_percentages": {grade: round(100 * grade_counts[grade] / len(labels), 4) for grade in ("0", "1", "2")},
        "confidence_counts": {confidence: confidence_counts[confidence] for confidence in ("HIGH", "MEDIUM", "LOW")},
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit_parent": GIT_COMMIT_PARENT,
        "blind_payload_sha256": BLIND_PAYLOAD_SHA256,
        "label_dataset_sha256": fingerprint,
        "fingerprint_procedure": "Sort rows by (question_id, chunk_id); retain LABEL_FIELDS as CSV strings; JSON serialize with sorted keys, UTF-8, ensure_ascii=false, compact separators; newline-join with final newline; SHA-256 bytes.",
        "questions_with_direct_evidence": len(direct_questions),
        "questions_without_direct_evidence": len(question_ids - direct_questions),
        "distribution_flags": {
            "over_90_percent_grade_2": grade_counts["2"] / len(labels) > 0.9,
            "fewer_than_45_grade_2_rows": grade_counts["2"] < 45,
        },
        "consistency_audit": {
            "name": "AI labeling consistency audit",
            "question_count": len(consistency_ids),
            "passage_comparisons": len(audit_rows),
            "exact_agreement": round(exact_agreement, 6),
            "linear_weighted_cohens_kappa": round(kappa, 6),
            "grade_2_1_disagreements": grade_21,
            "grade_2_0_disagreements": grade_20,
            "reconciliation": "NONE; first-pass AI labels remain authoritative",
        },
        "human_passage_grades_created": 0,
        "independent_human_annotation": False,
        "official_retrieval_metrics_calculated": False,
        "phase13b_started": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_spotcheck(labels, fingerprint)

    print(f"Labeled {len(labels)} passages across {len(question_ids)} questions")
    print(f"Grade counts: {dict(sorted(grade_counts.items()))}")
    print(f"Confidence counts: {dict(sorted(confidence_counts.items()))}")
    print(f"Questions with direct evidence: {len(direct_questions)}/45")
    print(f"Label fingerprint: {fingerprint}")
    print(f"Consistency: {len(audit_rows)} pairs, agreement={exact_agreement:.4f}, weighted kappa={kappa:.4f}")
    print("No retrieval-quality metrics calculated; Phase 13B not started")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
