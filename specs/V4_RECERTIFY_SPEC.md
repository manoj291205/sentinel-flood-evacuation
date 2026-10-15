# V4_RECERTIFY_SPEC — Phase 26: in-transit re-certification + atomic migration

Lane S (Builder S) · branch `m26-recertify` (from `m25-gate`) · tests `tests/test_p26_recertify.py`
Confidential: dependent claims 8, 9, 16; **fallback lead claim** if D-27 rejects joint-vs-marginal
(G23 was weak — build this to full quality).

## Goal
On every new prepared observation, re-certify each in-transit group's **remaining** trip with the looser
keep threshold `1 - eps_keep` (hysteresis). Only a *certified failure* (verdict INFEASIBLE) triggers a
migration: certify alternatives from the group's next node at `1 - eps_dispatch`, then release the old
reservation and acquire the new one in **one** ledger transaction with a `MIGRATION` certificate, and emit
a reroute command. Mask changes are sent as compact deltas.

## Files (Lane S)
`src/certify/recertify.py`, `src/certify/mask_delta.py` (new); `src/sim/transit.py` (`group_position`,
`reroute_plan`); `src/sim/stochastic.py` (`migrate(...)`, v4 only); `src/sim/events.py`
(`AuditEventType.GROUP_MIGRATED`, `MIGRATION_NO_CERTIFIED_ALTERNATIVE` — add members only);
`src/certify/gate.py` (`CertifiedGate.recertify`); `src/actuation/commands.py` (`RerouteCommand`);
`scripts/phase26_flipflop.py`; `data/eval_results/phase26/`; `tests/test_s_p26_*.py`.

## Interfaces
```python
# transit.py
@dataclass(frozen=True)
class GroupPosition: event_id: str; node_id: str; at_minutes: float; remaining_edge_ids: tuple[str, ...]
def group_position(plan: TransitPlan, graph, now_minutes: float) -> GroupPosition
    # current edge = last edge with entry <= now; node = its end node; at_minutes = next edge's entry
    # (or arrival). Before the first entry (boarding): node = origin node, at_minutes = first entry.
def reroute_plan(plan, position, new_shelter_id, new_edge_ids, road_state, graph, world, config,
                 streams, timestep) -> TransitPlan
    # same event_id/zone/people; departure_timestep = timestep; entries start at position.at_minutes;
    # travel noise keyed (timestep, zone_id, new_shelter_id, edge_id); no boarding time.

# recertify.py
@dataclass(frozen=True)
class RecertDecision:
    event_id: str; keep_verdict: Verdict; keep_lower: float; keep_upper: float
    action: str            # "KEEP" | "MIGRATE" | "KEEP_ESCALATE" | "COOLDOWN"
    new_shelter_id: str | None; certificate: dict | None
@dataclass(frozen=True)
class RecertPolicy: cooldown_steps: int = 3; max_migrations: int = 2
def keep_candidate(plan, position, graph) -> Candidate        # remaining edges, start_minutes = at_minutes
def migration_candidates(plan, position, graph, road_state, scenario) -> tuple[Candidate, ...]
    # shortest_valid_path(position.node -> each shelter node) except the current shelter and every shelter
    # this group already left; departure_timestep = t, start_minutes = position.at_minutes
@dataclass(frozen=True)
class GroupHistory: migrations: int = 0; last_migration_step: int | None = None; left_shelters: frozenset[str] = frozenset()
def recertify_group(event_id: str, keep: Candidate, alternatives: Sequence[Candidate], futures, ledger: LedgerView,
                    world, params: CertParams, graph, *, timestep: int, history: GroupHistory,
                    policy: RecertPolicy = RecertPolicy(), rollout=rollout_joint) -> RecertDecision
    # pure core (no ledger writes): cooldown/max check first (no certify call), keep certify at eps_keep,
    # alternatives whose shelter is in history.left_shelters or == keep.shelter_id are dropped,
    # alternatives certified at eps_dispatch; certificate=None (the gate builds it on commit)
def recertify_in_transit(gate: CertifiedGate, state, road_state, plans, histories, policy) -> tuple[RecertDecision, ...]

# mask_delta.py
def encode_mask_delta(prev: Mapping[str, bool], new: Mapping[str, bool], *, epoch: int) -> bytes
def decode_mask_delta(prev: Mapping[str, bool], payload: bytes) -> dict[str, bool]
```
`Candidate.start_minutes` (added in Phase 25) replaces `departure_timestep * dt + boarding_minutes` in
`rollout_joint` when set. The keep candidate's capacity term must **not** count the group's own
reservation: its `LedgerView` is the current view with that event removed from `pending`.

## Pseudocode
```text
for event in in-transit events, in event_id order:          # deterministic
    if migrations[event] >= max_migrations or t - last_migration[event] < cooldown: COOLDOWN; continue
    pos  = group_position(plans[event], graph, t * dt)
    keep = certify([keep_candidate], futures, view_without(event), world,
                   replace(params, eps_dispatch=params.eps_keep), graph)
    if keep verdict != INFEASIBLE: KEEP; continue             # UNDECIDED keeps (only certified failure moves)
    alts = certify(migration_candidates(...), futures, view_without(event), world, params, graph)
    if no FEASIBLE alt: KEEP_ESCALATE (audit MIGRATION_NO_CERTIFIED_ALTERNATIVE); continue
    best = paired_argmax(FEASIBLE alts)
    with ledger.transaction() as tx:                          # no gap, no double hold
        tx.release(old_shelter, people, cert_id); tx.reserve(best.shelter, people, cert_id)
        tx.append_certificate(MIGRATION cert (operator decision "AUTO"), inputs)
    simulator.migrate(event, best.shelter, best.edge_ids)      # SimLedgerAdapter does this inside commit
    sink.send(RerouteCommand(cert_id, cert_hash, group_id=event, shelter_id, edge_ids))
```
One `FutureSet` per prepared timestep is shared by dispatch certification and every re-certification
(same root, CRN). The edge union for it must also include every in-transit group's remaining edges and
every migration path (still independent of which candidates are evaluated).

## Mask delta format (little-endian)
`b"SMD1"` · `uint32 epoch` · `uint16 count` · `count × (uint16 index, uint8 allowed)`; indices refer to
`sorted(prev.keys() | new.keys())`. An unchanged mask is exactly 10 bytes. A key missing from `new` is
encoded as `allowed = 0`. Decoding with a wrong-length payload raises `ValueError`.

## Edge cases
Group already on its last edge → no migration candidates → KEEP_ESCALATE only if keep is INFEASIBLE.
Migration target = shelter left earlier → excluded (no A→B→A). Arrival this step → not re-certified.
Legacy and non-certified v4 runs: nothing changes (`migrate` is only called by the gate).

## Acceptance (tests/test_p26_recertify.py)
`group_position` on a hand-made plan (boarding, mid-edge, last edge); keep threshold looser than dispatch
(a candidate with true p = 0.92 is kept but not dispatched, fake futures); INFEASIBLE keep + FEASIBLE
alternative → one MIGRATION certificate, old reservation released and new one held in the same
transaction (crash hook → neither); no FEASIBLE alternative → KEEP_ESCALATE; cooldown and max-migration
limits; never returns to a shelter it left; **burst-closure concurrency**: 8 threads migrating into one
`SqliteLedger` shelter with room for 3 groups (`SqliteLedger` must be thread-safe: one connection, `check_same_thread=False`, a lock around each transaction, `BEGIN IMMEDIATE`) → exactly 3 succeed, reservations never exceed capacity;
mask delta round-trip, unchanged mask = 10 bytes. `scripts/phase26_flipflop.py` (1,000 seeds, fake
futures with random per-step closures) writes `data/eval_results/phase26/flipflop.json`
(`returns_to_left_shelter` must be 0, `max_migrations_observed <= 2`).

## Runner may
H1 runs, H4 hand-made `TransitPlan` fixtures.

## Out of scope
Intermediate recourse rules beyond shortest valid path, radio transport of deltas (28 sends them only
as MQTT payload sizes), API wiring (34A).
