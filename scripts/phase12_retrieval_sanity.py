#!/usr/bin/env python3
"""Run Phase 12 engineering smoke, determinism, and warmed-latency checks offline."""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.ingest import EMBEDDING_DIMENSION, EMBED_MODEL_NAME  # noqa: E402
from src.rag.retrieve import (  # noqa: E402
    BM25_B,
    BM25_EPSILON,
    BM25_K1,
    BM25_METHOD_ID,
    DENSE_METHOD_ID,
    DENSE_SCORE_TYPE,
    EXPECTED_CHUNK_COUNT,
    HYBRID_CANDIDATE_K,
    HYBRID_METHOD_ID,
    RETRIEVAL_CONFIG_VERSION,
    RRF_K,
    TOKENIZER_VERSION,
    RetrievalMethod,
    clear_retriever_cache,
    frozen_corpus_identity,
    get_retriever,
)

OUTPUT_PATH = PROJECT_ROOT / "data" / "eval_v3" / "phase12_retrieval_sanity.json"
QUERIES = [
    "evacuation",
    "temporary shelter",
    "flood-safe location",
    "vulnerable groups",
    "transport access",
    "relief camp sanitation",
    "route accessibility",
]
TOP_K = 5
LATENCY_REPETITIONS = 5


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def result_record(result) -> dict:
    return {
        "rank": result.rank,
        "chunk_id": result.chunk_id,
        "source_id": result.source_id,
        "filename": result.filename,
        "page": result.page,
        "retrieval_method": result.retrieval_method,
        "dense_score": result.dense_score,
        "dense_rank": result.dense_rank,
        "bm25_score": result.bm25_score,
        "bm25_rank": result.bm25_rank,
        "fusion_score": result.fusion_score,
        "fusion_rank": result.fusion_rank,
    }


def signature(results) -> list[tuple]:
    return [
        (
            item.chunk_id,
            item.rank,
            item.dense_rank,
            item.bm25_rank,
            item.fusion_rank,
            item.dense_score,
            item.bm25_score,
            item.fusion_score,
        )
        for item in results
    ]


def main() -> int:
    version, fingerprint = frozen_corpus_identity()
    clear_retriever_cache()

    startup_started = time.perf_counter()
    dense = get_retriever(RetrievalMethod.DENSE)
    dense_factory_ms = (time.perf_counter() - startup_started) * 1000

    startup_started = time.perf_counter()
    bm25 = get_retriever(RetrievalMethod.BM25)
    bm25_build_ms = (time.perf_counter() - startup_started) * 1000

    hybrid = get_retriever(RetrievalMethod.HYBRID_RRF)
    retrievers = {"dense": dense, "bm25": bm25, "hybrid": hybrid}

    # Warm all lazy state. Dense model load and Chroma open are deliberately excluded.
    warm_started = time.perf_counter()
    for retriever in retrievers.values():
        retriever.retrieve(QUERIES[0], TOP_K)
    warmup_ms = (time.perf_counter() - warm_started) * 1000

    smoke: list[dict] = []
    determinism: dict[str, bool] = {name: True for name in retrievers}
    observed_sources: dict[str, set[str]] = {name: set() for name in retrievers}

    for query in QUERIES:
        query_record = {"query": query, "results": {}}
        print(f"\nQUERY: {query}")
        for name, retriever in retrievers.items():
            first = retriever.retrieve(query, TOP_K)
            second = retriever.retrieve(query, TOP_K)
            determinism[name] &= signature(first) == signature(second)
            observed_sources[name].update(item.source_id for item in first)
            query_record["results"][name] = [result_record(item) for item in first]
            print(f"  {name.upper()}")
            for item in first:
                print(
                    f"    {item.rank}. {item.chunk_id} | {item.source_id} | "
                    f"{item.filename} p.{item.page} | dense={item.dense_score} "
                    f"bm25={item.bm25_score} rrf={item.fusion_score}"
                )
        smoke.append(query_record)

    latency: dict[str, dict[str, float | int]] = {}
    for name, retriever in retrievers.items():
        samples: list[float] = []
        for _ in range(LATENCY_REPETITIONS):
            for query in QUERIES:
                started = time.perf_counter()
                retriever.retrieve(query, TOP_K)
                samples.append((time.perf_counter() - started) * 1000)
        latency[name] = {
            "samples": len(samples),
            "median_ms": statistics.median(samples),
            "p90_ms": percentile(samples, 0.90),
            "p95_ms": percentile(samples, 0.95),
        }

    if not all(determinism.values()):
        raise RuntimeError(f"deterministic replay failed: {determinism}")

    artifact = {
        "artifact_type": "phase12_engineering_retrieval_sanity",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "retrieval_spec_version": RETRIEVAL_CONFIG_VERSION,
        "corpus_version": version,
        "corpus_fingerprint": fingerprint,
        "chunk_count": EXPECTED_CHUNK_COUNT,
        "dense": {
            "method_id": DENSE_METHOD_ID,
            "model": EMBED_MODEL_NAME,
            "dimension": EMBEDDING_DIMENSION,
            "score_type": DENSE_SCORE_TYPE,
            "score_order": "lower_is_better",
        },
        "bm25": {
            "method_id": BM25_METHOD_ID,
            "implementation": "local explicit Okapi BM25",
            "k1": BM25_K1,
            "b": BM25_B,
            "epsilon": BM25_EPSILON,
            "tokenizer_version": TOKENIZER_VERSION,
        },
        "hybrid": {
            "method_id": HYBRID_METHOD_ID,
            "fusion": "reciprocal_rank_fusion",
            "rrf_k": RRF_K,
            "candidate_k": HYBRID_CANDIDATE_K,
            "candidate_rule": "max(candidate_k, requested_k) per component",
        },
        "startup": {
            "dense_factory_ms_excludes_lazy_model_and_store_load": dense_factory_ms,
            "bm25_index_build_ms": bm25_build_ms,
            "all_retriever_warmup_ms": warmup_ms,
        },
        "smoke_queries": smoke,
        "distinct_source_ids_observed": {
            name: sorted(source_ids) for name, source_ids in observed_sources.items()
        },
        "latency": latency,
        "latency_scope": (
            "warmed query calls; excludes one-time model load, Chroma open, and BM25 build"
        ),
        "determinism": determinism,
        "offline": True,
        "quality_claim": (
            "engineering smoke only; no accuracy metric or method-superiority claim"
        ),
        "reranker": "not implemented; deferred",
        "gemini_invoked": False,
        "phase10_rl_result_changed": False,
    }
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"\nWrote {OUTPUT_PATH}")
    for name, values in latency.items():
        print(
            f"{name}: median={values['median_ms']:.3f} ms, "
            f"p90={values['p90_ms']:.3f} ms, p95={values['p95_ms']:.3f} ms"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
