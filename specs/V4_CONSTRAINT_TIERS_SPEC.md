# V4_CONSTRAINT_TIERS_SPEC — Phase 15′: tier-verified NDMA constraints in the joint indicator

Lane S (Builder S) · branch `m15p-constraints` (from `m26-recertify`, or from `main` after 25/26 merge)
· tests `tests/test_p15p_constraints.py` · dependent claim 13. **Build last in Wave B**: T2 needs the 14B
verdict (`data/eval_results/phase14b/score.json`, Lane X run, ≈ 7 days of free-tier quota).

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
