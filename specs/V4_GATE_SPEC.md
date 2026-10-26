# V4_GATE_SPEC — Phase 25: gate, atomic commit, certificate, replay (element E)

2026-10-26 authorized prospective integrity amendment: `CertifiedGate(..., bind_inputs=True)`
emits `sentinel-cert-v2` for dispatch, hold, override and migration. Its `inputs_digest` is SHA-256
of canonical JSON of the complete stored `CertificateInputs.to_dict()`, with the final certificate
id, ordered candidate edges, departure/start times, world and horizon. The certificate hash covers
this digest. Replay checks it before constructing futures and rebuilds the same v2 document.
Actuator authorization requires v2 and matching inputs. The default `bind_inputs=False` retains
v1 bytes and simulation/replay behavior for frozen historical generators; v1 documents remain
readable and replayable but cannot authorize future actuation. Parameters, sampling and root keys
are unchanged. This digest detects input corruption; it is not an external digital signature.

Lane S (Builder S) · branch `m25-gate` · depends on 21–24 (merged) · tests `tests/test_p25_gate.py`
Confidential: core patent element. Contract: `specs/contracts/certificate.schema.json` (v1, unchanged
except the optional `edge_set_digest`, added 2026-10-15).

## Goal
Turn a `CertificationResult` into an **actuation gate**: the chosen dispatch is committed to the
capacity ledger *together with* a hash-chained certificate in one transaction (or nothing is), and only
then are vehicle / shelter-admission commands emitted, each naming the certificate. Any third party can
regenerate the decision bit-for-bit from the certificate plus its stored inputs (`replay`).

## Files (all Lane S)
- `src/certify/certificate.py` (new) — canonical JSON, hashing, build, validate, chain check.
- `src/certify/ledger.py` (new) — `Ledger` protocol, `SqliteLedger` (stdlib `sqlite3`), `SimLedgerAdapter`.
- `src/certify/gate.py` (new) — `CertifiedGate`, `canonical_edge_union`, `ledger_view_hash`.
- `src/certify/replay.py` (new) + `scripts/replay_certificate.py` (CLI wrapper) + `scripts/phase25_replay_batch.py`.
- `src/actuation/__init__.py`, `src/actuation/commands.py` (new).
- `src/certify/params.py` — register `v4-cert-test-v1` (below). `src/certify/certifier.py` — add keyword
  `stop_after_looks: int | None = None` (replay only; default keeps behaviour). `src/certify/rollout.py` —
  `Candidate` gains `start_minutes: float | None = None` (Phase 26 uses it; default keeps behaviour).
- `src/safety/masks.py` — `_apply_certifier` takes threshold / config version from the certificate
  mapping (`CandidateCertificate` gains nothing; the certifier callable may return an object with
  `threshold` and `params_id` attributes; fall back to 0.95 / "v4-cert-v1" when absent).
- `src/sim/stochastic.py` — public read-only `transit_plans() -> Mapping[str, TransitPlan]` (v4 only, `{}` otherwise).
- `src/simulation_session.py` — certified mode (below). Legacy constructor behaviour unchanged.
- `tests/test_s_p25_*.py` (your unit tests), `data/eval_results/phase25/` (new).

## Canonical JSON and hashes (shared rule — Lane X's actuator implements the same)
```python
def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")
def certificate_hash(cert: Mapping) -> str      # sha256(canonical_json(cert without "cert_hash")).hexdigest()
```
This matches the `hash_rule` of `certificates_fixture.json` (all five fixture hashes verify).
Floats written into a certificate are rounded first: `lower`, `upper` to 12 decimals, `mean_utility`
to 9, so replay on another OS / SciPy build compares equal.

## Interfaces
```python
# certificate.py
CERT_VERSION = "sentinel-cert-v1"
def build_certificate(*, cert_id: str, kind: str, incident_id: str, scenario_id: str, timestep: int,
                      root: str, forecast_hash: str, graph_fingerprint: str, ledger_hash: str,
                      params: CertParams, a_max: int, result: CertificationResult | None,
                      candidates: Sequence[Candidate], chosen_key: str, chosen_people: int,
                      group_id: str | None, operator: Mapping[str, str],
                      commands: Sequence[Mapping[str, str]], prev_cert_hash: str | None,
                      edge_set_digest: str) -> dict          # cert_hash filled in last
def validate_certificate(cert: Mapping) -> None   # jsonschema (contract) + hash; raises CertificateError
def verify_chain(certs: Sequence[Mapping]) -> int | None    # index of first broken link, None if intact

@dataclass(frozen=True)
class CertificateInputs:          # stored next to every certificate; everything replay needs
    cert_id: str; world_id: str; params_id: str; horizon_steps: int
    forecast: ForecastSnapshot; ledger: LedgerView
    candidates: tuple[Candidate, ...]; edge_ids: tuple[str, ...]
    def to_dict(self) -> dict; @classmethod def from_dict(cls, d) -> "CertificateInputs"

# ledger.py
class LedgerConflict(RuntimeError): ...
class LedgerTx(Protocol):
    def reserve(self, shelter_id: str, people: int, cert_id: str) -> None   # LedgerConflict if over capacity
    def release(self, shelter_id: str, people: int, cert_id: str) -> None
    def append_certificate(self, cert: Mapping, inputs: CertificateInputs) -> None
class Ledger(Protocol):
    def view(self) -> LedgerView
    def transaction(self) -> ContextManager[LedgerTx]     # all-or-nothing
    def certificates(self) -> list[dict]
    def inputs(self, cert_id: str) -> CertificateInputs
    def next_cert_id(self, prefix: str = "CERT") -> str   # CERT-000001, CERT-000002, ...
class SqliteLedger:
    def __init__(self, path: str | Path = ":memory:", *, shelters: Mapping[str, tuple[int, int]] = {},
                 fail_hook: Callable[[str], None] | None = None): ...   # shelter -> (capacity, occupancy)
    def view(self, timestep: int = 0) -> LedgerView     # pending = committed reservations as
                                                        # (cert_id, shelter, people, -1); sigma/age 0.0
class SimLedgerAdapter:            # wraps a v4 StochasticSimulator; certificates kept in memory
    def __init__(self, simulator: StochasticSimulator): ...

# gate.py
def canonical_edge_union(graph, road_state, scenario) -> tuple[str, ...]   # moved from the G23 pilot
def ledger_view_hash(view: LedgerView) -> str                             # sha256(canonical_json(view))
@dataclass(frozen=True)
class GateDecision:
    action: SimulationAction; certificate: dict; commands: tuple[Command, ...]; escalate: bool
class GateError(ValueError): ...
class CertifiedGate:
    def __init__(self, scenario, graph, world, params: CertParams, ledger: Ledger, *,
                 sink: CommandSink | None = None, clock=time.perf_counter,
                 futures_factory: Callable[..., Any] | None = None,   # tests inject fakes
                 rollout: Callable = rollout_joint): ...
    def evaluate(self, state, road_state, snapshot: SafetySnapshot) -> tuple[CertificationResult, CertificateInputs]
    def commit(self, result, inputs, *, operator: Mapping[str, str], selected_key: str | None = None,
               group_id: str | None = None) -> GateDecision

# replay.py
@dataclass(frozen=True)
class ReplayReport: result: str; mismatched_fields: tuple[str, ...]     # "MATCH" | "MISMATCH"
def replay_certificate(cert: Mapping, inputs: CertificateInputs, *, graph: RoadGraph,
                       futures_factory=None, rollout=rollout_joint) -> ReplayReport

# actuation/commands.py
@dataclass(frozen=True) class VehicleCommand: cert_id; cert_hash; group_id; zone_id; shelter_id; people; edge_ids
@dataclass(frozen=True) class AdmissionCommand: cert_id; cert_hash; shelter_id; people; group_id
Command = VehicleCommand | AdmissionCommand
class CommandSink(Protocol): def send(self, command: Command) -> None
class InMemorySink: sent: list[Command]
def authorize(command: Command, ledger: Ledger) -> bool
    # True iff the cert exists, validates, has kind DISPATCH/MIGRATION/OVERRIDE, its cert_hash equals
    # command.cert_hash, and chosen action_key / people match the command
```

## Pseudocode
```text
evaluate(state, road_state, snapshot):
    view   = ledger.view()                          # SimLedgerAdapter: ledger_view_from_state(state, plans)
    fc     = forecast_from_state(state, road_state, scenario)
    edges  = canonical_edge_union(graph, road_state, scenario)      # ALL canonical dispatches (A_MAX)
    root   = root_key(incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
                      graph_fingerprint=graph.graph_fingerprint, ledger_hash=ledger_view_hash(view),
                      params_id=params.params_id, backend=params.backend)
    H      = min(world.horizon_steps - t, ceil((boarding + 1.5 * max nominal path time) / dt) + 1)
    cands  = [Candidate(z, s, people, path.edge_ids, t) for each mask-allowed DispatchAction in snapshot]
    fs     = futures_factory(fc, graph, world, root, H, edge_ids=edges)  # default FutureSet
    result = certify(cands, fs, view, world, params, graph, clock=clock, rollout=rollout)
    return result, CertificateInputs(..., ledger=view, candidates=cands, edge_ids=edges)

commit(result, inputs, operator, selected_key=None):
    key = selected_key or result.chosen_key
    if key != HOLD_KEY and key not in result.allowed_keys(): raise GateError   # only certified actions
    kind = HOLD if key == HOLD_KEY else (OVERRIDE if operator["decision"] == "OVERRIDE" else DISPATCH)
    with ledger.transaction() as tx:                 # one transaction: reserve + certificate, or nothing
        if kind != HOLD: tx.reserve(shelter, people, cert_id)
        cert = build_certificate(..., prev_cert_hash = last cert_hash or None)
        tx.append_certificate(cert, inputs)
    commands = (VehicleCommand, AdmissionCommand) if kind != HOLD else ()     # only after commit
    for c in commands: sink.send(c)
    escalate = (key == HOLD_KEY and not result.allowed_keys() - {HOLD_KEY})   # empty certified set
```
`SimLedgerAdapter.transaction()` buffers the certificate and, on exit without error, calls
`simulator.step(DispatchAction|WAIT)` and then appends the certificate; an exception anywhere discards
both (the simulator is not stepped). `SqliteLedger.reserve` checks `occupancy + reserved + people <=
capacity` inside `BEGIN IMMEDIATE`; `fail_hook(stage)` is called at `"after_reserve"` and
`"after_certificate"` (before `COMMIT`) so tests can inject crashes.

## Replay
1. `certificate_hash(cert) != cert["cert_hash"]` is recorded but not yet reported.
2. Recompute `forecast_hash`, `ledger_hash` (= `ledger_view_hash(inputs.ledger)`), `graph_fingerprint`
   (graph loaded by the caller), `edge_set_digest`, `root_key` from the inputs.
3. Re-run `certify` with a clock that never advances and `stop_after_looks=cert["looks"]` (α still uses
   the recorded `max_looks` / `a_max`), then `build_certificate` with the recorded `cert_id`, `kind`,
   `operator`, `commands`, `prev_cert_hash`, `chosen`.
4. Compare field by field; nested paths are reported as `candidates[2].lower`, `params.delta`,
   `chosen.people`. Any difference → `MISMATCH` with every differing path. If all fields match but the
   stored hash does not, report `("cert_hash",)`. Otherwise `MATCH`.
`deadline_hit` is compared as stored (replay copies it; a deadline only changes `looks`, which is replayed).

## Certified mode in `SimulationSession`
`SimulationSession(seed, regime="v4-medium-dt2-v1", *, certified=True, params_id="v4-cert-v1")`:
`build_v4_runtime`; `SimLedgerAdapter`; `context()` uses `evaluate_actions(..., certifier=...)` backed by
`gate.evaluate` (computed once per prepared timestep, cached) and `CertifiedPlanner`; `decide()` maps
ACCEPT / OVERRIDE / REJECT to `gate.commit` (REJECT → HOLD certificate with operator decision REJECT)
after the existing human-decision validation; new `certificates() -> list[dict]`. `certified=False`
(default) is today's behaviour, bit-identical.

## Params
`v4-cert-test-v1 = CertParams(params_id="v4-cert-test-v1", eps_dispatch=0.30, eps_keep=0.40, k0=32,
max_looks=2, deadline_ms=600_000.0)` — CI speed only; never used for results.

## Edge cases
Empty candidate set → HOLD certificate with `escalate=True`, `candidates=[]`. First certificate
`prev_cert_hash = null`. Graph fingerprint mismatch in replay → `MISMATCH ("graph_fingerprint",)`.
`next_cert_id` never reuses an id after a rolled-back transaction (ids are allocated inside it).

## Acceptance (tests/test_p25_gate.py)
Canonical hash reproduces all fixture hashes; built certificates validate against the contract; HOLD
when nothing is certified and `escalate`; uncertified `selected_key` → `GateError`; crash at either
`fail_hook` stage leaves no reservation and no certificate; capacity conflict raises `LedgerConflict`;
chain intact after three commits and `verify_chain` finds a tampered link; replay MATCH on 20 fake-future
decisions; tampering each top-level field and `candidates[0].lower` → MISMATCH naming that path;
`authorize` accepts the committed command and rejects unknown id / wrong hash / wrong shelter; one
end-to-end decision on the real v4 runtime with `v4-cert-test-v1` commits and replays MATCH; legacy
`SimulationSession()` unchanged. Batch: `scripts/phase25_replay_batch.py --n 1000 --workers 16`
(`v4-cert-test-v1`, random seeds from 1_060_000) writes `data/eval_results/phase25/replay_batch.json`
(`match_rate` must be 1.0) — record the number in STATUS.

## Runner may
H1 runs; H2 locate `evaluate_actions` / `SimulationSession` callers; H4 fixture certificates.

## Out of scope
In-transit re-certification and migration (26), HIL transport (28), API wiring (34A), Postgres.
