# V4_CLAIM_SUPPORT_14B_SPEC — Phase 14B: rebuild provider, run, score

Lane X · branch `lane-x/m14b-claim-support` · tests `tests/test_p14b_claim_support.py`
Protocol authority: `V3_CLAIM_SUPPORT_SPEC.md` (frozen). This spec **adds no protocol change**; it
records the run amendment below and specifies the missing code.

## Run amendment (2026-10-14, Lead)
The Phase 14B provider code was never committed; `verify_claim_support` still raises
`NotImplementedError`. It is rebuilt here under the frozen protocol: existing Gemini provider pattern
(`src/constraints/generate.py:_call_gemini`, model constant `MODEL = "gemini-3.6-flash"`),
temperature 0.0, strict structured JSON output, payload = `build_verifier_payload(claim, evidence)`
only, evaluation order = `label_independent_order(pair_ids, challenge_fingerprint)`, thresholds =
`usefulness_gate`. Free-tier quota (≈ 20 requests/day) makes the run multi-day and resumable; a paid
key may be used (same model and settings). Nothing about labels, thresholds or order may change.

## Files (all Lane X)
- `src/constraints/claim_support_gemini.py` (new) — provider.
- `scripts/phase14b_run_claim_support.py` (new) — resumable runner.
- `scripts/phase14b_score.py` (new) — scorer.
- Output folder `data/eval_results/phase14b/` (new; becomes frozen once the final score is written).
- Do **not** edit `src/constraints/claim_support.py`; Lead wires `verify_claim_support` to the
  provider at audit (one-line delegation) — your provider must therefore expose the function below.

## Interfaces
```python
PROVIDER_ID = "gemini-claim-support-v1"
RESPONSE_SCHEMA = {  # Gemini structured output
  "type": "object",
  "properties": {"verdict": {"type": "string", "enum": ["SUPPORTED","PARTIALLY_SUPPORTED","UNSUPPORTED"]},
                 "confidence": {"type": "number"}, "supporting_spans": {"type": "array", "items": {"type": "string"}},
                 "reason": {"type": "string"}},
  "required": ["verdict","confidence","supporting_spans","reason"]}
def build_prompt(payload: dict) -> str          # instructions + json.dumps(payload); nothing else
def verify_claim_support_gemini(claim: str, evidence: EvidenceChunk, *,
                                client: Callable[[str], str] | None = None) -> ClaimSupportResult
    # client(prompt) -> raw JSON text; default = real Gemini call (key from GEMINI_API_KEY env only)
    # parse -> finalize_semantic_result(...); malformed JSON -> one retry, then UNSUPPORTED with
    # reason "PROVIDER_PARSE_FAILURE" and source_integrity_pass False (counted, never hidden)
```
Prompt instructions (fixed text, versioned `PROMPT_VERSION = "14b-prompt-v1"`): judge only whether the
evidence supports the exact claim; three verdict definitions copied from `V3_CLAIM_SUPPORT_SPEC.md`
"Claim-support labels"; supporting spans must be copied verbatim from the evidence; short reason; no
chain-of-thought.

## Runner
```
python scripts/phase14b_run_claim_support.py --max-requests 20 [--dry-run] [--client fake]
```
- Loads `data/eval_v3/phase14/claim_support_challenge.json` + manifest, verifies the challenge
  fingerprint, resolves chunks with `get_chunk_by_id` (with provenance checks).
- Order: `label_independent_order`. Skips pairs already in the ledger.
- Ledger `data/eval_results/phase14b/dispositions.jsonl`, one line per pair:
  `{claim_pair_id, order_index, provider_id, prompt_version, model, temperature, verdict, confidence,
  supporting_spans, reason, source_integrity_pass, request_utc, latency_ms}` — **never** the key,
  never the construction label.
- Stops cleanly at `--max-requests` or on HTTP 429; prints `done/135` and the exact command to rerun.
- `--client fake` uses a deterministic fake for tests/dry runs and writes to a temp ledger path.
- Importable API (tests load the script by path): `run(*, max_requests: int, client: Callable[[str], str],
  ledger_path: Path) -> dict` returning `{"done": int, "total": 135, "requests_made": int, "stopped_reason": "MAX_REQUESTS"|"COMPLETE"|"RATE_LIMITED"}`.

## Scorer
`python scripts/phase14b_score.py` refuses to score unless the ledger has all 135 pairs. Importable API:
`score(ledger_path: Path, out_path: Path) -> dict` (raises `ValueError` on a partial ledger). Joins labels
only at scoring time; computes `classification_metrics`, `span_integrity_failure_rate`,
`supported_precision = per_class["SUPPORTED"]["precision"]`, `usefulness_gate`; writes
`data/eval_results/phase14b/score.json` (+ ledger sha256, challenge fingerprint, provider/prompt
versions). Prints the verdict.

## Acceptance (tests/test_p14b_claim_support.py)
Payload equality with `build_verifier_payload`; no label fields reach the client; parse + finalize
behaviour (invented span → integrity failure); retry then parse-failure path; runner resumes and
respects `--max-requests` with the fake client; ledger contains no `GEMINI_API_KEY` value; scorer
refuses partial ledgers and reproduces `usefulness_gate` on a fake full ledger. No network in tests.
