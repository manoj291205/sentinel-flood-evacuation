# V4_FUTURES_SPEC — Phase 22: keyed future generator (invention element B)

Lane S (Builder S) · branch `m22-futures` · depends on 21 · tests `tests/test_p22_futures.py`
Confidential: core patent element.

## Goal
Generate many possible hazard futures from the **current prepared observation only**, such that
1. each future is regenerable bit-for-bit from a stored root key and an index `k`;
2. every draw is keyed by *(root, k, stream, absolute timestep, entity)* — never by draw order, by
   candidate index or by which/how many candidates are evaluated (order- and set-invariance);
3. the existing dynamics (`evolve_flood_state`, `derive_road_state`, shelter degradation, walk-ins)
   run **unchanged** as the future dynamics, by passing a duck-typed stream object.

## Files
- `src/certify/__init__.py`, `src/certify/futures.py`, `src/certify/forecast.py` (new).
- `src/sim/stochastic.py`: extract the body of `_degrade_shelters` and the walk-in step into pure
  functions taking `(state, config, streams, t)` so futures can call them (no behaviour change).

## Interfaces
```python
CERT_KEY_VERSION = "sentinel-cert-v1"

def root_key(*, incident_id: str, forecast_hash: str, graph_fingerprint: str,
             ledger_hash: str, params_id: str, backend: str = "sha256") -> str:
    # sha256 over compact JSON [CERT_KEY_VERSION, incident_id, forecast_hash,
    # graph_fingerprint, ledger_hash, params_id, backend] -> 64-char hex

class FutureStreams:                      # duck-types EpisodeRandomStreams
    def __init__(self, root: str, k: int, config_id: str): ...
    root_seed: int        # int(root[:15], 16) — only for code that reads it; never used for draws
    config_id: str
    replication_id: int   # == k
    def uniform(self, stream: RandomStream, *key) -> float
    def normal(self, stream: RandomStream, *key) -> float
    # digest = sha256(json(["sentinel-cert-future-v1", root, k, stream.value, list(key), lane]))
    # uniform/normal exactly as EpisodeRandomStreams (same lanes, same Box–Muller)

@dataclass(frozen=True)
class ForecastSnapshot:                   # forecast.py — what futures may condition on
    incident_id: str; timestep: int; timestep_minutes: float; uncertainty_config_id: str
    zone_severity: tuple[tuple[str, float], ...]; zone_trend: tuple[tuple[str, str], ...]
    shelter_severity: tuple[tuple[str, float], ...]; shelter_status: tuple[tuple[str, str], ...]
    edge_open: tuple[tuple[str, bool], ...]          # current RoadState
    regional_shock_estimate: float                   # 0.0 in v1 (latent state is NOT read)
    def forecast_hash(self) -> str                   # sha256 canonical JSON, floats repr-rounded to 1e-9
def forecast_from_state(state: EpisodeState, road_state: RoadState, scenario: ScenarioV3) -> ForecastSnapshot
def ledger_hash(state: EpisodeState) -> str          # occupancy, reserved, pending groups (id, people, shelter, arrival)

@dataclass(frozen=True)
class FutureTrajectory:                   # exogenous world only; no candidate enters it
    k: int; start_timestep: int; steps: int
    def edge_open(self, edge_id: str, t: int) -> bool
    def edge_hazard(self, edge_id: str, t: int) -> float
    def shelter_severity(self, shelter_id: str, t: int) -> float
    def shelter_status(self, shelter_id: str, t: int) -> str
    def walk_ins(self, shelter_id: str, t: int) -> int
    def travel_normal(self, *key) -> float           # TRAVEL stream of this future (for rollouts)

class FutureSet:
    def __init__(self, forecast: ForecastSnapshot, graph: RoadGraph, world: V4WorldConfig,
                 root: str, horizon_steps: int, backend: str = "sha256"): ...
    def future(self, k: int) -> FutureTrajectory        # lazy, memoised per k, k >= 1
    A_MAX: int                                          # fixed candidate budget (see below)
```
- Futures start from the forecast snapshot (observed severities and statuses, current edge state),
  then for `t = now+1 … now+H` apply: `evolve_flood_state` (with `FutureStreams`, regional shock
  starting at `regional_shock_estimate`), the shelter-degradation function, `derive_road_state`
  (with `streams=FutureStreams`, `previous=` last step), walk-ins. Absolute `t` is passed exactly as
  the live simulator does, so draws for the same `(t, entity)` coincide across successive decision
  epochs that share a root (temporal coherence).
- **No leakage:** `FutureSet` takes no `StochasticSimulator`, no `_StochasticContext`, no
  `EpisodeRandomStreams`. A test builds two simulators that differ only in latent regional state and
  identical observations; their futures must be identical.
- `A_MAX = len(canonical dispatch actions) + 1` (zones × shelters + HOLD); it is fixed by the scenario,
  not by how many candidates survive the mask — used by the certifier's δ split (Phase 24).
- Backend `"sha256"` is required. Backend `"philox"` (NumPy `Philox` keyed from the same digest of
  `(root, k, stream, key)`) is optional and only for speed; the certificate records the backend and
  replay must use the same one.

## Edge cases
`H` beyond scenario horizon → truncate at horizon. Graph fingerprint mismatch with forecast → raise.
`k < 1` → `ValueError`. Memoisation must not change results (pure functions).

## Acceptance (tests/test_p22_futures.py)
Determinism; `root_key` changes when any component changes; `FutureStreams` values equal for the same
key regardless of call order (Hypothesis); trajectory independent of which candidates are later rolled
out; no-leakage test; `FutureStreams` accepted by `evolve_flood_state` and `derive_road_state`
unchanged; replay: two `FutureSet`s from equal inputs give identical trajectories for k = 1..64.
Performance smoke: building 256 futures × 10 steps on the Fort Kochi graph < 20 s on a laptop
(informational, not asserted in CI).

## Runner may
H1 test runs, H4 Hypothesis strategy boilerplate from the signatures above.
