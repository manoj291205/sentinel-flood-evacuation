# V4_CLAIM_SUPPORT_14D_SPEC — Phase 14D: claim-support evaluation for T2 (replaces 14C)

Lane X (provider, runner, scorer) and Opus (challenge sets, prompt freeze, audits) · branch
`lane-x/m14d-claim-support` · acceptance tests `tests/test_p14d_claim_support.py`.
Written and approved by Opus with the user on 2026-10-16, **before any 14D request to the provider and before
any 14D challenge claim exists**. The acceptance tests pin this file by SHA-256: any edit after this commit
requires a new evaluation ID and a new pre-registration (§9).

## 1. Why 14D exists, and what it replaces
Phase 14C (`v3-claim-support-eval-14c-v1`, 135/135, audited 2026-10-16) **failed** its pre-registered gate:
`CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE`. Macro-F1 was 0.585 (needs ≥ 0.75) because the model labelled 42 of
45 `PARTIALLY_SUPPORTED` claims `UNSUPPORTED`, and the span-integrity failure rate was 0.104 (needs ≤ 0.05)
because 14 answers quoted spans that are not verbatim in the evidence. SUPPORTED precision (0.978) and unsafe
citation acceptance (0.011) passed. These facts stay on the record exactly as scored.

**14D replaces 14C as the claim-support evaluation of record**, as 14C replaced 14B. It is not an addition:
from this commit only a 14D verdict can ever enable Phase 15′ T2, and 14C is reported everywhere (STATUS,
Evidence & Results, course pack, patent drafts) as "14C — failed (reasons above), superseded by 14D". 14C's
code, spec, ledger, calls log and score stay on `main` unchanged as history and are never rerun, rescored,
merged with or relabelled as 14D. 14D is reported alongside 14C, never instead of it.

Three things change, each aimed at a measured 14C failure, and nothing else:
1. **Citations by sentence number** (fixes invented quotes): the evidence is sent as numbered sentences and the
   model returns sentence numbers; the provider turns them into the exact sentence text, so a cited span is
   verbatim by construction. The deterministic integrity layer still runs unchanged.
2. **Clearer partial-vs-unsupported instructions and `reasoning_effort = "medium"`** (targets the partial
   confusion): a new prompt (§4) with an explicit decision rule and one invented worked example.
3. **A pass test that measures what T2 uses** (§6): T2 acts only on a `SUPPORTED` answer with a verified
   citation, so the deciding gate is about exactly that. The frozen V3 gate is still computed and reported
   as a secondary verdict, so the partial-vs-unsupported result is never hidden.

And the test claims are **new** (§3): a fresh 135-pair test set built on evidence chunks the 14C/V3 challenge
never used, plus a separate 30-pair practice set for at most two prompt-tuning rounds (§5). The test set is
seen by the model exactly once.

## 2. Identity (frozen)
| Field | Value |
|---|---|
| Evaluation ID | `v4-claim-support-eval-14d-v1` |
| Provider ID | `groq-claim-support-14d-v1` (Groq Cloud, OpenAI-compatible Chat Completions, Free Plan) |
| Model ID | `openai/gpt-oss-120b` (same model as 14C; no fallback, alias or substitution) |
| Endpoint | `POST https://api.groq.com/openai/v1/chat/completions` (synchronous; never `/batches` or `/files`) |
| Request settings | `{"temperature": 0.0, "seed": 14, "reasoning_effort": "medium", "include_reasoning": false, "max_completion_tokens": 4096}` |
| Prompt versions | `14d-prompt-r0` (§4, fixed now); `14d-prompt-r1` (optional, practice round 2 only) |
| Challenge ID | `v4-claim-support-challenge-14d-v1` (test 135 pairs, practice 30 pairs; §3) |
| Key | `GROQ_API_KEY` from the process environment only |
| Output folder | `data/eval_results/phase14d/` (`practice/round1/`, `practice/round2/`, `test/`) |

Unchanged from 14C and inherited by reference to `V4_CLAIM_SUPPORT_14C_SPEC.md`: temperature note
(`"provider converts 0 to 1e-8"`), single first pass (a written pair is never re-requested), strict JSON
schema, no system message, no `user`/`metadata`/`store`/`stream`/`tools`/`n`/`top_p`/`service_tier` field,
reasoning text never requested, returned, stored or logged (`include_reasoning = false`; any `reasoning`
field is discarded), Free Plan only, ZDR required, confidentiality check (§3.3 of 14C; the 14D payload is
the same class: a synthetic claim, public NDMA text and its provenance), and the error table of 14C §3.4 as
fixed at the 14C re-audit: any 5xx → `PROVIDER_UNAVAILABLE`; 401/403 → `AUTH_ERROR`; 429 with
`retry-after` ≤ 60 s → wait and retry, at most 2 waits per pair, else `RATE_LIMITED`; timeout/connection →
`NETWORK_ERROR`; every other non-200 except a 400 `json_validate_failed` → `REQUEST_REJECTED`. A stop
writes no disposition.

## 3. Challenge sets (built by Opus before any 14D call)
Built by `scripts/phase14d_prepare_challenge.py` (Opus) into `data/eval_v4/phase14d/`:
`challenge_test.json`, `challenge_practice.json`, `manifest.json`, `selection_log.json`. Construction follows
`V3_CLAIM_SUPPORT_SPEC.md` (labels, safe-to-cite mapping, reason vocabulary, `synthetic_variant = true`,
`not_authoritative_policy = true`, fingerprint procedure) with these differences:

**Chunk selection (deterministic, logged).** Corpus `v3-authoritative-corpus-v1` via `prepare_corpus()`.
Exclude (a) every chunk whose `(source_id, page)` holds any of the 31 V3 challenge chunks, and (b) chunks
shorter than 400 characters. Walk the rest in ascending `SHA-256("14d-v1:" + chunk_id)` order. A chunk is
accepted unless it is `NON_SUBSTANTIVE` (contents, headings, index, glossary, references, acknowledgements,
name or address lists, figure/table residue — no checkable guidance or factual statement), `GARBLED_TEXT`
(extraction too broken to read), or `NEAR_DUPLICATE` (≥ 80 % of its word set overlaps an accepted chunk).
Every walked chunk is written, in walk order, to `selection_log.json` = `{"walked": [{"chunk_id", "decision"
(`ACCEPTED_TEST`|`ACCEPTED_PRACTICE`|`SKIPPED`), "reason" (the skip code, or null)}]}`; the walk stops at the
55th accepted chunk. The first 45 accepted
chunks form the test set, the next 10 the practice set.

**Claims.** Three per chunk — one `SUPPORTED` (`SUPPORTED_PARAPHRASE`), one `PARTIALLY_SUPPORTED`, one
`UNSUPPORTED` — written by Opus under the V3 construction rules (supported = concise paraphrase; partial =
supported core plus one realistic material overstatement; unsupported = topically plausible but the core
proposition is changed or reversed). Construction labels follow from construction; this is **not** human
gold and the provenance limits conclusions (disclosed with every result). The subtype mix is fixed now and
copies the V3 challenge so 14D is not easier by design:

| Set | `PARTIALLY_SUPPORTED` subtypes | `UNSUPPORTED` subtypes |
|---|---|---|
| test (45 chunks) | SCOPE_OVERSTATEMENT 10, TIMING_ADDITION 8, NUMERIC_ADDITION 7, ACTOR_MISMATCH 7, MODALITY_OVERSTATEMENT 5, POPULATION_MISMATCH 4, UNSUPPORTED_ADDITION 3, CONDITION_ADDITION 1 | CONTRADICTION 40, SAME_TOPIC_WRONG_CLAIM 5 |
| practice (10 chunks) | SCOPE_OVERSTATEMENT 2, TIMING_ADDITION 2, NUMERIC_ADDITION 2, ACTOR_MISMATCH 2, MODALITY_OVERSTATEMENT 1, POPULATION_MISMATCH 1 | CONTRADICTION 9, SAME_TOPIC_WRONG_CLAIM 1 |

Claims are unique across both sets. No Groq call, no 14C/14D model output and no automatic generator is used
to write or check claims.

**Row schema** (both files): `claim_pair_id` (`T<nn>-C<k>` test, `P<nn>-C<k>` practice; `nn` = 01.. in
acceptance order, `k` = 1 supported, 2 partial, 3 unsupported), `challenge_set` (`test`|`practice`),
`chunk_id`, `source_id`, `filename`, `page`, `passage_sha256`, `claim`, `construction_label`,
`construction_reason`, `reason_subtype`, `synthetic_variant`, `not_authoritative_policy`,
`benchmark_version` (= challenge ID), `construction_protocol_version` (`v4-claim-support-construction-14d-v1`).

**Manifest** `manifest.json`: `challenge_id`, `corpus_version`, `corpus_fingerprint`, `selection_rule`
(the text above), `canonical_fields_in_order` (the row schema order; rows store keys in this order), `sets` = `{"test": {...}, "practice": {...}}`
with `{claim_pairs, label_counts, reason_subtype_counts, chunk_ids, challenge_fingerprint}` each, and
`excluded_v3_pages` (list of `[source_id, page]`).
Fingerprint per set = SHA-256 over compact UTF-8 JSON arrays of the canonical fields, rows sorted by
`claim_pair_id`, LF-separated with a final LF (the V3 procedure).

**Freeze.** The challenge commit lands on `main` before Lane X's code is merged; Opus records both set
fingerprints in `STATUS.md` → Decision log. From then on `data/eval_v4/phase14d/**` is frozen.

## 4. Provider protocol
### 4.1 Sentences, payload, prompt, request
```python
_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SPLIT.split(text) if part.strip()]
```
Every element is a contiguous substring of the chunk text (verbatim). Sentence IDs are 1-based.
```python
def build_payload(claim, evidence) -> dict:      # derived from claim_support.build_verifier_payload
    base = build_verifier_payload(claim, evidence)
    return {"claim": base["claim"],
            "evidence_sentences": [{"id": i, "text": s} for i, s in enumerate(split_sentences(evidence.text), 1)],
            "source_provenance": base["source_provenance"]}
def build_prompt(payload, prompt_version) -> str:  # load_prompt(prompt_version) + json.dumps(payload, ensure_ascii=False)
RESPONSE_SCHEMA = {"type": "object", "additionalProperties": False,
  "properties": {"verdict": {"type": "string", "enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]},
                 "confidence": {"type": "number"},
                 "supporting_sentence_ids": {"type": "array", "items": {"type": "integer"}},
                 "reason": {"type": "string"}},
  "required": ["verdict", "confidence", "supporting_sentence_ids", "reason"]}
body = {"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "claim_support_verdict_14d", "strict": True, "schema": RESPONSE_SCHEMA}},
        **REQUEST_SETTINGS}
```
Prompts live in `src/constraints/p14d_prompts/<prompt_version>.txt` (UTF-8, LF). `14d-prompt-r0.txt` is
**exactly** the text between the markers below (the line after `BEGIN` to the line before `END`, with one
final LF); the acceptance tests compare it byte for byte.

<!-- BEGIN 14d-prompt-r0 -->
Decide whether the numbered evidence sentences support the exact claim.
SUPPORTED: every material part of the claim is established by the evidence. Paraphrase is fine, but the claim must not be stronger than the evidence in modality (for example "should" turned into "must"), certainty, scope, actor, timing, numbers or conditions.
PARTIALLY_SUPPORTED: at least one meaningful part of the claim is established by the evidence, and at least one material part is not. Typical cases: a supported statement plus an added number, deadline, actor, population or condition; a recommendation turned into a mandate; a claim made broader or more universal than the evidence.
UNSUPPORTED: the central statement of the claim is not established. It states a different fact, reverses or contradicts the evidence, or names the wrong actor, action, condition or population for its main point.
Decision rule: first identify which parts of the claim the evidence establishes. If a meaningful part is established and something material is added or strengthened, answer PARTIALLY_SUPPORTED, not UNSUPPORTED. Answer UNSUPPORTED only when the central statement itself is absent or wrong.
Invented example, not from the evidence below: evidence "Warning messages should be issued in the local language." Claim "Warning messages should be issued in the local language at least three times a day." is PARTIALLY_SUPPORTED. Claim "Warning messages should be issued only in English." is UNSUPPORTED.
Cite evidence by sentence number: put in supporting_sentence_ids the numbers of the sentences that establish the supported part. Give at least one number for SUPPORTED or PARTIALLY_SUPPORTED; the list may be empty for UNSUPPORTED. Use only numbers that appear in the evidence. Give a one-sentence reason. Return only the JSON object.
Input:
<!-- END 14d-prompt-r0 -->

### 4.2 Parsing and the deterministic layer
`content = body["choices"][0]["message"]["content"]`; any `reasoning` field is ignored. A response is valid
only if it is a JSON object with exactly the four fields; `verdict` in the enum; `confidence` a number (not a
bool) in [0, 1]; `supporting_sentence_ids` a list of ints (not bools), each in `1..len(sentences)`, no
duplicates; `reason` a string. Invalid output, `finish_reason = "length"`, or a 400 `json_validate_failed` →
one retry (counted), then `UNSUPPORTED`, reason `PROVIDER_PARSE_FAILURE`, `source_integrity_pass = false`,
no sentence IDs (a real, counted disposition). For a valid response, `supporting_spans` = the sentences for
the returned IDs in the returned order, then `finalize_semantic_result` (unchanged: chunk integrity, and for
SUPPORTED/PARTIALLY_SUPPORTED at least one verbatim span). A SUPPORTED/PARTIALLY_SUPPORTED answer with no IDs
therefore fails integrity, as in 14C.

### 4.3 Module interface (`src/constraints/claim_support_p14d.py`, Lane X)
```python
EVALUATION_ID = "v4-claim-support-eval-14d-v1"; PROVIDER_ID = "groq-claim-support-14d-v1"
MODEL_ID = "openai/gpt-oss-120b"; API_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_SETTINGS  # exactly §2
TEMPERATURE_NOTE = "provider converts 0 to 1e-8"
PROMPT_VERSIONS = ("14d-prompt-r0", "14d-prompt-r1")
PROMPT_DIR = <repo>/src/constraints/p14d_prompts
def load_prompt(prompt_version: str) -> str        # ValueError for a version not in PROMPT_VERSIONS or a missing file
def prompt_sha256(prompt_version: str) -> str      # SHA-256 of the prompt file bytes
def split_sentences(text: str) -> list[str]; def build_payload(claim, evidence) -> dict
def build_prompt(payload: dict, prompt_version: str) -> str; def build_request(prompt: str) -> dict  # fresh dict
RESPONSE_SCHEMA
# ProviderResponse, ProviderStop, Transport and http_transport: re-exported from claim_support_p14c (same
# endpoint, key handling and error mapping); the 14C module itself is not edited.
def verify_claim_support_p14d(claim: str, evidence: EvidenceChunk, *, prompt_version: str, transport: Transport,
                              sleep: Callable[[float], None] = time.sleep) -> P14dOutcome
@dataclass(frozen=True)
class P14dOutcome: result: ClaimSupportResult; supporting_sentence_ids: tuple[int, ...]
                   response_model: str | None; system_fingerprint: str | None; finish_reason: str | None
                   usage: Mapping[str, int]; attempts: int
```

## 5. Practice rounds and prompt freeze
- **Round 1** (required): practice set (30 pairs) with `14d-prompt-r0` → `practice/round1/`.
- **Round 2** (optional, at most one): Lane X may write `14d-prompt-r1.txt`, changing **wording only** —
  the four labels and their meaning, the JSON fields, the input format, model, settings, schema and gate are
  untouched — and run the practice set again → `practice/round2/`. No third round, no other prompt version.
- Practice results are scored with full metrics (`phase14d_score.py --set practice`, label "PRACTICE — not
  an evaluation result"). Lane X may read practice labels; test labels are joined only inside the test scorer.
- Lane X proposes the prompt to freeze (`r0` or `r1`) with a short reason in `STATUS_LANE_X.md`, pushes the
  practice logs and prompt files, and stops. Opus audits and writes `specs/approvals/p14d_prompt_freeze.json`:
  `{"evaluation_id", "prompt_version", "prompt_sha256", "practice_rounds": [{"round", "prompt_version",
  "score_sha256"}], "frozen_by_opus_utc"}`. Both practice rounds are reported with the final result.
- The test set runs only with the frozen prompt, once.

## 6. Pass test (primary, decides T2) and V3 gate (secondary, reported)
On the complete 135-pair **test** ledger, with `t2_positive(row) = verdict == "SUPPORTED" and
source_integrity_pass`:

| Metric | Definition | Pass |
|---|---|---|
| `t2_precision` | t2-positive rows labelled SUPPORTED / t2-positive rows (0 if none) | ≥ 0.95 |
| `t2_unsafe_acceptance` | t2-positive rows labelled PARTIALLY_SUPPORTED or UNSUPPORTED / 90 | ≤ 0.05 |
| `t2_recall` | t2-positive rows labelled SUPPORTED / 45 | ≥ 0.70 |
| `supported_integrity_failure` | rows with verdict SUPPORTED and `source_integrity_pass = false` / rows with verdict SUPPORTED (0 if none) | ≤ 0.02 |

All four pass → `t2_verdict = "T2_VERIFIER_USEFUL"`, otherwise `"T2_VERIFIER_NOT_YET_RELIABLE"`.
The frozen V3 gate (`classification_metrics`, `span_integrity_failure_rate`, `usefulness_gate`, thresholds of
`V3_CLAIM_SUPPORT_SPEC.md`) is computed on the same ledger and reported as `v3_verdict` with its conditions
and full metrics. Only `t2_verdict` decides T2; `v3_verdict` is always shown next to it. Thresholds are
project engineering choices fixed before any 14D call and cannot change afterwards.

## 7. Runner and scorer (Lane X)
### 7.1 Ledger rows (`dispositions.jsonl`, ordered prefix)
14C §4.2 fields plus `challenge_id`, `challenge_set`, `prompt_sha256`, `supporting_sentence_ids`:
`{evaluation_id, provider_id, model_id, prompt_version, prompt_sha256, temperature_requested,
temperature_note, request_settings, challenge_id, challenge_set, challenge_fingerprint, protocol_sha256,
zdr_attested, claim_pair_id, order_index, verdict, confidence, supporting_sentence_ids, supporting_spans,
reason, source_integrity_pass, response_model, system_fingerprint, finish_reason, usage, attempts,
request_utc, latency_ms}` — never the key, the prompt, the raw response, reasoning text or any construction
field. `protocol_sha256` = SHA-256 of this file. Order = `label_independent_order(pair_ids, set fingerprint)`.

### 7.2 Runner `scripts/phase14d_run_claim_support.py`
```python
@dataclass(frozen=True)
class Budget: requests_per_minute: int = 20; tokens_per_minute: int = 7000
              requests_per_day: int = 800; tokens_per_day: int = 185_000
EXPECTED_COMPLETION_TOKENS = 1500
def run(*, transport, challenge_set: str, out_dir: Path, max_requests: int, prompt_version: str,
        freeze_path: Path | None = None, budget_root: Path | None = None, budget: Budget = Budget(),
        zdr_attested: bool, clock=time.time, sleep=time.sleep) -> dict
    # -> {"done", "total" (135 test / 30 practice), "requests_made", "tokens_counted", "stopped_reason"}
```
- Same counting, `calls.jsonl` schema, pacing, header stop and stop reasons as 14C §4.3, except: estimate =
  `ceil(len(prompt.encode("utf-8")) / 3) + EXPECTED_COMPLETION_TOKENS`; **daily totals count every
  `calls.jsonl` under `budget_root`** (recursive; default `out_dir`), so practice and test runs on one UTC day
  share one budget. The CLI uses `budget_root = data/eval_results/phase14d`.
- `ValueError` before any call when: `zdr_attested` is false; `challenge_set` not `test`/`practice`;
  `prompt_version` unknown; `out_dir` resolves to or inside `data/eval_results/phase14b` or `.../phase14c`;
  `challenge_set == "test"` and `freeze_path` is missing, unreadable, or its `prompt_version`/`prompt_sha256`
  do not equal `prompt_version`/`prompt_sha256(prompt_version)`; an existing ledger differs in any identity
  field (evaluation, provider, model, prompt version/hash, request settings, challenge ID/set/fingerprint).
- `prepare_corpus()` at most once per process; chunks resolved with `get_chunk_by_id` and the row provenance.
- CLI: `--check-env`; `--dry-run` (fake transport, temp folder); `--preflight` (one `GET
  /openai/v1/models/openai/gpt-oss-120b`, no payload); `--live --attest-zdr --set practice --round {1,2}
  --prompt <version> [--max-requests N]` (round 2 refused unless round 1 is complete; round 3 does not exist);
  `--live --attest-zdr --set test [--max-requests N]` (prompt from `specs/approvals/p14d_prompt_freeze.json`).
  `--live` refuses unless `GROQ_API_KEY` is set and this spec, the challenge files, the prompt file used and
  (for test) the freeze file are tracked and unmodified in git. Prints `done/total`, the stop reason, calls made
  and the rerun command; never the key, prompt or responses.

### 7.3 Scorer `scripts/phase14d_score.py`
`score(ledger_path, out_path, calls_path=None, *, challenge_set="test") -> dict` and
`t2_gate(expected: Sequence[str], predicted: Sequence[str], integrity: Sequence[bool]) -> tuple[dict, str, dict]`
(metrics incl. `t2_positive_count`, `t2_verdict`, conditions keyed by the four §6 metric names). Refuses (`ValueError`) a
partial or unordered ledger, mixed identity fields, rows of another evaluation/provider, and any ledger or
output path under `phase14b/` or `phase14c/`. Writes: identity fields, `prompt_version`, `prompt_sha256`,
`temperature_requested`, `temperature_note`, `request_settings`, `challenge_id`, `challenge_set`,
`challenge_fingerprint`, `protocol_sha256`, `ledger_sha256`, `claim_pairs`, `verdict` (= `t2_verdict`),
`t2_verdict`, `t2_conditions`, `t2_metrics` (§6 four metrics + `t2_positive_count`), `v3_verdict`,
`v3_conditions`, `metrics` (full V3 metrics incl. `supported_precision`, `span_integrity_failure_rate`),
top-level `supported_precision` and `macro_f1`, `calls_total`, `system_fingerprints`, and `label` =
`"Phase 14D (replaces 14C as the claim-support evaluation of record)"` for test or
`"PRACTICE — not an evaluation result"` for practice.

## 8. T2 (Phase 15′) — the only route
14D counts toward T2 only if **all** hold: (a) 135/135 test dispositions under this protocol and
`protocol_sha256`, with the frozen prompt; (b) scored by `phase14d_score.py`; (c) `t2_verdict =
T2_VERIFIER_USEFUL`; (d) Opus audits challenge, practice logs, freeze record, ledger, calls and score and
records the decision; (e) the user explicitly approves the verdict for T2. Then Opus writes
`specs/approvals/t2_semantic_verifier.json` (fields per `V4_CONSTRAINT_TIERS_SPEC.md`, `verdict =
"T2_VERIFIER_USEFUL"`, plus `prompt_sha256`), and T2 may use only this exact configuration (model, frozen
prompt, settings, sentence-ID citation, ZDR). Otherwise T2 stays disabled. See the 15′ spec Amendment
2026-10-16.

## 9. Changes after approval
No edit to this protocol once committed. A different model, setting, threshold, schema or challenge is a new
evaluation ID with a new pre-registration committed before its first call. Every evaluation attempted is
reported (no silent reruns, no best-of selection). Rows already written are never rewritten.

## Acceptance (tests/test_p14d_claim_support.py, no network)
Protocol pinned by hash; identity and settings; `14d-prompt-r0` byte-identical to §4.1; sentence splitting
verbatim; payload shape with no label fields; exact request body and strict schema; sentence IDs → verbatim
spans; invalid IDs/fields, truncation and schema-400 → retry then parse failure; reasoning discarded; stop
statuses write nothing; runner ordered, resumable, counted, secret-free, budgets shared across practice and
test under one root; test set refused without a matching freeze record; `phase14b`/`phase14c` paths and mixed
ledgers refused; scorer applies the §6 gate and reports the V3 gate; challenge files (once built) have the
§3 counts, subtype mix, disjointness from V3 pages and between sets, verified provenance and fingerprints.

## Out of scope
Editing 14B/14C code, specs or results; reusing 14C claims; other models; paid plans; batch endpoints; live
calls in tests; wiring T2 into the gate (Lane S, Wave C, only after §8 is met).
