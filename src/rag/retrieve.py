"""Offline dense, BM25, and hybrid-RRF retrieval over one frozen chunk corpus.

The module-level :func:`retrieve` remains the dense compatibility API used by the V1
demo and Gemini integration. New code selects a retriever once through
:func:`get_retriever`; every returned result uses the same ``RetrievedChunk`` model.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Protocol, Sequence

from .corpus import CORPUS_VERSION, corpus_fingerprint, load_manifest, validate_manifest
from .ingest import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL_NAME, PreparedCorpus, prepare_corpus

RETRIEVAL_CONFIG_VERSION = "v3-retrieval-v1"
DENSE_METHOD_ID = "dense-minilm-v1"
BM25_METHOD_ID = "bm25-okapi-v1"
HYBRID_METHOD_ID = "hybrid-rrf-v1"
TOKENIZER_VERSION = "nfkc-casefold-alphanumeric-v1"

EXPECTED_CHUNK_COUNT = 1797
DENSE_SCORE_TYPE = "cosine_distance"
BM25_K1 = 1.5
BM25_B = 0.75
BM25_EPSILON = 0.25
RRF_K = 60
HYBRID_CANDIDATE_K = 20

_TOKEN_PATTERN = re.compile(r"[^\W_]+", flags=re.UNICODE)


class RetrievalMethod(str, Enum):
    DENSE = "dense"
    BM25 = "bm25"
    HYBRID_RRF = "hybrid"


@dataclass(frozen=True)
class RetrievedChunk:
    """One immutable citation passage plus method-specific retrieval provenance.

    The first five fields preserve the historical constructor and ``score`` API. For
    dense results, ``score`` is cosine distance (lower is better); for BM25 and hybrid
    results it is respectively BM25 or RRF score (higher is better).
    """

    text: str
    source_document: str
    page: int
    score: float
    source_id: str = ""
    chunk_id: str = ""
    retrieval_method: str = DENSE_METHOD_ID
    rank: int = 0
    dense_score: float | None = None
    dense_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    fusion_score: float | None = None
    fusion_rank: int | None = None
    corpus_version: str | None = None
    corpus_fingerprint: str | None = None

    @property
    def filename(self) -> str:
        """Common-schema filename alias for the historical source_document field."""
        return self.source_document

    def citation(self) -> str:
        return f"{self.source_document}, page {self.page}"


class Retriever(Protocol):
    method_id: str

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]: ...


def tokenize(text: str) -> list[str]:
    """NFKC + casefold + Unicode alphanumeric tokens; no stopwords or stemming."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _TOKEN_PATTERN.findall(normalized)


def _validate_request(query: str, k: int) -> str:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain non-whitespace text")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be an integer >= 1")
    return query


@lru_cache(maxsize=1)
def frozen_corpus_identity() -> tuple[str, str]:
    manifest = load_manifest()
    documents = validate_manifest(manifest, verify_files=False)
    fingerprint = corpus_fingerprint(documents)
    if manifest.get("fingerprint") != fingerprint:
        raise ValueError("manifest corpus fingerprint is invalid")
    return manifest["corpus_version"], fingerprint


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL_NAME, local_files_only=True)


def _validate_dense_collection(collection) -> None:
    version, fingerprint = frozen_corpus_identity()
    metadata = collection.metadata or {}
    if metadata.get("corpus_version") != version:
        raise ValueError("dense index corpus version does not match the frozen corpus")
    if metadata.get("corpus_fingerprint") != fingerprint:
        raise ValueError("dense index corpus fingerprint does not match the frozen corpus")
    if collection.count() != EXPECTED_CHUNK_COUNT:
        raise ValueError(
            f"dense index contains {collection.count()} chunks; expected {EXPECTED_CHUNK_COUNT}"
        )


@lru_cache(maxsize=1)
def _collection():
    import chromadb

    if not Path(CHROMA_DIR).exists():
        raise FileNotFoundError(
            f"No Chroma store at {CHROMA_DIR}.\n"
            "Build it first:  .venv/bin/python -m src.rag.ingest"
        )
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(name=COLLECTION_NAME)
    _validate_dense_collection(collection)
    return collection


class DenseRetriever:
    """Existing MiniLM/Chroma baseline with explicit identity and score semantics."""

    method_id = DENSE_METHOD_ID

    def __init__(self, *, model=None, collection=None) -> None:
        self._embedding_model = model
        self._dense_collection = collection

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        query = _validate_request(query, k)
        model = self._embedding_model if self._embedding_model is not None else _model()
        collection = (
            self._dense_collection if self._dense_collection is not None else _collection()
        )
        _validate_dense_collection(collection)
        limit = min(k, collection.count())
        embedding = model.encode([query], convert_to_numpy=True).tolist()
        result = collection.query(
            query_embeddings=embedding,
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )
        version, fingerprint = frozen_corpus_identity()
        rows = sorted(
            zip(
                result["ids"][0],
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            ),
            key=lambda row: (float(row[3]), str(row[0])),
        )
        if len({str(row[0]) for row in rows}) != len(rows):
            raise ValueError("dense backend returned duplicate chunk IDs")
        return [
            RetrievedChunk(
                chunk_id=str(chunk_id),
                text=text,
                source_document=str(metadata["source_document"]),
                source_id=str(metadata["source_id"]),
                page=int(metadata["page"]),
                score=float(distance),
                retrieval_method=self.method_id,
                rank=rank,
                dense_score=float(distance),
                dense_rank=rank,
                corpus_version=version,
                corpus_fingerprint=fingerprint,
            )
            for rank, (chunk_id, text, metadata, distance) in enumerate(rows, start=1)
        ]


@dataclass(frozen=True)
class _LexicalRecord:
    chunk_id: str
    text: str
    source_id: str
    source_document: str
    page: int
    chunk_index: int


class BM25Retriever:
    """Small, explicit Okapi BM25 implementation over the canonical extracted chunks."""

    method_id = BM25_METHOD_ID
    k1 = BM25_K1
    b = BM25_B
    epsilon = BM25_EPSILON
    tokenizer_version = TOKENIZER_VERSION

    def __init__(
        self,
        prepared: PreparedCorpus | None = None,
        *,
        expected_chunk_count: int = EXPECTED_CHUNK_COUNT,
    ) -> None:
        prepared = prepared or prepare_corpus()
        if len(prepared.ids) != expected_chunk_count:
            raise ValueError(
                f"BM25 input contains {len(prepared.ids)} chunks; expected {expected_chunk_count}"
            )
        if len(prepared.ids) != len(set(prepared.ids)):
            raise ValueError("BM25 input contains duplicate chunk IDs")
        packed = zip(prepared.ids, prepared.documents, prepared.metadatas)
        self.records = tuple(
            sorted(
                (
                    _LexicalRecord(
                        chunk_id=chunk_id,
                        text=text,
                        source_id=str(metadata["source_id"]),
                        source_document=str(metadata["source_document"]),
                        page=int(metadata["page"]),
                        chunk_index=int(metadata["chunk_index"]),
                    )
                    for chunk_id, text, metadata in packed
                ),
                key=lambda row: (row.source_id, row.page, row.chunk_index, row.chunk_id),
            )
        )
        self.chunk_ids = tuple(record.chunk_id for record in self.records)
        self._tokens = tuple(tuple(tokenize(record.text)) for record in self.records)
        self._term_frequencies = tuple(Counter(tokens) for tokens in self._tokens)
        self._lengths = tuple(len(tokens) for tokens in self._tokens)
        self._average_length = sum(self._lengths) / len(self._lengths)
        document_frequency: Counter[str] = Counter()
        for frequencies in self._term_frequencies:
            document_frequency.update(frequencies.keys())
        self.vocabulary = frozenset(document_frequency)
        raw_idf = {
            token: math.log((len(self.records) - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }
        average_idf = sum(raw_idf.values()) / len(raw_idf)
        floor = self.epsilon * average_idf
        self._idf = {
            token: (value if value >= 0 else floor) for token, value in raw_idf.items()
        }

    def _score(self, query_tokens: Sequence[str], index: int) -> float:
        frequencies = self._term_frequencies[index]
        length = self._lengths[index]
        score = 0.0
        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if not frequency:
                continue
            denominator = frequency + self.k1 * (
                1 - self.b + self.b * length / self._average_length
            )
            score += self._idf[token] * frequency * (self.k1 + 1) / denominator
        return score

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        query = _validate_request(query, k)
        query_tokens = tokenize(query)
        overlap = set(query_tokens) & self.vocabulary
        if not overlap:
            return []
        candidates = [
            (self._score(query_tokens, index), record)
            for index, record in enumerate(self.records)
            if overlap & self._term_frequencies[index].keys()
        ]
        candidates.sort(key=lambda item: (-item[0], item[1].chunk_id))
        version, fingerprint = frozen_corpus_identity()
        return [
            RetrievedChunk(
                chunk_id=record.chunk_id,
                text=record.text,
                source_document=record.source_document,
                source_id=record.source_id,
                page=record.page,
                score=float(score),
                retrieval_method=self.method_id,
                rank=rank,
                bm25_score=float(score),
                bm25_rank=rank,
                corpus_version=version,
                corpus_fingerprint=fingerprint,
            )
            for rank, (score, record) in enumerate(candidates[:k], start=1)
        ]


def _same_logical_chunk(left: RetrievedChunk, right: RetrievedChunk) -> bool:
    return (
        left.source_id,
        left.source_document,
        left.page,
        left.text,
    ) == (
        right.source_id,
        right.source_document,
        right.page,
        right.text,
    )


def reciprocal_rank_fusion(
    dense_results: Iterable[RetrievedChunk],
    bm25_results: Iterable[RetrievedChunk],
    *,
    rrf_k: int = RRF_K,
) -> list[RetrievedChunk]:
    """Fuse two ranked lists by stable chunk ID and deterministic score/ID ordering."""
    if rrf_k < 1:
        raise ValueError("rrf_k must be >= 1")
    entries: dict[str, dict[str, object]] = {}
    for label, results in (("dense", dense_results), ("bm25", bm25_results)):
        seen: set[str] = set()
        for fallback_rank, chunk in enumerate(results, start=1):
            if not chunk.chunk_id:
                raise ValueError("RRF requires a non-empty stable chunk_id")
            if chunk.chunk_id in seen:
                raise ValueError(f"duplicate chunk_id in {label} ranking: {chunk.chunk_id}")
            seen.add(chunk.chunk_id)
            rank = chunk.rank or fallback_rank
            entry = entries.setdefault(
                chunk.chunk_id,
                {"chunk": chunk, "score": 0.0, "dense": None, "bm25": None},
            )
            existing = entry["chunk"]
            if not isinstance(existing, RetrievedChunk) or not _same_logical_chunk(existing, chunk):
                raise ValueError(f"chunk metadata mismatch across methods: {chunk.chunk_id}")
            entry["score"] = float(entry["score"]) + 1.0 / (rrf_k + rank)
            entry[label] = chunk

    ordered = sorted(entries.items(), key=lambda item: (-float(item[1]["score"]), item[0]))
    fused: list[RetrievedChunk] = []
    for fusion_rank, (_chunk_id, entry) in enumerate(ordered, start=1):
        base = entry["chunk"]
        dense = entry["dense"]
        bm25 = entry["bm25"]
        assert isinstance(base, RetrievedChunk)
        assert dense is None or isinstance(dense, RetrievedChunk)
        assert bm25 is None or isinstance(bm25, RetrievedChunk)
        score = float(entry["score"])
        fused.append(
            replace(
                base,
                score=score,
                retrieval_method=HYBRID_METHOD_ID,
                rank=fusion_rank,
                dense_score=dense.dense_score if dense else None,
                dense_rank=dense.rank if dense else None,
                bm25_score=bm25.bm25_score if bm25 else None,
                bm25_rank=bm25.rank if bm25 else None,
                fusion_score=score,
                fusion_rank=fusion_rank,
            )
        )
    return fused


class HybridRetriever:
    method_id = HYBRID_METHOD_ID
    rrf_k = RRF_K
    candidate_k = HYBRID_CANDIDATE_K

    def __init__(self, dense: Retriever, bm25: Retriever) -> None:
        self.dense = dense
        self.bm25 = bm25

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        query = _validate_request(query, k)
        candidate_k = max(self.candidate_k, k)
        dense_results = self.dense.retrieve(query, candidate_k)
        bm25_results = self.bm25.retrieve(query, candidate_k)
        return reciprocal_rank_fusion(
            dense_results, bm25_results, rrf_k=self.rrf_k
        )[:k]


def _normalize_method(method: RetrievalMethod | str) -> RetrievalMethod:
    aliases = {
        "dense": RetrievalMethod.DENSE,
        DENSE_METHOD_ID: RetrievalMethod.DENSE,
        "bm25": RetrievalMethod.BM25,
        BM25_METHOD_ID: RetrievalMethod.BM25,
        "hybrid": RetrievalMethod.HYBRID_RRF,
        "hybrid_rrf": RetrievalMethod.HYBRID_RRF,
        HYBRID_METHOD_ID: RetrievalMethod.HYBRID_RRF,
    }
    key = method.value if isinstance(method, RetrievalMethod) else str(method).casefold()
    if key not in aliases:
        raise ValueError(f"unknown retrieval method: {method!r}")
    return aliases[key]


@lru_cache(maxsize=3)
def _construct_retriever(selected: RetrievalMethod) -> Retriever:
    if selected is RetrievalMethod.DENSE:
        return DenseRetriever()
    if selected is RetrievalMethod.BM25:
        return BM25Retriever()
    return HybridRetriever(
        _construct_retriever(RetrievalMethod.DENSE),
        _construct_retriever(RetrievalMethod.BM25),
    )


def get_retriever(method: RetrievalMethod | str = RetrievalMethod.DENSE) -> Retriever:
    return _construct_retriever(_normalize_method(method))


def clear_retriever_cache() -> None:
    """Clear constructed retrievers; primarily useful for tests and sanity runs."""
    _construct_retriever.cache_clear()


def retrieve(query: str, k: int = 3) -> list[RetrievedChunk]:
    """Backward-compatible dense retrieval used by existing application code."""
    return get_retriever(RetrievalMethod.DENSE).retrieve(query, k)
