"""Chunk and embed the real guideline PDFs into a local Chroma collection.

Everything in this module runs locally on CPU:
  - text extraction: pypdf
  - embeddings: sentence-transformers all-MiniLM-L6-v2 (downloads ~90MB once, then offline)
  - vector store: Chroma PersistentClient on disk

No API key and no network call is involved once the embedding model is cached.

Run:  .venv/bin/python -m src.rag.ingest
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DOCS_DIR = PROJECT_ROOT / "data" / "raw_docs"
CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"

COLLECTION_NAME = "flood_guidelines"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Chunking is page-scoped: a chunk never spans a page boundary, so every chunk keeps an
# exact page number and Step 3 can cite "document, page N" truthfully.
CHUNK_CHARS = 1000
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 200  # drops cover pages, page furniture, stray headers


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return [(1-based page number, text)] for pages that have a usable text layer."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - a bad page shouldn't kill the run
            print(f"    page {index}: extraction error ({exc}) -- skipped")
            continue
        # Normalise whitespace; PDF extraction is noisy about line breaks.
        text = " ".join(text.split())
        if text:
            pages.append((index, text))
    return pages


def chunk_page(text: str) -> list[str]:
    """Split one page's text into overlapping windows."""
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


def build_index() -> int:
    pdf_paths = sorted(RAW_DOCS_DIR.glob("*.pdf"))
    if not pdf_paths:
        print(
            "No PDFs in data/raw_docs/.\n"
            "Run:  .venv/bin/python -m src.rag.fetch_docs\n"
            "This step will not invent a corpus -- it needs real documents."
        )
        return 1

    print(f"Found {len(pdf_paths)} document(s) in data/raw_docs/\n")

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    for pdf_path in pdf_paths:
        print(f"[{pdf_path.name}]")
        pages = extract_pages(pdf_path)
        total_chars = sum(len(t) for _, t in pages)
        print(f"  pages with a text layer: {len(pages)}")
        print(f"  characters extracted: {total_chars:,}")

        # A scanned PDF has no text layer; pypdf returns almost nothing and OCR is out of
        # scope for this prototype. Surface that loudly instead of indexing emptiness.
        if total_chars < 5000:
            print(
                f"  WARNING: very little text extracted from {pdf_path.name}. This PDF may be\n"
                f"           a scanned image rather than digital text. No OCR fallback exists\n"
                f"           in this prototype."
            )

        kept = 0
        for page_number, page_text in pages:
            for chunk_index, chunk in enumerate(chunk_page(page_text)):
                if len(chunk) < MIN_CHUNK_CHARS:
                    continue
                documents.append(chunk)
                metadatas.append(
                    {
                        # Field name matches the Step 3 constraint schema's source_document.
                        "source_document": pdf_path.name,
                        "page": page_number,
                        "chunk_index": chunk_index,
                    }
                )
                ids.append(f"{pdf_path.stem}-p{page_number}-c{chunk_index}")
                kept += 1
        print(f"  chunks kept: {kept}\n")

    if not documents:
        print("No chunks survived filtering -- nothing to index.")
        return 1

    print(f"Total chunks to embed: {len(documents)}")
    print(f"Loading embedding model '{EMBED_MODEL_NAME}' (local, CPU)...")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL_NAME)
    embeddings = model.encode(
        documents, batch_size=64, show_progress_bar=True, convert_to_numpy=True
    )
    print(f"Embedded {embeddings.shape[0]} chunks, dimension {embeddings.shape[1]}")

    # Rebuild from scratch so re-running is idempotent rather than duplicating chunks.
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # No embedding_function is set: we pass our own vectors, so Chroma never silently
    # falls back to downloading and using its default embedding model.
    collection = client.create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings.tolist(),
    )

    print(f"\nIndexed {collection.count()} chunks into '{COLLECTION_NAME}'")
    print(f"Chroma store: {CHROMA_DIR}  (gitignored -- regenerate with this script)")
    return 0


if __name__ == "__main__":
    sys.exit(build_index())
