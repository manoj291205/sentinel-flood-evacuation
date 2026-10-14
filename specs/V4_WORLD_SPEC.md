# V4_WORLD_SPEC — Phase 21: simulator realism ("v4 world")

Lane S (Builder S) · branch `m21-v4-world` · acceptance tests `tests/test_p21_world.py` · gate **G21**

## Why
Measured on `main` (seed 620000, `v3-medium-v1`): Fort Kochi graph trips take **0.48–2.63 min** while
`timestep_minutes = 10`, so every dispatch arrives after exactly 1 step and nothing can go wrong in
transit (arrivals always succeed in `_process_arrivals`). An arrival-time certificate has nothing to
certify. Phase 21 makes trips span several steps and lets them fail, **only under new `v4-*` IDs**.

## Non-negotiables
- Every legacy entry point (`StochasticSimulator(scenario, "v3-*")`, `build_geospatial_demo_runtime`,
  `derive_road_state(...)` without `streams=`, planners with default `PlannerInput`) is **bit-identical**.
  The Phase 20 frozen-artifact test and all 735 legacy tests must stay green.
- No edits to `data/geospatial_v3/**`. A wider graph, if ever needed, goes in `data/geospatial_v4/`.

## Design

### 1. `src/sim/world.py` (new)
```python
@dataclass(frozen=True)
class V4WorldConfig:
    world_id: str                    # e.g. "v4-medium-dt2-v1"
    base_uncertainty_id: str         # "v3-low-v1" | "v3-medium-v1" | "v3-high-v1"
    timestep_minutes: float = 2.0
    horizon_steps: int = 45          # 90 simulated minutes
    boarding_minutes: float = 4.0    # loading time before the vehicle moves
    flood_speed_reduction: float = 0.6   # speed *= (1 - r * edge_hazard)
    evacuation_speed_cap_kph: float = 15.0
    closure_model: str = "EDGE"      # route-level closures disabled; edges are authoritative
    walk_in_rate: float = 0.6        # mean walk-ins per shelter per step at hazard 1.0
    enable_transit_failures: bool = True
def get_world_config(world_id: str) -> V4WorldConfig      # KeyError-style ValueError like configs.py
V4_WORLDS: dict[str, V4WorldConfig]   # v4-low-dt2-v1, v4-medium-dt2-v1, v4-high-dt2-v1
def scaled_uncertainty(world: V4WorldConfig) -> UncertaintyConfig
```
`scaled_uncertainty` derives a per-step config from the 10-minute base with `f = dt / 10`:
`sigma *= sqrt(f)` (regional, local), `persistence = base ** f`, `drift *= f`,
`travel_noise_fraction` unchanged, per-step probabilities `p' = 1 - (1 - p) ** f` for
`maximum_closure_probability`, `shelter_degradation_probability`; `base_closure_multiplier` and
`hazard_to_closure_strength` scaled by `f`; thresholds unchanged. `config_id = world_id + "-unc"`,
`version = 1`. Register the three scaled configs in `UNCERTAINTY_CONFIGS` **in addition to** the
legacy ones (adding keys only).

### 2. Transit plans and failures — `src/sim/transit.py` (new) + small hooks
```python
class TransitOutcome(str, Enum): ARRIVED, STRANDED, ARRIVAL_UNSAFE, ARRIVAL_OVERFLOW
@dataclass(frozen=True)
class TransitPlan:
    event_id: str; zone_id: str; shelter_id: str; people: int
    departure_timestep: int
    edge_ids: tuple[str, ...]
    edge_entry_minutes: tuple[float, ...]   # absolute sim minutes when each edge is entered
    arrival_minutes: float
    @property
    def arrival_timestep(self) -> int       # ceil(arrival_minutes / dt), >= departure + 1
```
- Edge minutes: `edge.length_m / (min(assumed_speed, cap) * (1 - r * hazard_at_entry) km/h)` × keyed
  travel multiplier `streams.normal(TRAVEL, departure_timestep, zone_id, shelter_id, edge_id)`
  (clipped like `realize_dispatch_travel`). **Keyed by (departure, zone, shelter, edge)** — never by an
  event sequence number or candidate index (Phase 22/23 reuse this rule).
- Path at dispatch = `shortest_valid_path` on the current `RoadState`.
- New `DispatchStatus` members `STRANDED`, `ARRIVAL_UNSAFE`, `ARRIVAL_OVERFLOW` and matching
  `AuditEventType` members (`GROUP_STRANDED`, `ARRIVAL_UNSAFE`, `ARRIVAL_OVERFLOW`, `WALK_IN`). Adding
  enum members only.
- Each prepared timestep in a v4 world, for every in-transit group, in this order:
  1. **Stranding:** if any edge whose entry minute is `> (t-1)*dt` and `<= t*dt` is closed at `t`
     → `STRANDED` at `t`; release its reservation; people go to `people_stranded` (new counter on
     `EpisodeState`, default 0, included in `to_dict()` only when the world is v4 — legacy dict unchanged).
  2. **Arrival** at `arrival_timestep`: shelter `CLOSED` or severity `>= uncertainty.closed_threshold`
     → `ARRIVAL_UNSAFE` (release reservation; people → `people_unsafe_arrival`). Else admit
     `min(people, capacity_total - occupancy_current)`; the rest → `ARRIVAL_OVERFLOW`
     (`people_overflow`). Admitted people count as `people_safely_arrived`.
- **Walk-ins** (keyed `RandomStream.WALK_IN`, new member, key `(t, shelter_id)`):
  `walk_ins = floor(walk_in_rate * mean_zone_hazard * 2 * u)` with `u = uniform(...)`, capped so
  `occupancy_current <= capacity_total`. Walk-ins raise occupancy but **not** reservations, so reserved
  seats can be lost — this is what creates `ARRIVAL_OVERFLOW`.
- Invariants (`src/sim/invariants.py`): in v4 worlds replace "occupancy + reserved <= capacity" with
  "occupancy <= capacity" and add population conservation
  `initial = remaining + in_transit + safe + stranded + unsafe + overflow`. Legacy checks unchanged.

### 3. Unified edge-only closures
With `closure_model == "EDGE"`, `update_route_state(..., realize_closures=...)` must not realize
route-level closures (call it with `realize_closures=False` from the v4 path); route reachability comes
only from `GeospatialRouteOverlay` / `_adapt_routes`. This removes the double closure (route proxy +
edges).

### 4. Replication fix — `src/geospatial/road_network.py`
`derive_road_state(..., streams: EpisodeRandomStreams | None = None)`. `None` keeps the current
construction `EpisodeRandomStreams(scenario_seed, config_id)` (legacy bit-identical). The v4 overlay
passes the simulator's own streams, so `replication_id` now changes edge hazards/closures.

### 5. Planner threshold — `src/planners/model.py:209`
Add `max_destination_hazard: float = 0.70` to `PlannerInput` (filled by `build_planner_input` from the
`SafetyConfig` actually used) and to `ModelState`; replace the literal `0.70`. Defaults keep every
legacy planner output identical. **Do not add the field to `PlannerInput.to_dict()`** (legacy
serialisation must not change).

Counters on `EpisodeState`: `people_stranded`, `people_unsafe_arrival`, `people_overflow` (all `int = 0`,
always present as attributes; serialised only in v4 worlds).

### 6. Runtime — `src/geospatial/v4_runtime.py` (new)
```python
def build_v4_runtime(world_id: str = "v4-medium-dt2-v1", *, generator_seed: int = 620000,
                     graph: RoadGraph | None = None, replication_id: int = 0
                     ) -> tuple[ScenarioV3, StochasticSimulator, RoadGraph, GeospatialRouteOverlay, V4WorldConfig]
```
Same scenario generator as `_graph_scenario`, with `time = TimeConfig(world.timestep_minutes,
world.horizon_steps)`, the scaled uncertainty config, and `StochasticSimulator(..., world=world)`.
`StochasticSimulator.__init__` gains keyword `world: V4WorldConfig | None = None`; all v4 behaviour is
behind `world is not None`. The simulator keeps the `TransitPlan` per event (harness-side, like
`_StochasticContext`; never in the policy observation except `arrival_timestep`).

## Gate G21 — `scripts/phase21_gate_g21.py`
Run Baseline A (Risk-Greedy + `V3_SAFETY_V1` mask, i.e. today's decision layer) on the v4 worlds,
practical seeds `620000–620119`, replication 0, all three levels. Write
`data/eval_results/phase21/g21.json` with per level: dispatched groups, stranded / unsafe / overflow
counts and rates, median and p90 travel lag (steps), Pearson correlation between path hazard exposure
and destination shelter severity at dispatch, runtime.
**G21 PASS** iff failure rate (stranded + unsafe + overflow groups / dispatched groups) ≥ 3 % on HIGH
and ≥ 1 % on MEDIUM, median lag ≥ 3 steps on all levels, correlation > 0.1 on MEDIUM.
If it fails: do **not** tune silently. Report numbers in STATUS and stop; Lead decides (options in
order: raise `walk_in_rate`, lower `evacuation_speed_cap_kph`, `dt = 1`, wider graph).

## Pseudocode (v4 prepare step, inserted in `_prepare_timestep` when `world` is set)
```text
state, arrivals = process_v4_transit(state, plans, road_state, unc, t)   # strand -> arrive/unsafe/overflow
state = evolve_flood_state(...)                       # unchanged
state = update_route_state(..., realize_closures=False)
state = degrade_shelters(...)                         # unchanged, scaled probabilities
state, edge_records = overlay(scenario, state)        # edge closures (streams with replication)
state = apply_walk_ins(state, streams, world, t)
state = update_observable_forecasts(...)
```
Stranding is checked against the road state of the **current** step (closures are absorbing).

## Runner may
Run tests (H1), locate `0.70` / `derive_road_state` call sites (H2), generate the G21 JSON summary
table for the STATUS note (H5).

## Out of scope
Certification (22–24), wider graph download, any change to v3 configs or frozen data.
