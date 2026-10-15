# V4_CLAIM_SUPPORT_14C_SPEC — Phase 14C: second-provider claim-support evaluation

Lane X · branch `lane-x/m14c-claim-support` · acceptance tests `tests/test_p14c_claim_support.py`
Protocol authority for the challenge, labels, order and thresholds: `V3_CLAIM_SUPPORT_SPEC.md` (frozen).
Written and approved by Opus on 2026-10-15, **before any request to the provider and before any 14C
result exists**. The acceptance tests pin this file by SHA-256: any edit after this commit requires a new
evaluation ID and a new pre-registration (see "Changes after approval").

## 1. Identity — a separate evaluation, never a Gemini result

| Field | Value (frozen) |
|---|---|
| Evaluation ID | `v3-claim-support-eval-14c-v1` |
| Provider ID | `groq-claim-support-v1` (Groq Cloud, OpenAI-compatible Chat Completions, Free Plan) |
| Model ID | `openai/gpt-oss-120b` (exact string; no fallback, alias or substitution) |
| Endpoint | `POST https://api.groq.com/openai/v1/chat/completions` (synchronous; never `/batches` or `/files`) |
| Prompt version | `14b-prompt-v1` — **byte-identical** prompt text to 14B (`claim_support_gemini.build_prompt`) |
| Key | `GROQ_API_KEY` from the process environment only |
| Output folder | `data/eval_results/phase14c/` (never `phase14b/`) |

Phase 14B (`gemini-claim-support-v1`, `gemini-3.6-flash`, `data/eval_results/phase14b/`) is unchanged: its
spec, code, history, escalation LX-P14B-1 and any ledger stay as they are and may keep running. The two
evaluations are reported side by side under their own IDs. A 14C number is never written to, merged into,
or labelled as a 14B/Gemini result, and the ledgers are never concatenated or cross-scored.

## 2. What stays frozen (unchanged from V3 / 14B)
- Challenge `data/eval_v3/phase14/claim_support_challenge.json` (135 pairs, 45/45/45), manifest and
  `challenge_fingerprint`; the runner recomputes the fingerprint and refuses on mismatch.
- Order: `label_independent_order(pair_ids, challenge_fingerprint)`; ledger is an ordered prefix.
- Payload: `build_verifier_payload(claim, evidence)` only (claim, authoritative evidence text, source
  provenance). Labels, construction reasons/subtypes, synthetic flags, grades, ranks or question metadata
  never reach the request.
- Deterministic layer: `finalize_semantic_result` (chunk integrity + verbatim spans) exactly as 14B; same
  parse validation as `verify_claim_support_gemini` (object, exactly the four fields, spans are strings,
  reason is a string, confidence in [0, 1] via `ClaimSupportResult`).
- Malformed output: one retry, then `UNSUPPORTED`, reason `PROVIDER_PARSE_FAILURE`,
  `source_integrity_pass = false` (a real, counted disposition — it is the model's output).
- Scoring: `classification_metrics`, `span_integrity_failure_rate`, `supported_precision`,
  `usefulness_gate` with the frozen thresholds (Macro-F1 ≥ 0.75, SUPPORTED precision ≥ 0.85, unsafe
  acceptance ≤ 0.15, span-integrity failure ≤ 0.05). Verdicts: `CLAIM_SUPPORT_VERIFIER_USEFUL` /
  `CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE`. Construction labels are joined **only** inside the scorer,
  which refuses partial ledgers. No interim metric, peek or partial score is ever computed.
- Frozen data is never edited.

## 3. What is new (the provider protocol), all fixed before any call

### 3.1 Request (exact body; nothing else is sent)
```python
REQUEST_SETTINGS = {"temperature": 0.0, "seed": 14, "reasoning_effort": "low",
                    "include_reasoning": False, "max_completion_tokens": 2048}
body = {"model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": build_prompt(payload)}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "claim_support_verdict", "strict": True, "schema": RESPONSE_SCHEMA}},
        **REQUEST_SETTINGS}
RESPONSE_SCHEMA = {"type": "object", "additionalProperties": False,
  "properties": {"verdict": {"type": "string", "enum": ["SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED"]},
                 "confidence": {"type": "number"},
                 "supporting_spans": {"type": "array", "items": {"type": "string"}},
                 "reason": {"type": "string"}},
  "required": ["verdict", "confidence", "supporting_spans", "reason"]}
```
Headers: `Authorization: Bearer <GROQ_API_KEY>`, `Content-Type: application/json`. No `user`, `metadata`,
`store`, `stream`, `tools`, `n`, `top_p` or `service_tier` field (provider defaults: `n = 1`, `top_p = 1`,
`service_tier = on_demand`, no streaming). No system message: the single user message is the 14B prompt.

### 3.2 Documented provider behaviour (verified from Groq docs on 2026-10-15)
- **Temperature 0:** Groq's OpenAI-compatibility notes state a `temperature` of 0 is converted to `1e-8`.
  Every row records `temperature_requested = 0.0` and `temperature_note = "provider converts 0 to 1e-8"`.
  This satisfies V3's "temperature zero or its lowest deterministic supported setting". `seed` is
  best-effort only; determinism is not guaranteed, so the official result is the **single first pass**:
  a written pair is never re-requested, and `system_fingerprint` is recorded per row (informational).
- **Reasoning model:** gpt-oss-120b always reasons; it cannot be switched off (`none` is not supported for
  this model). Protocol choice: `reasoning_effort = "low"` (fewest hidden tokens, within free-tier token
  limits) and `include_reasoning = false`, so no reasoning text is returned. If a `reasoning` field
  appears anyway it is discarded and never stored or logged. This is the 14C reading of V3's "no hidden
  chain-of-thought": none is requested, returned, stored or scored. It is a disclosed difference from 14B.
- **Strict structured output:** `json_schema` with `strict: true` is supported for `openai/gpt-oss-120b`
  (all properties required, `additionalProperties: false`). Strict mode guarantees shape, not truth; the
  same semantic and integrity checks still run. A `400` whose error code is `json_validate_failed` is a
  model output failure → treated exactly like malformed JSON (counts as a call; one retry; then
  `PROVIDER_PARSE_FAILURE`). `finish_reason = "length"` (truncated) is treated the same way.
- **Free Plan limits:** Groq's public table lists `openai/gpt-oss-120b` at 30 RPM, 1K RPD, 8K TPM,
  200K TPD (labelled as base limits; the exact per-organisation limits are on the console Limits page).
  Limits apply per organisation, not per key. The runner's defaults are set below those numbers (§4.3) and
  it also obeys the live `x-ratelimit-*` / `retry-after` headers.
- **Data controls:** Groq does not retain inference inputs/outputs by default except temporary logs (up to
  30 days) for reliability/abuse; **Zero Data Retention (ZDR)** removes those logs and is enabled by an
  org admin in Console → Settings → Data Controls ("all customers may enable"). The Services Agreement
  (§4.2) bars training on Inputs/Outputs, treats Customer Data as Confidential Information (§10) and leaves
  IP with the customer (§8.1). No batch, files or fine-tuning endpoint is used.
- **No paid billing:** the evaluation runs only on the Free Plan. Nothing in code, docs or prompts may
  upgrade the plan, add a payment method or switch model. A plan/limit error is a stop, not a workaround.

### 3.3 Confidentiality check (Opus, 2026-10-15) — PASS, conditional on ZDR
The project rule (CLAUDE.md) forbids publishing or showing the **dispatch-gate work** before P0 is filed.
The 14C request contains only: a construction-derived synthetic claim, the text of a public NDMA guideline
chunk, and its provenance (chunk id, source id, NDMA filename, page, passage hash). It contains no gate,
certifier, rollout, futures, constraint-tier, code or project-identifying content (no project name, no
`user`/`metadata` field). This is the same payload class already approved for 14B. Sending it to a
processor bound by confidentiality and no-training terms is compliant **provided ZDR is enabled**.
**Live-run precondition:** the user confirms in chat that ZDR is ON for the Groq organisation that owns the
key, Opus records that in `STATUS.md` → Decision log, and the runner is started with `--attest-zdr`. Without
all three, no live call is made.

### 3.4 Error handling (no disposition is ever invented)
| Response | Action | Disposition written? |
|---|---|---|
| 200, valid JSON object passing parse validation | `finalize_semantic_result` | yes |
| 200 malformed / wrong fields / confidence outside [0,1] / `finish_reason = length`; 400 `json_validate_failed` | one retry (counted), then `PROVIDER_PARSE_FAILURE` | yes (counted failure) |
| 429 with `retry-after` ≤ 60 s | wait `retry-after`, retry the same request; at most 2 waits per pair (each attempt counted) | only if a later attempt succeeds |
| 429 otherwise, or third 429 for the pair | stop `RATE_LIMITED` | no |
| any 5xx | stop `PROVIDER_UNAVAILABLE` | no |
| 401 / 403 | stop `AUTH_ERROR` | no |
| other 4xx (incl. 404 model not found, 413, 400 not `json_validate_failed`) | stop `REQUEST_REJECTED` | no |
| timeout / connection error | stop `NETWORK_ERROR` | no |
A stop discards the current pair unwritten; the next run resumes from the ordered prefix. No backoff loop
beyond the bounded 429 wait above. If `REQUEST_REJECTED` names the model as unavailable, or
`PROVIDER_UNAVAILABLE` persists 7 consecutive days, Lane X escalates (`LX-P14C-<n>.md`) — never substitutes.

## 4. Files and interfaces (all Lane X)
- `src/constraints/claim_support_p14c.py` (new) — provider.
- `scripts/phase14c_run_claim_support.py` (new) — resumable runner.
- `scripts/phase14c_score.py` (new) — scorer.
- `data/eval_results/phase14c/` (new; `dispositions.jsonl`, `calls.jsonl`, `score.json`; frozen once scored).
- `tests/test_lx_p14c_*.py` (Lane X unit tests). No new dependency: `httpx` is already installed.
- Do **not** edit `claim_support.py`, `claim_support_gemini.py`, any `phase14b_*` file, or `phase14b/` data.

### 4.1 Provider
```python
EVALUATION_ID = "v3-claim-support-eval-14c-v1"; PROVIDER_ID = "groq-claim-support-v1"
MODEL_ID = "openai/gpt-oss-120b"; PROMPT_VERSION = "14b-prompt-v1"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
REQUEST_SETTINGS, RESPONSE_SCHEMA  # exactly as §3.1
TEMPERATURE_NOTE = "provider converts 0 to 1e-8"
def build_prompt(payload: dict) -> str            # returns claim_support_gemini.build_prompt(payload)
def build_request(prompt: str) -> dict            # exact body of §3.1 (a fresh dict each call)
@dataclass(frozen=True)
class ProviderResponse: status: int; body: dict; headers: Mapping[str, str]   # header names lower-case
Transport = Callable[[dict], ProviderResponse]    # takes the request body; may raise ProviderStop
class ProviderStop(Exception):                   # the run must stop; never becomes a disposition
    reason: str            # RATE_LIMITED | PROVIDER_UNAVAILABLE | AUTH_ERROR | REQUEST_REJECTED | NETWORK_ERROR
    status: int | None; retry_after: float | None
def http_transport(body: dict, *, client: httpx.Client | None = None, timeout: float = 60.0) -> ProviderResponse
    # reads GROQ_API_KEY at call time (RuntimeError if missing); POSTs to API_URL; maps httpx
    # timeout/connection errors to ProviderStop("NETWORK_ERROR") with the exception class name only
    # (never str(exc), never headers); non-JSON body -> body = {}
def verify_claim_support_p14c(claim: str, evidence: EvidenceChunk, *, transport: Transport,
                              sleep: Callable[[float], None] = time.sleep) -> P14cOutcome
@dataclass(frozen=True)
class P14cOutcome: result: ClaimSupportResult; response_model: str | None; system_fingerprint: str | None
                   finish_reason: str | None; usage: Mapping[str, int]; attempts: int
```
`verify_claim_support_p14c` applies §3.4: content = `body["choices"][0]["message"]["content"]`; any
`reasoning` field is ignored. Status mapping happens here, so the transport stays a thin HTTP shim.

### 4.2 Ledger rows (`dispositions.jsonl`, one per pair, ordered prefix)
`{evaluation_id, provider_id, model_id, prompt_version, temperature_requested, temperature_note,
request_settings, challenge_fingerprint, protocol_sha256, zdr_attested, claim_pair_id, order_index,
verdict, confidence, supporting_spans, reason, source_integrity_pass, response_model, system_fingerprint,
finish_reason, usage, attempts, request_utc, latency_ms}` — never the key, the prompt, the raw response,
reasoning text, or any construction label. `protocol_sha256` = SHA-256 of this spec file's bytes.

### 4.3 Runner
```
python scripts/phase14c_run_claim_support.py --check-env        # no network
python scripts/phase14c_run_claim_support.py --dry-run          # fake transport, temp folder, no network
python scripts/phase14c_run_claim_support.py --preflight        # 1 GET /openai/v1/models/openai/gpt-oss-120b, no payload
python scripts/phase14c_run_claim_support.py --live --attest-zdr --max-requests 120
```
Importable API (tests load the script by path):
```python
@dataclass(frozen=True)
class Budget: requests_per_minute: int = 20; tokens_per_minute: int = 6000
              requests_per_day: int = 800; tokens_per_day: int = 150_000
def run(*, transport: Transport, out_dir: Path, max_requests: int, budget: Budget = Budget(),
        zdr_attested: bool, clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep) -> dict
    # -> {"done": int, "total": 135, "requests_made": int, "tokens_counted": int, "stopped_reason": str}
    # stopped_reason: COMPLETE | MAX_REQUESTS | DAILY_REQUEST_BUDGET | DAILY_TOKEN_BUDGET | RATE_LIMITED
    #                 | PROVIDER_UNAVAILABLE | AUTH_ERROR | REQUEST_REJECTED | NETWORK_ERROR
```
- `zdr_attested=False` → `ValueError` before any call (the live CLI path requires `--attest-zdr`).
- `prepare_corpus()` runs at most once per process (module-level cache); chunks are still resolved per pair
  with `get_chunk_by_id` and its provenance checks.
- `out_dir` resolving to or inside `data/eval_results/phase14b` → `ValueError`. An existing ledger whose rows
  differ in `evaluation_id`, `provider_id`, `model_id`, `prompt_version`, `request_settings` or
  `challenge_fingerprint` → `ValueError` ("mixed ledger"); nothing is appended.
- **Counting:** every HTTP attempt (including retries, 429s, 5xx and failed parses) is one call; it is
  appended to `calls.jsonl` *before* the next attempt: `{call_index, utc, kind ("inference"|"preflight"),
  claim_pair_id, attempt, http_status, outcome, retry_after, usage, tokens_counted, latency_ms,
  ratelimit (the six x-ratelimit-* headers if present), response_model, system_fingerprint}`. No prompt,
  content, key or headers other than those listed. `--max-requests` caps calls in this run; reaching it
  mid-pair discards that pair unwritten.
- **Budgets** (defaults are ~75–80 % of the published 30 RPM / 1K RPD / 8K TPM / 200K TPD): estimate =
  `ceil(len(prompt.encode("utf-8")) / 3) + max_completion_tokens`; tokens counted for a call =
  `usage.total_tokens` if present else the estimate. Before each call: if calls today (UTC, from
  `calls.jsonl`, all runs) ≥ `requests_per_day` → stop `DAILY_REQUEST_BUDGET`; if tokens today + estimate >
  `tokens_per_day` → stop `DAILY_TOKEN_BUDGET`; if calls in the last 60 s ≥ `requests_per_minute` or
  tokens in the last 60 s + estimate > `tokens_per_minute` → `sleep` until the window allows it (a call
  whose estimate alone exceeds `tokens_per_minute` waits only for an empty 60 s window). After a
  response whose `x-ratelimit-remaining-requests` ≤ 1 → finish the pair, then stop `DAILY_REQUEST_BUDGET`.
- **Live CLI guards:** `--live` refuses unless `--attest-zdr` is given, `GROQ_API_KEY` is set, and this
  spec is tracked and unmodified in git (`git ls-files --error-unmatch` and `git diff --quiet HEAD --`).
- Prints `done/135`, `stopped_reason`, calls made, and the exact rerun command. Never prints the key, the
  prompt or responses. `--check-env` prints only: key `present`/`missing` (never its length or any part),
  Python and httpx versions, protocol committed yes/no, ledger `done/135`, calls and tokens counted today.

### 4.4 Scorer
`python scripts/phase14c_score.py` → `score(ledger_path: Path, out_path: Path, calls_path: Path | None) -> dict`.
Refuses (ValueError): partial or unordered ledger; any row with `provider_id != PROVIDER_ID`,
`evaluation_id != EVALUATION_ID`, or mixed `model_id`/`prompt_version`/`request_settings`/
`challenge_fingerprint`; a ledger or output path under `phase14b/`. Writes `score.json` with: `evaluation_id`,
`provider_id`, `model_id`, `prompt_version`, `temperature_requested`, `temperature_note`,
`request_settings`, `challenge_fingerprint`, `protocol_sha256`, `ledger_sha256`, `claim_pairs`, `verdict`,
`conditions`, `metrics`, top-level `supported_precision` and `macro_f1`, `calls_total` (from
`calls.jsonl`), `system_fingerprints` (distinct values), and `label = "Phase 14C (second provider); not a
Phase 14B / Gemini result"`.

## 5. Gate for Phase 15′ (T2) — preregistered
14C counts toward T2 only if **all** hold: (a) 135/135 dispositions under this exact protocol and
`protocol_sha256`; (b) scored by `phase14c_score.py`; (c) verdict `CLAIM_SUPPORT_VERIFIER_USEFUL` under the
frozen thresholds; (d) Opus audits ledger, calls log and score and records the decision; (e) the user
explicitly approves the verdict for T2. Then T2 may use **only** this provider configuration (same
model, prompt, request settings, ZDR) as the `semantic` callable. Anything else → T2 stays disabled. See
`V4_CONSTRAINT_TIERS_SPEC.md` Amendment 2026-10-15.

## 6. Changes after approval
No edit to this protocol once committed. A different model, prompt, setting, threshold or provider is a new
evaluation ID with a new pre-registration committed before its first call, and every evaluation attempted
is reported (no silent reruns, no best-of selection). Rows already written are never rewritten.

## Acceptance (tests/test_p14c_claim_support.py, no network)
Protocol pinned by hash; prompt identical to 14B; exact request body and strict schema; no label fields and
no key in requests; parse/semantic checks as 14B (invented span, retry then parse failure, schema-400 and
truncation as parse failures, reasoning text discarded); 429 bounded wait then stop, 5xx / 401 / 404 stops
with nothing written; resumable ordered ledger, strict call counting, daily budgets across runs; refusal
of `phase14b/` paths and mixed ledgers; ZDR attestation required; real `http_transport` over
`httpx.MockTransport` (auth header, URL, no key on errors); scorer refuses partial/mixed ledgers and applies
the frozen gate.

## Out of scope
Changing 14B, the challenge, labels, order, thresholds or frozen data; paid plans; other models; batch
endpoints; live calls in tests; wiring T2 into the gate (Lane S, after §5 is met).
