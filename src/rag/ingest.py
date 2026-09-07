"""Page-scoped dense ingestion for the frozen local authoritative corpus.

Text extraction, MiniLM embeddings, and Chroma storage all run locally. The committed
PDFs and cached embedding model make normal ingestion independent of web access.

Run:  .venv/bin/python -m src.rag.ingest
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .corpus import (
    CORPUS_VERSION,
    RAW_DOCS_DIR,
    corpus_fingerprint,
    load_manifest,
    validate_manifest,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"

COLLECTION_NAME = "v3_authoritative_corpus_v1"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# Existing page-scoped chunking remains the dense baseline for later retrieval phases.
CHUNK_CHARS = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 200


@dataclass(frozen=True)
class PreparedCorpus:
    documents: list[str]
    metadatas: list[dict[str, Any]]
    ids: list[str]
    source_chunk_counts: dict[str, int]
    page_count: int
    text_page_count: int


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return readable 1-based PDF pages, preserving the citation boundary."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - isolate a bad page, do not hide it
            print(f"    page {index}: extraction error ({exc}) -- skipped")
            continue
        # Corel-generated NDMA PDFs encode a common "ti" ligature as NUL. Repairing that
        # extraction artifact makes words such as evacuation searchable without changing
        # the underlying page or citation. Whitespace normalization is the existing rule.
        text = " ".join(text.replace("\x00", "ti").split())
        if text:
            pages.append((index, text))
    return pages


def chunk_page(text: str) -> list[str]:
    """Split one page into the unchanged overlapping character windows."""
    if len(text) <= CHUNK_CHARS:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_CHARS
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return chunks


def prepare_corpus(*, raw_docs_dir: Path = RAW_DOCS_DIR) -> PreparedCorpus:
    """Verify canonical files, extract pages, and create stable chunk records."""
    manifest = load_manifest(raw_docs_dir / "MANIFEST.json")
    canonical = validate_manifest(manifest, raw_docs_dir=raw_docs_dir)
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    ids: list[str] = []
    source_chunk_counts: dict[str, int] = {}
    text_page_count = 0

    for source in canonical:
        pdf_path = raw_docs_dir / source["filename"]
        print(f"[{pdf_path.name}]")
        pages = extract_pages(pdf_path)
        total_chars = sum(len(text) for _, text in pages)
        text_page_count += len(pages)
        print(f"  pages with a text layer: {len(pages)}/{source['pages']}")
        print(f"  characters extracted: {total_chars:,}")
        if total_chars < 5_000:
            raise ValueError(
                f"unusable extraction for {pdf_path.name}: only {total_chars} characters"
            )
        kept = 0
        for page_number, page_text in pages:
            for chunk_index, chunk in enumerate(chunk_page(page_text)):
                if len(chunk) < MIN_CHUNK_CHARS:
                    continue
                documents.append(chunk)
                metadatas.append(
                    {
                        "source_document": source["filename"],
                        "source_id": source["source_id"],
                        "source_sha256": source["sha256"],
                        "corpus_version": CORPUS_VERSION,
                        "page": page_number,
                        "chunk_index": chunk_index,
                    }
                )
                ids.append(f"{source['source_id']}-p{page_number}-c{chunk_index}")
                kept += 1
        source_chunk_counts[source["source_id"]] = kept
        print(f"  chunks kept: {kept}\n")

    if not documents:
        raise ValueError("no chunks survived filtering")
    return PreparedCorpus(
        documents,
        metadatas,
        ids,
        source_chunk_counts,
        sum(int(source["pages"]) for source in canonical),
        text_page_count,
    )


def build_index(
    *,
    model: Any | None = None,
    chroma_dir: Path = CHROMA_DIR,
    prepared: PreparedCorpus | None = None,
) -> int:
    prepared = prepared or prepare_corpus()
    manifest = load_manifest()
    fingerprint = corpus_fingerprint(validate_manifest(manifest))
    print(f"Total chunks to embed: {len(prepared.documents)}")
    if model is None:
        print(f"Loading embedding model '{EMBED_MODEL_NAME}' (local, CPU)...")
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBED_MODEL_NAME, local_files_only=True)
    embeddings = model.encode(
        prepared.documents,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    if embeddings.shape != (len(prepared.documents), EMBEDDING_DIMENSION):
        raise ValueError(f"unexpected embedding shape: {embeddings.shape}")
    print(f"Embedded {embeddings.shape[0]} chunks, dimension {embeddings.shape[1]}")

    if chroma_dir.exists():
        shutil.rmtree(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    import chromadb

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine",
            "corpus_version": CORPUS_VERSION,
            "corpus_fingerprint": fingerprint,
            "embedding_model": EMBED_MODEL_NAME,
            "embedding_dimension": EMBEDDING_DIMENSION,
        },
    )
    collection.add(
        ids=prepared.ids,
        documents=prepared.documents,
        metadatas=prepared.metadatas,
        embeddings=embeddings.tolist(),
    )
    print(f"\nIndexed {collection.count()} chunks into '{COLLECTION_NAME}'")
    print(f"Chroma store: {chroma_dir}  (gitignored; regenerated entirely offline)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(build_index())
    except (FileNotFoundError, ValueError) as exc:
        print(exc)
        sys.exit(1)
