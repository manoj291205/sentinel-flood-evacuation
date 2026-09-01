"""Local retrieval over the indexed NDMA/NIDM guideline chunks.

This is the module Step 3 (the Gemini constraint step) imports to get real guideline
text to ground its citations in. Runs entirely locally -- no API key, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .ingest import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL_NAME


@dataclass(frozen=True)
class RetrievedChunk:
    """One retrieved guideline passage, with enough provenance to cite it."""

    text: str
    source_document: str
    page: int
    score: float  # cosine distance; lower is closer

    def citation(self) -> str:
        return f"{self.source_document}, page {self.page}"


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL_NAME)


@lru_cache(maxsize=1)
def _collection():
    import chromadb

    if not Path(CHROMA_DIR).exists():
        raise FileNotFoundError(
            f"No Chroma store at {CHROMA_DIR}.\n"
            "Build it first:  .venv/bin/python -m src.rag.ingest"
        )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def retrieve(query: str, k: int = 3) -> list[RetrievedChunk]:
    """Return the k guideline chunks most similar to `query`."""
    embedding = _model().encode([query], convert_to_numpy=True).tolist()
    result = _collection().query(
        query_embeddings=embedding,
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[RetrievedChunk] = []
    for text, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        chunks.append(
            RetrievedChunk(
                text=text,
                source_document=meta["source_document"],
                page=int(meta["page"]),
                score=float(distance),
            )
        )
    return chunks
