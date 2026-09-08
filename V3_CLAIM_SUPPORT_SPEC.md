# Sentinel-Agent V3 — Claim–Evidence Support Specification

## Phase boundary and identity

Phase 14A freezes the construction-labeled claim-support challenge and the future
evaluation protocol. It does **not** run a semantic verifier or calculate official
performance metrics.

- benchmark: `v3-claim-support-challenge-v1`
- construction protocol: `v3-claim-support-construction-v1`
- support protocol: `v3-claim-support-protocol-v1`
- source benchmark: `v3-retrieval-benchmark-ai-assisted-v2`
- source label fingerprint: `393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7`
- corpus: `v3-authoritative-corpus-v1`
- corpus fingerprint: `a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`

## Three separate concepts

### A. Source integrity

Does the source, chunk, filename, and physical PDF page exist, and do quoted supporting
spans occur verbatim in that authoritative chunk? This is deterministic provenance and
quote integrity. The compatible V1 baseline is formally named `quote-integrity-v1`; its
existing `check_grounding` behavior answers `SOURCE_VALID / QUOTE_EXISTS`, not semantic
support.

### B. Retrieval relevance

Is a passage relevant to an information need? Phase 13 measured this property using
passage grades. Relevance is not entailment.

### C. Claim support

Does the cited evidence establish the exact factual proposition in a generated claim?
A source can exist and a passage can be relevant while the full claim remains unsafe
because it changes scope, modality, certainty, actor, timing, quantity, or conditions.
These three concepts must never be collapsed into one `citation_valid` Boolean.

## Claim-support labels

- `SUPPORTED`: every material proposition is established. Paraphrasing is allowed, but
  the claim cannot materially strengthen modality, certainty, scope, actor
  responsibility, timing, numerical quantity, or conditions.
- `PARTIALLY_SUPPORTED`: a meaningful component is established, but at least one
  material component is not. Examples include supported A plus unsupported B, turning a
  recommendation into a mandate, or adding an actor, deadline, number, or population.
- `UNSUPPORTED`: the evidence does not materially establish the core factual claim.
  Same-topic wrong facts, wrong actors/actions/conditions/populations, reversed advice,
  unsupported quantities, and contradictions belong here. Contradiction is an
  `UNSUPPORTED` subtype.

Safe-to-cite mapping is frozen as:

| Verdict | Complete original claim safe to cite? |
| --- | --- |
| `SUPPORTED` | `SAFE_TO_CITE` |
| `PARTIALLY_SUPPORTED` | `NOT_SAFE_TO_CITE` |
| `UNSUPPORTED` | `NOT_SAFE_TO_CITE` |

Phase 14A does not rewrite, narrow, or retrieve again for an unsafe claim.

## Construction-labeled challenge

This is a **construction-labeled claim-support challenge set**, not human gold, expert
annotated, or independently human reviewed. AI assistance was used to construct the
claims and reasons under the controlled protocol. Labels follow directly from the
controlled construction, and this provenance limits conclusions from future results.

For each of all 45 frozen Phase 13 questions, the builder collects every grade-2 chunk,
sorts stable `chunk_id` values ascending, and selects the first. Selection never uses a
retriever, rank, retrieval score, or Phase 13 system performance. This produces 45
question-level evidence selections (31 unique underlying chunks because some questions
share direct evidence). Source ID, filename, physical page, corpus identity, and exact
UTF-8 passage SHA-256 are checked against the frozen local corpus.

Each question has exactly three claims over the same evidence chunk: one `SUPPORTED`,
one `PARTIALLY_SUPPORTED`, and one `UNSUPPORTED`, for 135 pairs balanced 45/45/45.
Supported examples are concise paraphrases. Partial examples add one realistic material
overstatement where practical. Unsupported examples retain topical plausibility while
changing or reversing the core proposition.

The controlled reason vocabulary is exactly:

`SUPPORTED_PARAPHRASE`, `UNSUPPORTED_ADDITION`, `MODALITY_OVERSTATEMENT`,
`SCOPE_OVERSTATEMENT`, `ACTOR_MISMATCH`, `TIMING_ADDITION`, `NUMERIC_ADDITION`,
`CONDITION_ADDITION`, `CONTRADICTION`, `SAME_TOPIC_WRONG_CLAIM`,
`POPULATION_MISMATCH`, `OTHER`.

All rows set `synthetic_variant=true` and `not_authoritative_policy=true`. For supported
rows this means the wording is a generated benchmark paraphrase, not a verbatim policy
statement. For partial/unsupported rows it additionally warns that the content includes
deliberately ungrounded challenge material. Negative claims must never be presented as
NDMA guidance.

The machine-readable challenge stores provenance and a passage hash, not authoritative
passage text. The audit document contains only short excerpts reconstructed locally.

## Deterministic fingerprint

The fingerprint uses the fields published in `claim_support_manifest.json` in that exact
order. Records sort by `claim_pair_id` ascending. Each is encoded as one compact UTF-8
JSON array (`ensure_ascii=false`, separators `,` and `:`), records are separated by LF,
one final LF is added, and SHA-256 is calculated over those bytes. A claim or canonical
field change therefore changes the digest, while JSON presentation formatting does not.

## Two-layer verifier architecture

The future interface is:

```python
verify_claim_support(claim: str, evidence: EvidenceChunk) -> ClaimSupportResult
```

`ClaimSupportResult` contains one of the three verdicts, confidence in `[0,1]`,
supporting spans, a short reason, `source_integrity_pass`, and the support protocol
version.

Layer 1 is deterministic source integrity. It verifies chunk/source/filename/page/hash
and then requires every returned supporting span to occur verbatim inside the local
authoritative chunk. Layer 2 is semantic claim support. It judges the exact claim but
cannot override a failed integrity layer. `SUPPORTED` and `PARTIALLY_SUPPORTED` require
one or more supporting spans; an invented span is an integrity failure.

Phase 14B should use the existing Gemini provider at temperature zero or its lowest
deterministic supported setting, strict structured output, and no hidden chain-of-thought.
Its payload may contain only the claim, authoritative evidence, and source provenance.
It may not contain labels, construction reasons/subtypes, synthetic indicators, Phase 13
grades, retriever identity/rank, question class metadata, or the expected verdict.
Gemini is not invoked over this benchmark in Phase 14A.

## Frozen Phase 14B evaluation

Evaluation order is label-independent: ascending
`SHA-256(claim_pair_id + challenge_fingerprint)`, then `claim_pair_id`. Class blocks are
forbidden.

Primary metric: three-class Macro-F1 over `SUPPORTED`, `PARTIALLY_SUPPORTED`, and
`UNSUPPORTED`.

Secondary metrics: overall accuracy; per-class precision, recall, and F1; confusion
matrix; `SUPPORTED` precision; safe-to-cite precision and recall; unsafe citation
acceptance rate; and supporting-span/source-integrity validation failure rate. Cosine
similarity is not entailment and is not a baseline.

Binary safe-to-cite treats only `SUPPORTED` as positive. Unsafe citation acceptance is:

```text
(PARTIALLY_SUPPORTED or UNSUPPORTED examples predicted SUPPORTED) / 90
```

The future result is `CLAIM_SUPPORT_VERIFIER_USEFUL` only if **all** hold:

1. three-class Macro-F1 >= 0.75;
2. `SUPPORTED` precision >= 0.85;
3. unsafe citation acceptance rate <= 0.15;
4. source-integrity/supporting-span validation failure rate <= 0.05.

Otherwise it is `CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE`. These are project engineering
thresholds, not universal scientific standards, and cannot be changed after evaluation.

## Limits and frozen prior results

The evidence is authoritative, but claims and labels are construction-derived with AI
assistance. The corpus has three documents from one publisher, the challenge is small,
and controlled negatives may be easier or stylistically different from organic model
errors. No independent semantic annotation exercise has occurred.

Phase 10 remains `RL usefulness = NO`. Phase 13 remains `HYBRID_SUPPORTED` against the
frozen Dense baseline, while BM25 has the highest DirectHit@5. No corpus, retrieval
configuration, relevance label, question wording, PPO model, or prior result changes in
Phase 14A.

> **NO OFFICIAL CLAIM-SUPPORT VERIFIER PERFORMANCE RESULT WAS CALCULATED IN PHASE 14A.**
