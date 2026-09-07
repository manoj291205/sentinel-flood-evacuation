# Sentinel-Agent V3 — Frozen Retrieval Specification

## Status and scientific boundary

This document freezes `v3-retrieval-v1` before the Phase 13 relevance benchmark. It
defines three engineering-complete retrieval alternatives over exactly the frozen Phase
11 corpus. It contains no human relevance labels and makes no retrieval-accuracy claim.

> Phase 12 introduces retrieval alternatives but does not establish that BM25 or hybrid
> retrieval is superior to dense retrieval. Retrieval quality will be evaluated only
> after Phase 13 creates a human-reviewed relevance benchmark.

Any parameter change after Phase 13 labels or results are seen requires a formal
specification amendment and a complete benchmark rerun. Phase 12 does not change the
corpus, chunks, Gemini prompt, constraint cache, or the frozen Phase 10 RL result (`NO`).

## Frozen identity and configuration

| Field | Frozen value |
| --- | --- |
| Retrieval config | `v3-retrieval-v1` |
| Corpus version | `v3-authoritative-corpus-v1` |
| Corpus fingerprint | `a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753` |
| Canonical chunks | 1,797 |
| Dense method ID | `dense-minilm-v1` |
| BM25 method ID | `bm25-okapi-v1` |
| Hybrid method ID | `hybrid-rrf-v1` |
| Tokenizer | `nfkc-casefold-alphanumeric-v1` |
| BM25 `k1` | 1.5 |
| BM25 `b` | 0.75 |
| BM25 `epsilon` | 0.25 |
| RRF constant | 60 |
| Hybrid candidate rule | `max(20, requested_k)` from each component |

The manifest fingerprint is recomputed from its canonical source records before use.
The persisted Chroma collection must claim the same corpus version and fingerprint and
must contain exactly 1,797 chunks. A mismatch is an error, never a warning or fallback.
BM25 rebuilds from the same verified local `PreparedCorpus` at process start and checks
the exact chunk count and uniqueness.

## Common result and interface

Each retriever implements:

```python
retrieve(query: str, k: int) -> list[RetrievedChunk]
```

`RetrievedChunk` carries stable `chunk_id`, `source_id`, `source_document` (also exposed
as `filename`), 1-based PDF `page`, original chunk `text`, `retrieval_method`, output
`rank`, component scores/ranks where applicable, corpus version, and corpus fingerprint.
The historical `score`, `source_document`, and `citation()` API remains compatible with
the Gemini and demo code. All fusion joins use `chunk_id`; text, rank position, filename,
and page are never used as identity. If two methods return different text/source/page for
one ID, fusion fails.

Requests reject an empty/whitespace query and any `k` that is not an integer at least
one. Requests larger than the available result set return only available chunks. No
method returns one chunk ID twice, and no source-diversity quota is imposed.

## Dense baseline

Dense retrieval finds chunks whose vector embeddings are semantically close to a raw
query even when wording differs. The baseline remains the local `all-MiniLM-L6-v2`
model, 384 dimensions, and the existing cosine-space Chroma index. Chunking, stored
text, query preprocessing, model, and metric are unchanged.

Chroma returns cosine **distance**, not similarity. `dense_score` therefore means
`cosine_distance`, and lower is better. Results sort by ascending distance, then
ascending stable chunk ID for exact ties. The dense query is passed raw to MiniLM; it is
not replaced with BM25 tokens.

## Lexical BM25

BM25 is a lexical ranking algorithm that rewards query terms found in a chunk while
accounting for term rarity and chunk length. `bm25-okapi-v1` is a small local,
transparent Okapi implementation using explicit `k1=1.5`, `b=0.75`, and
`epsilon=0.25`. The epsilon rule floors negative Robertson/Sparck-Jones IDF values at
`epsilon × mean corpus IDF`, matching the intended explicit Okapi behavior without a
runtime package or service.

The same tokenizer processes a normalized copy of both corpus text and query:

1. Unicode NFKC normalization;
2. `casefold()`;
3. regex `[^\W_]+` under Unicode semantics (alphanumeric word runs, excluding
   underscore);
4. no stopword removal, stemming, or lemmatization.

For example, `Flood-Safe Shelter Capacity` becomes `flood`, `safe`, `shelter`,
`capacity`. Returned citation text is never normalized. Canonical index order is source
ID, PDF page, within-page chunk index, then chunk ID. BM25 sorts by decreasing score and
then ascending chunk ID. If no normalized query token occurs in the corpus vocabulary,
it returns `[]`, never arbitrary zero-score chunks.

## Hybrid reciprocal-rank fusion

Hybrid retrieval uses more than one retrieval strategy. Reciprocal Rank Fusion combines
rank positions rather than comparing incompatible dense-distance and BM25-score scales.
For each stable chunk ID:

```text
RRF_score(chunk) = Σ_system 1 / (60 + rank_system(chunk))
```

Ranks are 1-based. For `retrieve(query, k)`, dense and BM25 each supply
`max(20, k)` candidates. Their union is deduplicated by chunk ID. A missing component
contributes zero; therefore BM25 no-overlap still produces a dense-based hybrid list.
Dense backend errors propagate and are not disguised as lexical fallback. Results sort
by decreasing RRF score, then ascending chunk ID, and receive `fusion_rank=1..N`.
Hybrid results expose every available dense/BM25 rank and raw score plus fusion score and
rank.

## Determinism, citations, and offline behavior

With the same local corpus, query, `k`, and configuration, all ranked ID sequences are
deterministic. SHA-256—not Python's process-randomized `hash()`—protects corpus identity.
BM25 index construction, all retrieval calls, fusion, tests, and the sanity script use
only committed PDFs/local derived text. Dense model loading uses
`local_files_only=True`; normal queries cannot download a model, PDF, or other resource.

All methods return identical original text, source ID, filename, and PDF page for the
same chunk. The additive method metadata does not change existing verbatim citation
verification. No Gemini call, prompt change, or constraint-cache regeneration is part of
Phase 12.

## Engineering characterization only

The Phase 12 sanity script uses seven fixed smoke queries and reports top-five provenance,
component scores/ranks, deterministic replay, and warmed median/p90/p95 latency. Model
load and BM25 construction are excluded from per-query latency and may be reported as
startup costs. No Hit@k, Recall, MRR, nDCG, official relevance judgment, or method
superiority claim is permitted before Phase 13's human-reviewed benchmark.

No cross-encoder reranker is included. The small three-document, single-publisher corpus,
simple tokenizer, unchanged V1-era dense model, and design choice `RRF_K=60` remain known
limitations. Source authority does not prove passage relevance; passage relevance does
not prove a generated claim is entailed. Phase 13 addresses the former and Phase 14 the
latter.
