# Sentinel-Agent V3 — AI-Assisted Retrieval Benchmark Amendment

## Status and reason for amendment

The original frozen Phase 13 benchmark specification requires 45 accepted questions
plus human passage-level relevance judgments. Phase 13A.1 completed question selection,
but the project owner elected not to manually annotate all 485 retained passage rows.
Passage-level human annotation therefore remains incomplete, and the originally planned
human-gold benchmark cannot honestly be completed from the current evidence.

This amendment creates a separate **AI-assisted relevance benchmark** for controlled
comparative analysis. It does not have the same evidentiary strength as independently
human-annotated relevance judgments. The original human-gold design remains visible and
unfinished as a possible future validation exercise. No AI label is stored in a human
field or described as human verified, human annotated, expert annotated, or human gold.

## Versions and frozen inputs

- AI-assisted benchmark: `v3-retrieval-benchmark-ai-assisted-v1`
- label protocol: `v3-ai-relevance-labeler-v1`
- unchanged candidate set: `v3-retrieval-benchmark-candidate-v1`
- corpus: `v3-authoritative-corpus-v1`
- corpus fingerprint:
  `a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`
- retrieval configuration: `v3-retrieval-v1`
- parent commit: `231e1467eacade54bbc5017fbd240f0196d3e174`

`v3-retrieval-benchmark-gold-v1` is not created. The exact 45 Phase 13A.1 questions and
485 retained passage rows are fixed before labeling. No question is removed or replaced
because it is difficult to label, and effective question wording is unchanged.

## Blind labeling payload

The primary and consistency-pass labelers receive one question–passage pair at a time
with only these fields:

1. `question_id`
2. `effective_question`
3. `topic`
4. `query_style`
5. `chunk_id`
6. `source_id`
7. `filename`
8. `page`
9. `original_text`

They do not receive Dense, BM25, or Hybrid identity, rank, or score; retrieval-method or
fusion metadata; the Phase 13A seed flag; or `machine_suggested_grade`. The sanitized
payload is materialized before labeling and the labeler reads that payload—not the
rank-bearing retained review CSV. Rows are ordered by the SHA-256 of
`question_id + NUL + chunk_id`, preventing the original seed-first pool order from acting
as an indirect hint. Prior suggestions are not defaults, hints, fallbacks, or tie
breakers.

## Frozen relevance decision protocol

The labeler applies this order independently to every pair:

1. If the passage itself contains information that directly answers the question or a
   material component of it, assign `2 — DIRECTLY RELEVANT`. A reasonable answer could
   cite it as substantive evidence.
2. Otherwise, if the passage contains specific useful context that would reasonably
   contribute to an answer but is insufficient to answer the core question, assign
   `1 — PARTIALLY RELEVANT`.
3. Otherwise assign `0 — NOT RELEVANT`.

Same-topic text alone is not sufficient for grade 1. The labeler does not infer facts
that are absent from the passage and does not assume a nearby PDF page supplies missing
information. Each label includes a concise text-specific rationale.

Confidence is independent of the grade:

- `HIGH`: explicit passage content makes the grade clear.
- `MEDIUM`: a relevant relationship exists, but the grade 1/2 boundary has some
  ambiguity.
- `LOW`: the relationship or extracted text is genuinely ambiguous.

## Storage and human-field firewall

AI judgments are written only to
`data/eval_v3/phase13/ai_assisted_passage_labels.csv` using fields prefixed with `ai_`.
The historical `human_grade` values remain blank and `human_review_status` remains
`PENDING` in both the original and retained review files. The primary AI label is the
authoritative label for the AI-assisted benchmark; a later consistency pass is
diagnostic and is never reconciled to improve retrieval results.

## Label-set fingerprint

The label fingerprint is independent of CSV row order. For every completed label row:

1. retain exactly the published label-artifact fields;
2. represent every value as its CSV string value;
3. serialize the object as UTF-8 JSON with keys sorted, no insignificant whitespace,
   and non-ASCII characters preserved;
4. sort serialized rows lexicographically by `(question_id, chunk_id)` before joining;
5. join records with `\n`, add one final `\n`, and compute SHA-256 over those bytes.

The resulting digest, grade/confidence counts, parent commit, timestamp, and frozen
identifiers are stored in `ai_assisted_label_manifest.json` before any Phase 13B metric
is calculated.

## Answerability and distribution safeguards

All 45 questions must have at least one grade-2 passage in the frozen pool. A failure
stops the work without promoting grade 1, deleting the question, or generating a
replacement. Grade totals and percentages are reported without optimizing their
distribution. More than 90% grade 2 or fewer than 45 grade-2 rows is flagged for
investigation rather than silently changed.

## AI labeling consistency audit

The unchanged seed-`131313` Phase 13A.1 subset supplies ten questions. Their 107 passage
pairs receive a second blind application of the same protocol without access to
first-pass labels. The first pass remains authoritative and the second is diagnostic.
The audit reports exact agreement, linear weighted Cohen's kappa for ordinal grades,
absolute grade differences, and grade-2/1 and grade-2/0 disagreement counts. This is an
**AI labeling consistency audit**, not inter-rater reliability.

## Metrics remain frozen and unrun

No actual `DirectHit@1`, `DirectHit@3`, `DirectHit@5`, `MRR@5`, `nDCG@5`, pooled
`Recall@5`, paired bootstrap interval, or `HYBRID_SUPPORTED` decision is calculated in
Phase 13A.2. The previously frozen Phase 13B metrics, principal Hybrid-versus-Dense
comparison, 10,000 question-level bootstrap resamples, seed `131313`, and claim rule are
unchanged. Dense, BM25, Hybrid, corpus, chunking, tokenizer, and candidate depth remain
unchanged; no reranker is added.

Phase 13A.2 stops after label creation and freezing. Phase 13B has not started.
