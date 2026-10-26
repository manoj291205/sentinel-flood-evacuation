"""Frozen Phase 14 claim-support contracts and evaluation helpers.

This module contains no semantic model call. Phase 14A freezes the interface and the
deterministic integrity/evaluation layers; a provider implementation belongs to 14B.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

if TYPE_CHECKING:
    from src.rag.ingest import PreparedCorpus
    from ..rag.ingest import PreparedCorpus

QUOTE_INTEGRITY_PROTOCOL_VERSION = "quote-integrity-v1"
SUPPORT_PROTOCOL_VERSION = "v3-claim-support-protocol-v1"


class ClaimSupportVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    source_id: str
    filename: str
    page: int
    text: str
    passage_sha256: str


@dataclass(frozen=True)
class ClaimSupportResult:
    verdict: ClaimSupportVerdict
    confidence: float
    supporting_spans: list[str]
    reason: str
    source_integrity_pass: bool
    support_protocol_version: str = SUPPORT_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdict", ClaimSupportVerdict(self.verdict))
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if not self.reason.strip():
            raise ValueError("reason must be non-empty")
        if self.verdict in {
            ClaimSupportVerdict.SUPPORTED,
            ClaimSupportVerdict.PARTIALLY_SUPPORTED,
        } and not self.supporting_spans:
            raise ValueError("supported and partially supported results require spans")


def get_chunk_by_id(
    chunk_id: str,
    prepared: "PreparedCorpus",
    *,
    source_id: str | None = None,
    filename: str | None = None,
    page: int | None = None,
    passage_sha256: str | None = None,
) -> EvidenceChunk:
    """Resolve exactly one frozen chunk and validate optional provenance."""
    if not (len(prepared.ids) == len(prepared.documents) == len(prepared.metadatas)):
        raise ValueError("prepared corpus arrays have inconsistent lengths")
    matches = [index for index, candidate in enumerate(prepared.ids) if candidate == chunk_id]
    if len(matches) != 1:
        raise ValueError(f"chunk ID must exist exactly once: {chunk_id}")
    index = matches[0]
    metadata = prepared.metadatas[index]
    text = prepared.documents[index]
    chunk = EvidenceChunk(
        chunk_id=chunk_id,
        source_id=str(metadata["source_id"]),
        filename=str(metadata["source_document"]),
        page=int(metadata["page"]),
        text=text,
        passage_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    expected = (source_id, filename, page, passage_sha256)
    actual = (chunk.source_id, chunk.filename, chunk.page, chunk.passage_sha256)
    for label, expected_value, actual_value in zip(
        ("source ID", "filename", "page", "passage SHA-256"), expected, actual
    ):
        if expected_value is not None and expected_value != actual_value:
            raise ValueError(f"chunk {label} mismatch for {chunk_id}")
    return chunk


def verify_evidence_integrity(evidence: EvidenceChunk) -> bool:
    """Layer 1: validate stable provenance shape and exact local text digest."""
    if not all((evidence.chunk_id, evidence.source_id, evidence.filename, evidence.text)):
        return False
    if isinstance(evidence.page, bool) or evidence.page < 1:
        return False
    digest = hashlib.sha256(evidence.text.encode("utf-8")).hexdigest()
    return digest == evidence.passage_sha256


def validate_supporting_spans(
    evidence: EvidenceChunk, supporting_spans: Iterable[str]
) -> bool:
    """Require every semantic supporting span to occur verbatim in the chunk."""
    spans = tuple(supporting_spans)
    return bool(spans) and all(span and span in evidence.text for span in spans)


def build_verifier_payload(claim: str, evidence: EvidenceChunk) -> dict[str, object]:
    """Construct the only payload shape permitted for a future semantic provider."""
    if not claim.strip():
        raise ValueError("claim must be non-empty")
    return {
        "claim": claim,
        "evidence": evidence.text,
        "source_provenance": {
            "chunk_id": evidence.chunk_id,
            "source_id": evidence.source_id,
            "filename": evidence.filename,
            "page": evidence.page,
            "passage_sha256": evidence.passage_sha256,
        },
    }


def finalize_semantic_result(
    *,
    evidence: EvidenceChunk,
    verdict: ClaimSupportVerdict | str,
    confidence: float,
    supporting_spans: Sequence[str],
    reason: str,
) -> ClaimSupportResult:
    """Apply the deterministic layer after a future semantic provider responds."""
    semantic_verdict = ClaimSupportVerdict(verdict)
    integrity = verify_evidence_integrity(evidence)
    if semantic_verdict in {
        ClaimSupportVerdict.SUPPORTED,
        ClaimSupportVerdict.PARTIALLY_SUPPORTED,
    }:
        integrity = integrity and validate_supporting_spans(evidence, supporting_spans)
    return ClaimSupportResult(
        verdict=semantic_verdict,
        confidence=confidence,
        supporting_spans=list(supporting_spans),
        reason=reason,
        source_integrity_pass=integrity,
    )


def verify_claim_support(claim: str, evidence: EvidenceChunk) -> ClaimSupportResult:
    """Frozen Phase 14B interface; delegates to the Gemini provider (V4_CLAIM_SUPPORT_14B_SPEC)."""
    from src.constraints.claim_support_gemini import verify_claim_support_gemini

    return verify_claim_support_gemini(claim, evidence)


def safe_to_cite(verdict: ClaimSupportVerdict | str) -> bool:
    """Frozen classification mapping only; use evidence.operational_citation_eligible for permission."""
    return ClaimSupportVerdict(verdict) is ClaimSupportVerdict.SUPPORTED


def label_independent_order(pair_ids: Sequence[str], challenge_fingerprint: str) -> list[str]:
    """Order pairs without consulting their labels or construction metadata."""
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("claim pair IDs must be unique")
    return sorted(
        pair_ids,
        key=lambda pair_id: (
            hashlib.sha256(f"{pair_id}{challenge_fingerprint}".encode("utf-8")).hexdigest(),
            pair_id,
        ),
    )


def classification_metrics(
    expected: Sequence[ClaimSupportVerdict | str],
    predicted: Sequence[ClaimSupportVerdict | str],
) -> dict[str, object]:
    """Compute frozen metrics for toy tests and future Phase 14B evaluation."""
    if len(expected) != len(predicted) or not expected:
        raise ValueError("equal, non-empty expected and predicted sequences are required")
    truth = [ClaimSupportVerdict(value) for value in expected]
    guesses = [ClaimSupportVerdict(value) for value in predicted]
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    matrix: dict[str, dict[str, int]] = {
        label.value: {guess.value: 0 for guess in ClaimSupportVerdict}
        for label in ClaimSupportVerdict
    }
    for label, guess in zip(truth, guesses):
        matrix[label.value][guess.value] += 1
    for label in ClaimSupportVerdict:
        tp = sum(a is label and b is label for a, b in zip(truth, guesses))
        fp = sum(a is not label and b is label for a, b in zip(truth, guesses))
        fn = sum(a is label and b is not label for a, b in zip(truth, guesses))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label.value] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": sum(value is label for value in truth),
        }
    safe_tp = sum(safe_to_cite(a) and safe_to_cite(b) for a, b in zip(truth, guesses))
    safe_fp = sum(not safe_to_cite(a) and safe_to_cite(b) for a, b in zip(truth, guesses))
    safe_fn = sum(safe_to_cite(a) and not safe_to_cite(b) for a, b in zip(truth, guesses))
    unsafe_total = sum(not safe_to_cite(value) for value in truth)
    return {
        "accuracy": sum(a is b for a, b in zip(truth, guesses)) / len(truth),
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class": per_class,
        "confusion_matrix": matrix,
        "safe_to_cite_precision": safe_tp / (safe_tp + safe_fp) if safe_tp + safe_fp else 0.0,
        "safe_to_cite_recall": safe_tp / (safe_tp + safe_fn) if safe_tp + safe_fn else 0.0,
        "unsafe_citation_acceptance_rate": safe_fp / unsafe_total if unsafe_total else 0.0,
    }


def span_integrity_failure_rate(results: Sequence[ClaimSupportResult]) -> float:
    if not results:
        raise ValueError("at least one result is required")
    return sum(not result.source_integrity_pass for result in results) / len(results)


def usefulness_gate(metrics: Mapping[str, float]) -> tuple[str, dict[str, bool]]:
    conditions = {
        "macro_f1": metrics["macro_f1"] >= 0.75,
        "supported_precision": metrics["supported_precision"] >= 0.85,
        "unsafe_acceptance": metrics["unsafe_acceptance"] <= 0.15,
        "span_integrity_failure": metrics["span_integrity_failure"] <= 0.05,
    }
    verdict = (
        "CLAIM_SUPPORT_VERIFIER_USEFUL"
        if all(conditions.values())
        else "CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE"
    )
    return verdict, conditions
