"""Phase 12 frozen dense/BM25/hybrid behavior and offline integrity tests."""

from __future__ import annotations

import math
import socket
import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from src.constraints.generate import check_grounding
from src.rag.corpus import CORPUS_VERSION, load_manifest
from src.rag.ingest import EMBED_MODEL_NAME, EMBED_MODEL_REVISION, EMBEDDING_DIMENSION, PreparedCorpus, prepare_corpus
from src.rag.retrieve import (
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    BM25_METHOD_ID,
    DENSE_METHOD_ID,
    EXPECTED_CHUNK_COUNT,
    HYBRID_CANDIDATE_K,
    HYBRID_METHOD_ID,
    RRF_K,
    TOKENIZER_VERSION,
    BM25Retriever,
    DenseRetriever,
    HybridRetriever,
    RetrievedChunk,
    RetrievalMethod,
    _model,
    _validate_dense_collection,
    clear_retriever_cache,
    frozen_corpus_identity,
    get_retriever,
    reciprocal_rank_fusion,
    tokenize,
)

FINGERPRINT = "a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753"


@pytest.fixture(scope="module")
def prepared() -> PreparedCorpus:
    return prepare_corpus()


@pytest.fixture(scope="module")
def bm25(prepared: PreparedCorpus) -> BM25Retriever:
    return BM25Retriever(prepared)


def tiny_prepared() -> PreparedCorpus:
    documents = [
        "rare evacuation route remains accessible",
        "temporary shelter sanitation and water",
        "shared flood shelter guidance",
        "shared logistics guidance",
    ]
    ids = ["chunk-z", "chunk-a", "chunk-c", "chunk-b"]
    metadatas = [
        {
            "source_id": f"source-{index % 3}",
            "source_document": f"source-{index % 3}.pdf",
            "page": index + 1,
            "chunk_index": 0,
            "corpus_version": CORPUS_VERSION,
        }
        for index in range(4)
    ]
    return PreparedCorpus(documents, metadatas, ids, {}, 4, 4)


def chunk(chunk_id: str, rank: int, method: str) -> RetrievedChunk:
    kwargs = {
        "dense_score": 0.1 * rank,
        "dense_rank": rank,
    } if method == DENSE_METHOD_ID else {
        "bm25_score": 10.0 / rank,
        "bm25_rank": rank,
    }
    return RetrievedChunk(
        text=f"text for {chunk_id}",
        source_document="source.pdf",
        source_id="source",
        page=1,
        score=0.1,
        chunk_id=chunk_id,
        retrieval_method=method,
        rank=rank,
        corpus_version=CORPUS_VERSION,
        corpus_fingerprint=FINGERPRINT,
        **kwargs,
    )


class FakeModel:
    def encode(self, queries, **_kwargs):
        return np.ones((len(queries), EMBEDDING_DIMENSION), dtype=np.float32)


class FakeCollection:
    def __init__(
        self,
        *,
        fingerprint: str = FINGERPRINT,
        version: str = CORPUS_VERSION,
        count: int = EXPECTED_CHUNK_COUNT,
    ):
        self.metadata = {
            "corpus_version": version,
            "corpus_fingerprint": fingerprint,
            "embedding_model": EMBED_MODEL_NAME,
            "embedding_revision": EMBED_MODEL_REVISION,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "hnsw:space": "cosine",
        }
        self._count = count

    def count(self):
        return self._count

    def query(self, *, n_results, **_kwargs):
        rows = [
            ("chunk-c", "third", "source-2", "two.pdf", 3, 0.3),
            ("chunk-a", "first", "source-0", "zero.pdf", 1, 0.1),
            ("chunk-b", "second", "source-1", "one.pdf", 2, 0.2),
        ][:n_results]
        return {
            "ids": [[row[0] for row in rows]],
            "documents": [[row[1] for row in rows]],
            "metadatas": [[
                {
                    "source_id": row[2],
                    "source_document": row[3],
                    "page": row[4],
                    "corpus_version": CORPUS_VERSION,
                }
                for row in rows
            ]],
            "distances": [[row[5] for row in rows]],
        }


class StaticRetriever:
    def __init__(self, method_id: str, results: list[RetrievedChunk], error=None):
        self.method_id = method_id
        self.results = results
        self.error = error
        self.requested: list[int] = []

    def retrieve(self, _query: str, k: int) -> list[RetrievedChunk]:
        self.requested.append(k)
        if self.error:
            raise self.error
        return self.results[:k]


def test_corpus_identity_is_frozen():
    assert frozen_corpus_identity() == (CORPUS_VERSION, FINGERPRINT)
    assert load_manifest()["fingerprint"] == FINGERPRINT


def test_exact_canonical_chunk_count(prepared: PreparedCorpus):
    assert len(prepared.ids) == EXPECTED_CHUNK_COUNT == 1797


def test_three_source_ids_are_represented(prepared: PreparedCorpus):
    assert len({metadata["source_id"] for metadata in prepared.metadatas}) == 3


def test_bm25_ids_exactly_match_canonical_ids(bm25: BM25Retriever, prepared: PreparedCorpus):
    assert set(bm25.chunk_ids) == set(prepared.ids)


def test_canonical_and_bm25_chunk_ids_have_no_duplicates(
    bm25: BM25Retriever, prepared: PreparedCorpus
):
    assert len(set(prepared.ids)) == len(prepared.ids)
    assert len(set(bm25.chunk_ids)) == len(bm25.chunk_ids)


def test_tokenizer_is_deterministic():
    assert tokenize("Flood-Safe Shelter Capacity") == tokenize(
        "Flood-Safe Shelter Capacity"
    )


def test_tokenizer_casefolds_and_splits_punctuation():
    assert tokenize("Flood-SAFE, shelter_capacity!") == ["flood", "safe", "shelter", "capacity"]


def test_tokenizer_empty_input():
    assert tokenize("") == []


def test_tokenizer_nfkc_normalizes_unicode():
    assert tokenize("ＦＬＯＯＤ café") == ["flood", "café"]


def test_tokenizer_version_is_frozen():
    assert TOKENIZER_VERSION == "nfkc-casefold-alphanumeric-v1"


def test_dense_common_interface_and_complete_metadata():
    results = DenseRetriever(model=FakeModel(), collection=FakeCollection()).retrieve(
        "evacuation", 3
    )
    assert [result.chunk_id for result in results] == ["chunk-a", "chunk-b", "chunk-c"]
    assert all(result.filename == result.source_document for result in results)
    assert all(result.source_id and result.page and result.text for result in results)
    assert all(result.corpus_version == CORPUS_VERSION for result in results)
    assert all(result.corpus_fingerprint == FINGERPRINT for result in results)


def test_dense_method_and_cosine_distance_metadata():
    result = DenseRetriever(model=FakeModel(), collection=FakeCollection()).retrieve("x", 1)[0]
    assert result.retrieval_method == DENSE_METHOD_ID
    assert result.score == result.dense_score == 0.3
    assert result.dense_rank == result.rank == 1


def test_dense_is_deterministic():
    retriever = DenseRetriever(model=FakeModel(), collection=FakeCollection())
    first = [result.chunk_id for result in retriever.retrieve("same", 3)]
    second = [result.chunk_id for result in retriever.retrieve("same", 3)]
    assert first == second


def test_dense_rejects_duplicate_backend_chunk_ids():
    collection = FakeCollection()
    original_query = collection.query

    def duplicate_query(**kwargs):
        result = original_query(**kwargs)
        result["ids"][0][1] = result["ids"][0][0]
        return result

    collection.query = duplicate_query
    with pytest.raises(ValueError, match="duplicate chunk IDs"):
        DenseRetriever(model=FakeModel(), collection=collection).retrieve("query", 3)


def test_dense_model_loader_is_offline_only(monkeypatch: pytest.MonkeyPatch):
    calls = []

    class FakeSentenceTransformer:
        def __init__(self, name, **kwargs):
            calls.append((name, kwargs))

    _model.cache_clear()
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )
    _model()
    assert calls[0][1] == {"local_files_only": True, "revision": EMBED_MODEL_REVISION}
    _model.cache_clear()


def test_bm25_parameters_are_explicit():
    assert (BM25_K1, BM25_B, BM25_EPSILON) == (1.5, 0.75, 0.25)


def test_bm25_exact_lexical_fixture_ranks_expected_passage():
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    result = retriever.retrieve("rare evacuation accessible", 2)
    assert result[0].chunk_id == "chunk-z"
    assert result[0].retrieval_method == BM25_METHOD_ID
    assert result[0].bm25_score == result[0].score


def test_bm25_no_overlap_returns_empty():
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    assert retriever.retrieve("xylophonicword", 5) == []


def test_bm25_is_deterministic_and_ties_use_chunk_id():
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    first = retriever.retrieve("shared", 5)
    second = retriever.retrieve("shared", 5)
    assert [result.chunk_id for result in first] == ["chunk-b", "chunk-c"]
    assert first == second


def test_bm25_preserves_original_source_page_and_text():
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    result = retriever.retrieve("sanitation", 1)[0]
    assert (result.source_id, result.filename, result.page, result.text) == (
        "source-1",
        "source-1.pdf",
        2,
        "temporary shelter sanitation and water",
    )


def test_real_bm25_returns_unique_citable_results(bm25: BM25Retriever):
    results = bm25.retrieve("relief camp sanitation", 5)
    assert len(results) == 5
    assert len({result.chunk_id for result in results}) == 5
    assert all(result.source_id and result.filename and result.page and result.text for result in results)


def test_rrf_synthetic_fixture_exact_values_and_order():
    dense = [chunk(name, rank, DENSE_METHOD_ID) for rank, name in enumerate("ABC", 1)]
    lexical = [chunk(name, rank, BM25_METHOD_ID) for rank, name in enumerate("CAD", 1)]
    fused = reciprocal_rank_fusion(dense, lexical)
    assert [result.chunk_id for result in fused] == ["A", "C", "B", "D"]
    values = {result.chunk_id: result.fusion_score for result in fused}
    assert values["A"] == pytest.approx(1 / 61 + 1 / 62)
    assert values["B"] == pytest.approx(1 / 62)
    assert values["C"] == pytest.approx(1 / 63 + 1 / 61)
    assert values["D"] == pytest.approx(1 / 63)


def test_rrf_component_contributions_and_metadata():
    dense = [chunk("A", 1, DENSE_METHOD_ID), chunk("B", 2, DENSE_METHOD_ID)]
    lexical = [chunk("A", 2, BM25_METHOD_ID)]
    results = reciprocal_rank_fusion(dense, lexical)
    assert results[0].dense_rank == 1 and results[0].bm25_rank == 2
    assert results[1].dense_rank == 2 and results[1].bm25_rank is None
    assert all(result.retrieval_method == HYBRID_METHOD_ID for result in results)


def test_rrf_ties_break_by_chunk_id():
    result = reciprocal_rank_fusion(
        [chunk("B", 1, DENSE_METHOD_ID)], [chunk("A", 1, BM25_METHOD_ID)]
    )
    assert [item.chunk_id for item in result] == ["A", "B"]


def test_rrf_union_deduplicates_cross_method_chunk_ids():
    result = reciprocal_rank_fusion(
        [chunk("A", 1, DENSE_METHOD_ID)], [chunk("A", 1, BM25_METHOD_ID)]
    )
    assert len(result) == 1


def test_rrf_rejects_duplicate_ids_inside_one_ranking():
    with pytest.raises(ValueError, match="duplicate chunk_id"):
        reciprocal_rank_fusion(
            [chunk("A", 1, DENSE_METHOD_ID), chunk("A", 2, DENSE_METHOD_ID)], []
        )


def test_rrf_rejects_same_id_with_different_citation_content():
    altered = replace(chunk("A", 1, BM25_METHOD_ID), page=99)
    with pytest.raises(ValueError, match="metadata mismatch"):
        reciprocal_rank_fusion([chunk("A", 1, DENSE_METHOD_ID)], [altered])


def test_hybrid_candidate_pool_and_top_k():
    dense = StaticRetriever(DENSE_METHOD_ID, [chunk("A", 1, DENSE_METHOD_ID)])
    bm25 = StaticRetriever(BM25_METHOD_ID, [chunk("B", 1, BM25_METHOD_ID)])
    result = HybridRetriever(dense, bm25).retrieve("query", 1)
    assert dense.requested == bm25.requested == [HYBRID_CANDIDATE_K]
    assert len(result) == 1


def test_hybrid_candidate_pool_expands_for_large_k():
    dense = StaticRetriever(DENSE_METHOD_ID, [])
    bm25 = StaticRetriever(BM25_METHOD_ID, [])
    HybridRetriever(dense, bm25).retrieve("query", 25)
    assert dense.requested == bm25.requested == [25]


def test_hybrid_bm25_empty_fallback_returns_dense_results():
    dense = StaticRetriever(DENSE_METHOD_ID, [chunk("A", 1, DENSE_METHOD_ID)])
    bm25 = StaticRetriever(BM25_METHOD_ID, [])
    result = HybridRetriever(dense, bm25).retrieve("query", 5)
    assert [item.chunk_id for item in result] == ["A"]
    assert result[0].dense_rank == 1 and result[0].bm25_rank is None


def test_hybrid_does_not_suppress_dense_failure():
    dense = StaticRetriever(DENSE_METHOD_ID, [], RuntimeError("dense failed"))
    bm25 = StaticRetriever(BM25_METHOD_ID, [])
    with pytest.raises(RuntimeError, match="dense failed"):
        HybridRetriever(dense, bm25).retrieve("query", 5)


def test_rrf_constant_is_exactly_60():
    assert RRF_K == 60


def test_factory_supports_all_three_methods():
    clear_retriever_cache()
    assert isinstance(get_retriever(RetrievalMethod.DENSE), DenseRetriever)
    assert isinstance(get_retriever("bm25"), BM25Retriever)
    assert isinstance(get_retriever("hybrid-rrf-v1"), HybridRetriever)
    clear_retriever_cache()


@pytest.mark.parametrize("bad_query", ["", "   "])
def test_empty_or_whitespace_query_rejected(bad_query: str):
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    with pytest.raises(ValueError, match="query"):
        retriever.retrieve(bad_query, 1)


@pytest.mark.parametrize("bad_k", [0, -1, True, 1.5])
def test_invalid_k_rejected(bad_k):
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    with pytest.raises(ValueError, match="k"):
        retriever.retrieve("query", bad_k)


def test_k_greater_than_available_is_safe():
    retriever = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    assert len(retriever.retrieve("shared", 100)) == 2


def test_wrong_dense_corpus_fingerprint_rejected():
    with pytest.raises(ValueError, match="fingerprint"):
        _validate_dense_collection(FakeCollection(fingerprint="0" * 64))


def test_wrong_dense_corpus_version_rejected():
    with pytest.raises(ValueError, match="version"):
        _validate_dense_collection(FakeCollection(version="wrong-version"))


def test_wrong_dense_chunk_count_rejected():
    with pytest.raises(ValueError, match="expected 1797"):
        _validate_dense_collection(FakeCollection(count=1796))


def test_offline_bm25_and_hybrid_make_no_network_calls(monkeypatch: pytest.MonkeyPatch):
    def fail_network(*_args, **_kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    lexical = BM25Retriever(tiny_prepared(), expected_chunk_count=4)
    lexical_result = lexical.retrieve("shelter", 2)
    dense = StaticRetriever(DENSE_METHOD_ID, [chunk("A", 1, DENSE_METHOD_ID)])
    hybrid = HybridRetriever(dense, lexical)
    assert lexical_result
    assert hybrid.retrieve("shelter", 2)


def test_same_chunk_across_methods_has_identical_citation_fields():
    dense = chunk("A", 1, DENSE_METHOD_ID)
    lexical = chunk("A", 2, BM25_METHOD_ID)
    fused = reciprocal_rank_fusion([dense], [lexical])[0]
    for result in (dense, lexical, fused):
        assert (result.text, result.source_id, result.filename, result.page) == (
            "text for A", "source", "source.pdf", 1
        )


def test_existing_citation_verifier_accepts_hybrid_result():
    result = reciprocal_rank_fusion(
        [chunk("A", 1, DENSE_METHOD_ID)], [chunk("A", 2, BM25_METHOD_ID)]
    )[0]
    payload = {"constraints": [{"action_id": "S1", "source_excerpt": "text for A"}]}
    assert check_grounding(payload, [result]) == []
    assert payload["constraints"][0]["citation_verified"] is True


def test_no_python_hash_used_for_corpus_identity():
    assert frozen_corpus_identity()[1] == FINGERPRINT
    assert len(FINGERPRINT) == 64 and all(character in "0123456789abcdef" for character in FINGERPRINT)


def test_rrf_formula_does_not_mix_raw_score_magnitudes():
    dense = replace(chunk("A", 1, DENSE_METHOD_ID), dense_score=999999.0)
    lexical = replace(chunk("B", 1, BM25_METHOD_ID), bm25_score=-999999.0)
    result = reciprocal_rank_fusion([dense], [lexical])
    assert result[0].fusion_score == result[1].fusion_score == pytest.approx(1 / 61)
    assert math.isfinite(result[0].fusion_score)
