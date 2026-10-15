# V4_CERTIFIER_SPEC — Phase 24: sequential fail-closed certifier (element D)

Lane S (Builder S) · branch `m24-certifier` · depends on 22, 23 · tests `tests/test_p24_certifier.py`
Confidential: core patent element.

## Goal
Turn rollout indicators into a **gate**: a candidate dispatch may be suggested or executed only if a
one-sided Clopper–Pearson lower bound on `P(joint feasibility)` is ≥ `1 − ε`. Candidates that are not yet
proven either way are **UNDECIDED and blocked** (fail-closed). HOLD is always admissible.

## Files
`src/certify/params.py`, `src/certify/certifier.py`, `src/certify/calibration.py` (new);
`src/safety/models.py` (+ `RuleProvenance.CERTIFIED_CHANCE`, `RuleLayer.CERTIFIED`), `src/safety/masks.py`
(`evaluate_actions(..., certifier=None)`), `src/planners/certified.py` (new `CertifiedPlanner`).

## Interfaces
```python
@dataclass(frozen=True)
class CertParams:
    params_id: str = "v4-cert-v1"
    eps_dispatch: float = 0.05     # dispatch needs lower bound >= 0.95
    eps_keep: float = 0.10         # in-transit keep threshold (Phase 26), eps_keep > eps_dispatch
    delta: float = 0.01            # total error budget per decision epoch
    k0: int = 256; max_looks: int = 4          # n = 256, 512, 1024, 2048
    deadline_ms: float = 100.0
    theta_unsafe: float = 0.70     # = SafetyConfig.max_destination_hazard used by the episode
    k_sigma: float = 2.0; age_scale_s: float = 30.0
    w_strand: float = 1.0; w_unsafe: float = 1.5; w_overflow: float = 0.5
    backend: str = "sha256"
def get_cert_params(params_id: str) -> CertParams

class Verdict(str, Enum): FEASIBLE, INFEASIBLE, UNDECIDED
def clopper_pearson(successes: int, n: int, alpha: float) -> tuple[float, float]
    # one-sided bounds at level alpha each: lo = beta.ppf(alpha, s, n-s+1) (0 if s==0),
    # hi = beta.ppf(1-alpha, s+1, n-s) (1 if s==n)

@dataclass(frozen=True)
class CandidateCertificate:
    action_key: str; verdict: Verdict; successes: int; n: int
    lower: float; upper: float; mean_utility: float
    outcome_counts: Mapping[str, int]          # OK / STRANDED / UNSAFE / OVERFLOW (for the UI "why")
@dataclass(frozen=True)
class CertificationResult:
    root: str; params_id: str; a_max: int; looks: int; n_final: int; elapsed_ms: float
    deadline_hit: bool; candidates: tuple[CandidateCertificate, ...]; chosen_key: str  # "WAIT" if none
    def allowed_keys(self) -> frozenset[str]   # FEASIBLE only, plus "WAIT"

def certify(candidates: Sequence[Candidate], futures: FutureSet, ledger: LedgerView,
            world: V4WorldConfig, params: CertParams, graph: RoadGraph,
            *, clock: Callable[[], float] = time.perf_counter,
            rollout: Callable = rollout_joint) -> CertificationResult
def paired_argmax(feasible: Sequence[str], utilities: Mapping[str, Sequence[float]]) -> str
```

## Pseudocode
```text
alpha = params.delta / (params.max_looks * futures.A_MAX)      # Bonferroni over looks and the FIXED budget
status = {c: UNDECIDED}; S = {c: 0}; U = {c: []}; n = 0; K = params.k0
for look in 1..max_looks:
    for k in n+1..K:
        f = futures.future(k)
        for c in candidates (canonical action order):
            if status[c] == INFEASIBLE: continue
            r = rollout(c, f, ...); S[c] += r.z; U[c].append(r.utility)
        if clock() - start > deadline: deadline_hit = True; break
    n = number of futures completed for EVERY non-infeasible candidate (no partial looks)
    for c with status UNDECIDED:
        lo, hi = clopper_pearson(S[c], n, alpha)
        if lo >= 1 - eps_dispatch: FEASIBLE ; elif hi < 1 - eps_dispatch: INFEASIBLE
    if no UNDECIDED or deadline_hit: break
    K *= 2
feasible = [c for c if status FEASIBLE]
chosen = paired_argmax(feasible, U) if feasible else "WAIT"     # empty -> HOLD + escalate (Phase 25)
```
- `paired_argmax`: mean of per-future utility over the **common** futures (first `n` of each);
  ties broken by canonical action order. Candidates evaluated on identical futures (CRN).
- Deadline: futures already completed count; a partially processed future is discarded for all
  candidates (keeps pairing exact). UNDECIDED after the deadline stays blocked.
- Certified set is **independent of candidate order and of adding/removing other candidates**
  (keys never contain candidate index; α uses fixed `A_MAX`).

## Integration with the existing mask (legacy-safe)
`evaluate_actions(scenario, state, safety_config=..., *, enable_hard_safety=True, certifier=None)`.
`certifier` is any callable `(scenario, state, actions) -> Mapping[action_key, CandidateCertificate]`.
- `None` → exactly today's `SafetySnapshot` (test compares `to_dict()` with the legacy result).
- Given → for each mechanically valid, hard-safe dispatch append a `RuleVerdict(rule_id="CERTIFIED_ARRIVAL_FEASIBILITY", layer=CERTIFIED, provenance=CERTIFIED_CHANCE, allowed=verdict is FEASIBLE, reason_code=verdict.value, current_values=(("lower", lo), ("upper", hi), ("n", n), ("threshold", 1-eps)))`;
  `final_allowed` = previous AND allowed. WAIT unchanged. Human override (`allowed_override_actions`)
  therefore only offers certified actions automatically.
- `CertifiedPlanner.choose_action(planner_input)` returns the certifier's `chosen_key` (or WAIT) with
  `CandidateScore`s = mean utilities; `planner_id = "certified-v4"`.

## Calibration monitor — `calibration.py`
Rolling window of (predicted lower bound, realised outcome of the executed dispatch). Coverage =
share of executed FEASIBLE dispatches that succeeded. If coverage over the last 50 executions
< `1 − eps_dispatch − 0.02`, `recommend_fallback()` returns `"TIGHTEN"` (halve ε) and, below
`1 − 2·eps_dispatch`, `"DETERMINISTIC_MASK"`. Report only; Phase 25 wires actions.

## Acceptance (tests/test_p24_certifier.py)
`clopper_pearson` against SciPy reference values; FEASIBLE / INFEASIBLE / UNDECIDED rules; UNDECIDED is
not in `allowed_keys`; false-accept rate ≤ δ on synthetic Bernoulli candidates with true p = 0.94
(1,000 reps in CI; 10,000 in `scripts/phase24_coverage.py`); deadline with a fake clock leaves
undecided blocked; order invariance (shuffle candidates → identical certificates); `evaluate_actions`
legacy equality with `certifier=None`; `CERTIFIED_CHANCE` verdict appears and gates `final_allowed`.
Latency: `scripts/phase24_latency.py` reports p50/p95 for n = 256 on seed 620000 (target p95 ≤ 100 ms on
the laptop; Pi in Phase 27C) — informational, written to `data/eval_results/phase24/latency.json`.

## Runner may
H1 runs; H2 locate `evaluate_actions` callers; H4 reference-value table fixture.

## Amendments
- 2026-10-14 (lead-advisor): latency re-scoped. `scripts/phase24_latency.py` reports at n = 256 on seed 620000: (i) certify-only time on already-built futures, target p95 <= 100 ms; (ii) end-to-end time including future generation on the restricted edge set, target p95 <= 10 s on the laptop. Both informational. `CertParams.deadline_ms` default is 30_000.0 (a decision epoch is 120 s of simulated time). Pi latency and any vectorised/Philox fast path move to Phase 27C and must pass a bit-identity test against `derive_road_state`.
