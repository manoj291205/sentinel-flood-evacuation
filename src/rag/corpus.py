"""Provenance and integrity helpers for the frozen authoritative PDF corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DOCS_DIR = PROJECT_ROOT / "data" / "raw_docs"
MANIFEST_PATH = RAW_DOCS_DIR / "MANIFEST.json"
EXCLUDED_SOURCES_PATH = RAW_DOCS_DIR / "excluded_sources.json"

CORPUS_VERSION = "v3-authoritative-corpus-v1"
FINGERPRINT_FORMAT = "UTF-8 lines sorted by source_id: <source_id>\\t<sha256>\\n"
ALLOWED_TOPICS = frozenset(
    {
        "flood_management",
        "evacuation",
        "shelter",
        "vulnerability_accessibility",
        "logistics_transport",
    }
)
ALLOWED_AUTHORITY_CLASSES = frozenset(
    {
        "INDIA_NATIONAL_GOVERNMENT",
        "INDIA_STATE_GOVERNMENT",
        "INTERGOVERNMENTAL",
        "INTERNATIONAL_HUMANITARIAN",
        "OTHER_AUTHORITATIVE",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def corpus_fingerprint(documents: Iterable[dict[str, Any]]) -> str:
    """Hash sorted canonical source identity/hash pairs, independent of manifest order."""
    lines = sorted(
        f"{document['source_id']}\t{document['sha256']}\n"
        for document in documents
        if document.get("duplicate_of") is None
    )
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def canonical_documents(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    value = manifest or load_manifest()
    return [item for item in value["documents"] if item.get("duplicate_of") is None]


def documents_by_filename(manifest: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    return {item["filename"]: item for item in canonical_documents(manifest)}


def validate_manifest(
    manifest: dict[str, Any] | None = None,
    *,
    raw_docs_dir: Path = RAW_DOCS_DIR,
    verify_files: bool = True,
) -> list[dict[str, Any]]:
    value = manifest or load_manifest()
    if value.get("corpus_version") != CORPUS_VERSION:
        raise ValueError(f"unexpected corpus version: {value.get('corpus_version')!r}")
    documents = canonical_documents(value)
    if len(documents) < 3:
        raise ValueError("authoritative corpus requires at least three canonical documents")
    source_ids = [item["source_id"] for item in documents]
    filenames = [item["filename"] for item in documents]
    hashes = [item["sha256"] for item in documents]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("canonical source IDs must be unique")
    if len(filenames) != len(set(filenames)):
        raise ValueError("canonical filenames must be unique")
    if len(hashes) != len(set(hashes)):
        raise ValueError("exact-hash duplicates cannot be canonical documents")
    for item in documents:
        if not item.get("publisher") or not item.get("url"):
            raise ValueError(f"missing publisher/provenance URL for {item['source_id']}")
        if item.get("authority_class") not in ALLOWED_AUTHORITY_CLASSES:
            raise ValueError(f"invalid authority class for {item['source_id']}")
        if not set(item.get("topics", [])).issubset(ALLOWED_TOPICS):
            raise ValueError(f"invalid topic for {item['source_id']}")
        digest = item.get("sha256", "")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid SHA-256 for {item['source_id']}")
        if int(item.get("pages", 0)) <= 0:
            raise ValueError(f"invalid page count for {item['source_id']}")
        if len(item.get("spot_checks", [])) < 3:
            raise ValueError(f"fewer than three spot checks for {item['source_id']}")
        if verify_files:
            path = raw_docs_dir / item["filename"]
            if not path.is_file():
                raise FileNotFoundError(path)
            if path.stat().st_size != item["bytes"]:
                raise ValueError(f"byte count mismatch for {item['source_id']}")
            if sha256_file(path) != digest:
                raise ValueError(f"SHA-256 mismatch for {item['source_id']}")
    expected = corpus_fingerprint(documents)
    if value.get("fingerprint") != expected:
        raise ValueError("corpus fingerprint does not match canonical source hashes")
    return documents
