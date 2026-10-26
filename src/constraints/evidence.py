"""Offline authentication for operational citations, separate from frozen metric helpers."""

from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType

from src.rag.corpus import load_manifest, validate_manifest
from src.rag.ingest import prepare_corpus

from .claim_support import (
    ClaimSupportResult, EvidenceChunk, get_chunk_by_id, safe_to_cite,
    validate_supporting_spans, verify_evidence_integrity,
)

CANONICAL_CORPUS_FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"


@lru_cache(maxsize=1)
def _canonical_chunks():
    manifest = load_manifest()
    if manifest.get("fingerprint") != CANONICAL_CORPUS_FINGERPRINT:
        raise ValueError("operational corpus does not match the approved corpus fingerprint")
    validate_manifest(manifest)  # Authenticate the PDF bytes before trusting extracted chunks.
    prepared = prepare_corpus()
    if len(prepared.ids) != len(set(prepared.ids)):
        raise ValueError("canonical corpus contains duplicate chunk IDs")
    return MappingProxyType({key: get_chunk_by_id(key, prepared) for key in prepared.ids})


def get_authenticated_evidence(chunk_id: str) -> EvidenceChunk:
    """Resolve only from the verified local PDFs, never from caller-provided corpus objects."""
    if not isinstance(chunk_id, str) or chunk_id not in _canonical_chunks():
        raise ValueError("evidence chunk is not a member of the approved corpus")
    return _canonical_chunks()[chunk_id]


def authenticate_evidence(evidence: EvidenceChunk) -> bool:
    try:
        canonical = get_authenticated_evidence(evidence.chunk_id)
    except (AttributeError, KeyError, OSError, ValueError):
        return False
    return evidence == canonical and verify_evidence_integrity(evidence)


def authenticate_evidence_reference(source_id: str, page: int, chunk_id: str) -> dict:
    chunk = get_authenticated_evidence(chunk_id)
    if type(page) is not int or (chunk.source_id, chunk.page) != (source_id, page):
        raise ValueError("evidence reference does not match its canonical source and page")
    return {"source_id": chunk.source_id, "page": chunk.page, "chunk_id": chunk.chunk_id,
            "filename": chunk.filename, "passage_sha256": chunk.passage_sha256,
            "corpus_fingerprint": CANONICAL_CORPUS_FINGERPRINT}


def operational_citation_eligible(result: ClaimSupportResult, evidence: EvidenceChunk) -> bool:
    """Require authenticated membership and verbatim spans in addition to semantic support."""
    return (result.source_integrity_pass is True and safe_to_cite(result.verdict)
            and authenticate_evidence(evidence)
            and validate_supporting_spans(evidence, result.supporting_spans))
