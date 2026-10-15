# V4_ROLLOUT_SPEC — Phase 23: joint first-hitting evaluator + G23 pilot (element C)

Lane S (Builder S) · branch `m23-rollout` · depends on 21, 22 · tests `tests/test_p23_rollout.py`
Confidential: core patent element.

## Goal
For one candidate dispatch and one future, follow the group along its path to its **own** arrival
time and return a single joint indicator: *every edge open when entered* ∧ *shelter safe at arrival*
∧ *ledger-projected seats free at arrival ≥ group size + margin*. Evaluate all three in the **same**
future. Provide ablation twins so Phase 27 can prove the coupling matters.

## Files
`src/certify/rollout.py`, `src/certify/ledger_view.py`, and **`src/certify/params.py` with the
`CertParams` dataclass exactly as defined in `V4_CERTIFIER_SPEC.md`** (Phase 24 adds `get_cert_params`
and the certifier around it). Reads `FutureTrajectory` (22),
`TransitPlan` edge-time rules (21), `V4WorldConfig`.

## Interfaces
```python
@dataclass(frozen=True)
class Candidate:
    zone_id: str; shelter_id: str; people: int
    edge_ids: tuple[str, ...]          # shortest_valid_path at decision time
    departure_timestep: int
    @property
    def action_key(self) -> str        # "Z-03->S-04" style, same as ActionSafetyEvaluation.action_key
HOLD_KEY = "WAIT"

@dataclass(frozen=True)
class LedgerView:                       # ledger_view.py
    timestep: int
    capacity_total: Mapping[str, int]; occupancy: Mapping[str, int]
    reserved: Mapping[str, int]
    pending: tuple[tuple[str, str, int, int], ...]   # (event_id, shelter_id, people, arrival_timestep)
    occupancy_sigma: Mapping[str, float]             # 0.0 in simulation; HIL sensors fill it (Phase 28)
    occupancy_age_s: Mapping[str, float]
def ledger_view_from_state(state: EpisodeState, plans: Mapping[str, TransitPlan]) -> LedgerView

class Outcome(str, Enum): OK, STRANDED, UNSAFE, OVERFLOW
@dataclass(frozen=True)
class RolloutResult:
    z: bool; outcome: Outcome; arrival_timestep: int | None; utility: float
    path_ok: bool; shelter_ok: bool | None; capacity_ok: bool | None   # components, for ablations/UI "why"

def rollout_joint(c: Candidate, f: FutureTrajectory, ledger: LedgerView,
                  world: V4WorldConfig, params: CertParams, graph: RoadGraph) -> RolloutResult
def rollout_components(c, f_path, f_shelter, f_capacity, ledger, world, params, graph) -> RolloutResult
    # ablation "marginal": the three conditions read from three DIFFERENT futures
def candidate_key_for_no_crn(c: Candidate) -> str   # ablation "no CRN": per-candidate future offset
```

## Pseudocode (rollout_joint)
```text
dt = world.timestep_minutes
t_min = c.departure_timestep * dt + world.boarding_minutes
for e in c.edge_ids:
    step = ceil(t_min / dt)
    if not f.edge_open(e, step):                         -> STRANDED (path_ok False), utility_stranded
    v = min(edge.assumed_speed_kph, world.evacuation_speed_cap_kph) * (1 - world.flood_speed_reduction * f.edge_hazard(e, step))
    m = clip(1 + sigma_travel * f.travel_normal(c.departure_timestep, c.zone_id, c.shelter_id, e))
    t_min += 60 * edge.length_m / 1000 / max(v, 1.0) * m
arr = max(c.departure_timestep + 1, ceil(t_min / dt))
if f.shelter_status(s, arr) == "CLOSED" or f.shelter_severity(s, arr) >= params.theta_unsafe:
                                                         -> UNSAFE, utility_unsafe
reserved_s = sum(p for (_, sh, p, _) in ledger.pending if sh == s)   # ALL committed seats, any arrival time
walk = sum(f.walk_ins(s, t) for t in ledger.timestep+1 .. arr)
free = cap[s] - occ[s] - reserved_s - walk
margin = params.k_sigma * ledger.occupancy_sigma[s] * (1 + ledger.occupancy_age_s[s] / params.age_scale_s)
if free < c.people + margin:                             -> OVERFLOW, utility_full
return OK, utility_arrived
```
Travel noise is keyed by **(departure, zone, shelter, edge)**, identical to the live simulator in
Phase 21, so a rollout of the action actually taken reproduces the live travel draw in the true
future. **Nothing in the rollout reads other candidates**; reserved seats of *already committed* groups
enter only through `ledger.pending`.

Utilities (deterministic, documented constants in `CertParams`):
`utility_arrived = people`, `utility_stranded = -w_strand * people`, `utility_unsafe = -w_unsafe * people`,
`utility_full = -w_overflow * people`, defaults `w_strand = 1.0, w_unsafe = 1.5, w_overflow = 0.5`.
HOLD utility per future = 0 (it is always admissible and never rolled out).

## G23 pilot — `scripts/phase23_g23_pilot.py`
v4 worlds MEDIUM and HIGH, practical seeds 620000–620059, Baseline A drives the episode; at every
decision state evaluate every mechanically valid dispatch with n = 1024 futures two ways:
joint `p_J = mean(z)` and product of marginals `p_M = p_path · p_shelter · p_capacity`
(each component estimated with `rollout_components` on independent futures).
Write `data/eval_results/phase23/g23.json`: number of (decision, candidate) pairs, distribution of
`p_M - p_J`, share of pairs where the verdict at threshold 0.95 differs (`p_J >= 0.95` xor `p_M >= 0.95`).
**G23 PASS** iff ≥ 2,000 pairs and verdict disagreement ≥ 1.0 % (or mean |p_M − p_J| ≥ 0.01 with a
paired-bootstrap 95 % CI excluding 0). FAIL → stop and escalate to Lead (report §19 fallback:
lead with migration, Phase 26).

## Acceptance (tests/test_p23_rollout.py)
Hand-built `FutureTrajectory` stubs: closed edge before entry → STRANDED; edge closes after the group
passed → OK; shelter unsafe exactly at arrival → UNSAFE; walk-ins consume reserved seats → OVERFLOW;
seats reserved for other in-transit groups count whether they arrive before or after this group; constructed case where all three marginals are
≥ 0.95 but the joint is < 0.95 (negatively coupled futures) — `rollout_joint` sees it; rollout result
for candidate A identical whether or not candidate B was rolled out first.

## Runner may
H1 runs, H4 trajectory-stub fixtures from the dataclass signatures.

## Amendments
- 2026-10-14 (lead-advisor): G23 pilot deviation for performance. n = 256 futures per estimate; p_J and the three marginals each use their own disjoint k-block of one FutureSet (1..256, 257..512, 513..768, 769..1024). H per decision = min(scenario remaining, ceil((boarding + 1.5 x max nominal canonical-path time at the speed cap) / dt) + 1). A rollout whose arrival falls beyond H counts as z = 0 and the pilot logs that share; if it exceeds 1 %, rerun with H + 4. PASS iff >= 2,000 pairs AND either (a) the paired-bootstrap 95 % CI of the signed mean (p_M - p_J) excludes 0, or (b) verdict disagreement minus a noise floor is >= 1.0 %. The noise floor is the expected flip rate at 0.95 between two Binomial(256, p_J_hat)/256 draws (parametric bootstrap). The criterion |p_M - p_J| >= 0.01 is dropped because noise biases it upward.
