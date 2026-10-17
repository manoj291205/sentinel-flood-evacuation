# V4_CONSTRAINT_TIERS_SPEC — Phase 15′: tier-verified NDMA constraints in the joint indicator

Lane S (Builder S) · branch `m15p-constraints` (from `m26-recertify`, or from `main` after 25/26 merge)
· tests `tests/test_p15p_constraints.py` · dependent claim 13. **Build last in Wave B**: T2 needs the 14C
verdict (`data/eval_results/phase14c/score.json`, Lane X run; 14C replaced 14B — see Amendment below).

## Goal
Document rules (NDMA flood guidelines) enter the **joint indicator** of Phase 23 as extra per-future
predicates, but only at the trust tier their evidence earns. A rule whose stored source chunk or verbatim
span no longer verifies drops to T0 and is applied in its **strict fallback** form, which changes the mask
and is audited. First real use of `RuleProvenance.DOCUMENT_POLICY`.

## Files (Lane S)
`data/constraints_v4/ndma_constraints.json` (new; rules, see schema), `src/constraints/tiering.py`,
`src/constraints/ndma_rules.py` (new); `src/certify/rollout.py` (`extra_terms` keyword on
`rollout_joint` / `rollout_components`, default `()` = unchanged); `src/certify/gate.py` (passes the
active predicates; certificate `params.params_id` becomes `v4-cert-v1+rules-<sha8>` when rules are active);
`src/safety/masks.py` (one `RuleVerdict` per active rule on each dispatch, provenance DOCUMENT_POLICY);
`src/sim/events.py` (`AuditEventType.RULE_STRICT_FALLBACK` — member only); `tests/test_s_p15p_*.py`.
Do not edit `src/constraints/claim_support*.py` (frozen protocol / Lane X).

## Rule file (`ndma_constraints.json`: `{"schema": "ndma-constraints-v1", "rules": [rule, ...]}`)
```json
{"rule_id": "NDMA-R01", "text": "...", "predicate": "MAX_TRAVEL_MINUTES", "params": {"minutes": 40},
 "strict_fallback": {"minutes": 25}, "evidence": {"source_id": "...", "filename": "...", "page": 64,
 "chunk_id": "...", "passage_sha256": "<64 hex>", "span": "verbatim text from the chunk"},
 "approved": false, "approved_by": null, "approved_utc": null}
```
Predicate types (closed set): `MAX_TRAVEL_MINUTES {minutes}` (arrival minute − dispatch minute, boarding included; dispatch minute =
`start_minutes` if set else `departure_timestep · dt`);
`MAX_ROUTE_HAZARD {hazard}` (max edge hazard at entry along the path); `MAX_DESTINATION_SEVERITY
{severity}` (shelter severity at arrival); `MAX_OCCUPANCY_FRACTION {fraction}` ((occupancy + reserved +
walk-ins + people) / capacity at arrival). `strict_fallback` must be at least as strict as `params`
(validated on load).
**Human approval:** Builder S drafts 3–6 rules from the local corpus (`src/rag/ingest.prepare_corpus`,
`get_chunk_by_id`) with `approved: false`. Only rules with `approved: true` are loaded. The user approves
by editing the file (Builder S prints the list as a `⚠ NEEDS YOU` note at the end of the wave but does not
stop). Tests use their own fixture rules, never this file.

## Interfaces
```python
class Tier(str, Enum): T0 = "T0"; T1 = "T1"; T2 = "T2"
@dataclass(frozen=True)
class TieredRule: rule: NdmaRule; tier: Tier; reasons: tuple[str, ...]; active_params: Mapping[str, float]
def assign_tier(rule, chunk_lookup: Callable[[NdmaRule], EvidenceChunk | None], *,
                semantic: Callable[[str, EvidenceChunk], ClaimSupportResult] | None = None,
                semantic_verdict: str | None = None) -> TieredRule
    # T0: reason codes (all that apply, in this order): "CHUNK_MISSING" (lookup returned None);
    #     "CHUNK_HASH_MISMATCH" (verify_evidence_integrity False, or chunk.passage_sha256 != rule's);
    #     "SPAN_NOT_VERBATIM" (span not in chunk.text) -> active_params = strict_fallback
    # T1: all provenance checks pass -> active_params = params
    # T2: T1 and semantic_verdict == "CLAIM_SUPPORT_VERIFIER_USEFUL" and semantic(rule.text, chunk)
    #     returns SUPPORTED with source_integrity_pass -> params (tier recorded only)
    # semantic_verdict other than USEFUL -> T2 never assigned (no provider call)
def load_rules(path) -> tuple[NdmaRule, ...]                  # approved only; validation errors raise
@dataclass(frozen=True)
class ArrivalPredicate:
    rule_id: str; tier: Tier
    def __call__(self, c: Candidate, f, arrival: int, arrival_minutes: float, path_hazards: tuple[float, ...],
                 ledger: LedgerView) -> bool
def predicates_for(tiered: Sequence[TieredRule]) -> tuple[ArrivalPredicate, ...]
def tier_audit_records(tiered: Sequence[TieredRule], timestep: int) -> tuple[AuditRecord, ...]
    # one RULE_STRICT_FALLBACK record per T0 rule (rule id in route_id, reasons joined by ',' in reason_code)
```
`rollout_joint(..., extra_terms=())`: after the capacity term, every predicate must hold; a failing
predicate gives a new `Outcome.POLICY` (add member) with `utility = -w_overflow * people` and
`RolloutResult` gains `policy_ok: bool | None = None` (default keeps old constructors working).
Order of checks: path → shelter → capacity → predicates (first failure wins).

## Audit and mask
When a rule is T0 at decision time the gate writes `RULE_STRICT_FALLBACK` (rule id, reason codes) once
per decision epoch; each dispatch `RuleVerdict(rule_id=<rule>, layer=CERTIFIED, provenance=DOCUMENT_POLICY,
allowed=<certified>, reason_code=<tier>, current_values=(("tier", ...), *active_params))`. The
certificate's `params.params_id` names the rule set digest so replay uses the same rules.

## Acceptance (tests/test_p15p_constraints.py)
Tiering: verified fixture → T1; one byte of chunk text changed → T0 with `CHUNK_HASH_MISMATCH` and strict
params; span not in chunk → T0 `SPAN_NOT_VERBATIM`; USEFUL verdict + SUPPORTED fake provider → T2;
NOT_YET_RELIABLE → never T2 and the provider is not called; unapproved rules are not loaded; a
`strict_fallback` looser than `params` is rejected. Rollout: `extra_terms=()` leaves every P23 result
identical; a `MAX_TRAVEL_MINUTES` predicate turns an OK rollout into `POLICY`. With a fixed stub future: the same candidate is FEASIBLE under the T1 rule and not FEASIBLE once the chunk is
tampered (T0 strict fallback), and `tier_audit_records` returns one `RULE_STRICT_FALLBACK` record.

## Runner may
H1 runs, H2 corpus search for candidate spans, H4 fixture rules.

## Out of scope
Changing the 14B protocol, Gemini calls in tests, automatic rule extraction without human approval.

## Amendment 2026-10-15 (Lead) — where T2's semantic verdict may come from
Two separate claim-support evaluations exist: **14B** (`gemini-claim-support-v1`, `data/eval_results/phase14b/`)
and **14C** (`groq-claim-support-v1`, model `openai/gpt-oss-120b`, `data/eval_results/phase14c/`,
`specs/V4_CLAIM_SUPPORT_14C_SPEC.md`). Neither has a score yet, so **T2 stays disabled** and the gate keeps
calling `assign_tier` without `semantic_verdict` (T1 is the highest tier). No change to the code built on
`m15p-constraints` is required by this amendment.
- **Approval record.** The gate may pass `semantic_verdict` only from an Lead-written file
  `specs/approvals/t2_semantic_verifier.json` (does not exist yet):
  `{"evaluation_id", "provider_id", "model_id", "prompt_version", "request_settings", "score_path",
  "score_sha256", "verdict", "approved_by_user_utc", "approved_by_opus_utc"}`. It is written only when the
  evaluation is 135/135, scored by its own scorer, verdict `CLAIM_SUPPORT_VERIFIER_USEFUL` under the frozen
  thresholds, audited by Lead, **and** the user explicitly approves that verdict for T2.
- **Verification at load.** The loader re-hashes `score_path`; on a missing file, hash mismatch, verdict other
  than USEFUL, or provider/model/prompt/settings that differ from the `semantic` callable, it uses
  `semantic_verdict = None` (T2 disabled) and records why. A 14C verdict enables only the 14C provider
  configuration; a 14B verdict only the 14B one. Verdicts are never combined, averaged or substituted.
- **Calls.** Semantic checks run once per rule when rules are loaded (never per dispatch decision), with the
  same ZDR precondition as the evaluation. A provider error leaves the rule at T1 (never T0 for that reason,
  never T2 by default) and is logged; T2 changes no parameters, only the recorded tier.
- **UI honesty.** Evidence & Results lists 14B and 14C as separate rows; a missing score shows `-` and
  "Not run yet" (manifest items `p14b-*`, `p14c-*`). The tier shown for a rule is the tier actually assigned;
  "T2" never appears while the approval record is absent.
- Wiring the approval record into the gate is Lane S work scheduled after an approval exists (Wave C).

## Amendment 2026-10-15 (user + Lead) — 14C replaces 14B
The Gemini provider does not work, so 14B is superseded and will never be scored. **14C is the only source a T2
semantic verdict can come from.** The approval record, load-time verification and call rules above are unchanged;
read every "14B" there as historical. Evidence & Results keeps the `p14b-*` rows, labelled superseded (always "-").

## Amendment 2026-10-16 (user + Lead) — 14D replaces 14C as the only T2 source
14C failed its gate (`CLAIM_SUPPORT_VERIFIER_NOT_YET_RELIABLE`, 2026-10-16) and can never enable T2. **Phase 14D
(`specs/V4_CLAIM_SUPPORT_14D_SPEC.md`) is now the only source a T2 semantic verdict can come from.**
- The approval record `specs/approvals/t2_semantic_verifier.json` may be written only per 14D §8, with
  `"verdict": "T2_VERIFIER_USEFUL"` (14D's primary T2-use gate) and an extra field `prompt_sha256`. The loader
  accepts only that verdict string from that record, re-hashes `score_path`, and checks provider, model, prompt
  version, prompt hash and request settings against the `semantic` callable; any mismatch → T2 disabled.
- An accepted record makes the loader call `assign_tier(..., semantic_verdict="CLAIM_SUPPORT_VERIFIER_USEFUL")`.
  That string stays the internal "approved verifier" token of `assign_tier`, so the code on `m15p-constraints`
  and `tests/test_p15p_constraints.py` need no change.
- The 14D semantic callable cites by sentence number (14D §4); T2 still requires `SUPPORTED` with
  `source_integrity_pass`. Call rules, ZDR precondition and "T2 changes no parameters" are unchanged.
- Evidence & Results shows 14D as the evaluation of record, 14C as failed with its reasons (`p14c-*`), and 14B
  as superseded. "T2" never appears while the approval record is absent.

## Amendment 2026-10-17 (user + Lead) — P15T2: wiring the 14D approval record (T2 live)
The user approved the 14D verdict for T2 (2026-10-17) and `specs/approvals/t2_semantic_verifier.json` is on `main`.
P15T2 wires it. **Every T2 reference is 14D**; 14B (superseded) and 14C (failed) can never enable T2. `assign_tier`,
`tests/test_p15p_constraints.py` and the 14D files are unchanged. One-off lane exception (user, 2026-10-17): Lead
builds this Lane S code itself. Branch `m15t2-wiring`; acceptance tests `tests/test_p15t2_wiring.py` (milestone `P15T2`).

**Files (Lane S):** `src/constraints/t2_wiring.py` (new), `scripts/phase15t2_tier_rules.py` (new),
`data/constraints_v4/p15t2/` (new: live run output), `tests/test_s_p15t2_*.py`. The 14D module
`src/constraints/claim_support_p14d.py` (Lane X) is imported read-only, never edited.

**1. `load_t2_approval(path=APPROVAL_PATH, *, root=REPO_ROOT) -> T2Approval`** (frozen dataclass: `enabled: bool`,
`reason: str`, `record_sha256: str | None` = SHA-256 of the record file's bytes, and the record's `evaluation_id`,
`provider_id`, `model_id`, `prompt_version`, `prompt_sha256` or `None`). Never raises for a bad record. Checks in this
order; the first failure gives `enabled=False` and that reason:
`APPROVAL_MISSING` (no file) · `APPROVAL_UNREADABLE` (not UTF-8 JSON object) · `APPROVAL_FIELDS` (any of the 15′ fields
or `prompt_sha256` absent) · `VERDICT_NOT_T2_USEFUL` (`verdict != "T2_VERIFIER_USEFUL"`; a 14C/14B-style
`CLAIM_SUPPORT_VERIFIER_USEFUL` record fails here or earlier) · `EVALUATION_MISMATCH` / `PROVIDER_MISMATCH` /
`MODEL_MISMATCH` (≠ `claim_support_p14d.EVALUATION_ID` / `PROVIDER_ID` / `MODEL_ID`) · `PROMPT_VERSION_MISMATCH`
(≠ `"14d-prompt-r0"`, the frozen prompt) · `PROMPT_HASH_MISMATCH` (≠ the record's own `prompt_sha256` **and**
`claim_support_p14d.prompt_sha256("14d-prompt-r0")`, i.e. the prompt file on disk must still hash to the record) ·
`SETTINGS_MISMATCH` (`request_settings` key set or any value ≠ `claim_support_p14d.REQUEST_SETTINGS`) ·
`SCORE_PATH_INVALID` (absolute, or resolves outside `root`) · `SCORE_MISSING` · `SCORE_HASH_MISMATCH` (SHA-256 of the
score file's stored bytes ≠ `score_sha256`) · `SCORE_VERDICT_MISMATCH` (the score's `t2_verdict` or `evaluation_id`
disagrees with the record). All pass → `enabled=True`, `reason="ACCEPTED"`.

**2. `P14dSemantic(transport, *, sleep=time.sleep, clock=time.time)`** — the 14D semantic callable,
`__call__(claim, chunk) -> ClaimSupportResult` = `verify_claim_support_p14d(claim, chunk,
prompt_version="14d-prompt-r0", transport=transport, sleep=sleep).result`. It appends one metadata dict per call to
`self.calls` (`utc`, `latency_ms`, `outcome` = the verdict, `"PARSE_FAILURE"` or `"PROVIDER_STOP"`,
`source_integrity_pass`, `confidence`, `supporting_sentence_ids`, `attempts`, `response_model`,
`system_fingerprint`, `finish_reason`, `usage`, `stop_reason`, `http_status`). A `ProviderStop` is recorded and
re-raised. Never stored: the prompt, the claim/chunk payload, the raw response, the model's `reason` text, reasoning
text or any key value. T2 still needs `SUPPORTED` **with** `source_integrity_pass` (decided by `assign_tier`).

**3. `load_tiered_rules(rules_path, chunk_lookup, *, approval_path=APPROVAL_PATH, attest_zdr=False, transport=None,
env=os.environ, sleep=time.sleep, clock=time.time) -> TierLoad`** (frozen: `tiered: tuple[TieredRule, ...]`,
`approval: T2Approval`, `t2_enabled: bool`, `t2_reason: str`, `records: tuple[dict, ...]`). Loads approved rules
(`load_rules`), then decides T2 once for the whole load: disabled with `t2_reason` = the approval's reason if the
record is not accepted; else `ZDR_NOT_ATTESTED` if `attest_zdr` is not `True`; else `API_KEY_MISSING` if
`env.get("GROQ_API_KEY")` is empty (the key is only tested for presence here; it is read from the environment by
`http_transport` at call time and never stored, logged or returned); else enabled (`t2_reason="ENABLED"`),
`transport` defaulting to `claim_support_p14d`'s `http_transport`. Per rule:
- T2 enabled → `assign_tier(rule, chunk_lookup, semantic=<P14dSemantic>, semantic_verdict=USEFUL)` (USEFUL =
  `"CLAIM_SUPPORT_VERIFIER_USEFUL"`, the internal token). `assign_tier` calls the verifier only for rules whose
  provenance verifies, so a T0 rule makes no call. On `ProviderStop` the rule is re-tiered without `semantic`
  (T1 when provenance verifies — never T0 for that reason, never T2) and the stop is recorded.
- T2 disabled → `assign_tier(rule, chunk_lookup)`: no provider object is built and no call is made.
At most one semantic call per rule per load; nothing is called per dispatch decision: `TieredRule` holds no callable,
and the gate, masks, rollout and replay only read the returned tiers. **T2 changes no parameters:** T1 and T2 rules
have identical `active_params` and predicates; only the recorded tier (and so the `+rules-<sha8>` digest) differs.
`records` holds one JSON-ready dict per loaded rule: `rule_id`, `tier`, `reasons` (T0 codes), `active_params`,
`t2_enabled`, `t2_reason`, `approval_record_sha256`, `evaluation_id`, `provider_id`, `model_id`, `prompt_version`,
`prompt_sha256`, `semantic` (the call metadata above, or `null` when no call was made) and `semantic_status`
(`NOT_CALLED_T2_DISABLED`, `NOT_CALLED_T0`, `CALLED`, `PROVIDER_STOP`).

**4. Script `scripts/phase15t2_tier_rules.py`.** No flag: offline dry run (T2 disabled, no network), prints the tiers.
`--preflight`: one `GET /openai/v1/models/openai/gpt-oss-120b` with the key from the environment; prints the HTTP status only.
`--live --attest-zdr`: `load_tiered_rules` on `data/constraints_v4/ndma_constraints.json` with the local corpus
(`prepare_corpus` + `corpus_chunk_lookup`) and `http_transport`; refuses to overwrite an existing result; writes
`data/constraints_v4/p15t2/tier_results.json` (`schema "p15t2-tier-results-v1"`, `utc`, `rules_file_sha256`,
`approval_record_sha256`, `t2_enabled`, `t2_reason`, `calls_total`, `records`). Rule R03 (unapproved) is never loaded.
Before any live call the user re-confirms Zero Data Retention in chat (payload = the rule text, a modelling paraphrase
of public NDMA guidance, plus the public NDMA chunk; no gate work), and Lead audits the file before it is cited.

**5. Acceptance (`tests/test_p15t2_wiring.py`, fake transports, never the network).** The real record on `main` is
accepted. Accepted record + SUPPORTED / integrity-pass fake → T2 with the same `active_params` as T1. A PARTIALLY_SUPPORTED
fake, or SUPPORTED citing nothing → T1. Disabled with the stated reason and **zero** transport calls: tampered score hash,
wrong verdict string, wrong prompt hash, wrong settings, missing file, a 14C-style record, a 14B-style record, no ZDR
attest, no key. Provider stop (`ProviderStop`, e.g. HTTP 503) → T1, `semantic_status == "PROVIDER_STOP"`. A T0 rule is
not sent. Exactly one call per eligible rule at load and none afterwards (predicates evaluated, digest, audit records;
no `TieredRule` field is callable). Records carry the approval-record SHA-256 and call metadata, and no prompt, payload, model reason text or key.

**UI:** Evidence & Results shows 14D (`p14d-*`) as the evaluation of record, 14C as failed, 14B as superseded; a rule's tier
column shows T2 only when the API reports a T2 tier from this loader (part of 34A).
