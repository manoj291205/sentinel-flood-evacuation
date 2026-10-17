# V4_ESCROW_LITE_SPEC — Phase 35-lite: seat escrow during a simulated network outage

Lane X · branch `lane-x/m35-escrow-lite` (from your pushed `lane-x/m34c-live-session`, after X34C.7; before 36) ·
acceptance `tests/test_p35l_escrow_lite.py` (milestone `P35L`), web `specs/acceptance/web/p35l_network.spec.ts` (copy
unchanged) · contracts `escrow_status.schema.json`, `phase35lite_result.schema.json`, `claims_policy.json`.
**Exploratory**, added 2026-10-17 at the user's request: not part of the pre-registered evaluation (D-27 stands), Phase 35 in
full stays DROPPED, and nothing here may be described as an outcome improvement — the console, result file, demo script and
course pack report only counts of outages, conflicts and held dispatches. Confidential like every gate page.

## 1. Goal and the honest definition of "overbooking"
Two field teams split the zones. If the network between them is cut, each team keeps certifying dispatches from what it last
knew. **Without escrow** both teams believe every seat that was free at the cut is still theirs to book, so their offline
bookings can collide. **With escrow**, the free seats at the cut are split into per-team shares first, and each team's gate
certifies only against its own share. The simulator itself never overfills a shelter (it shrinks a group to the seats really
free), so a collision is measured where it would happen in practice — at reconciliation:
`overbooked_seats[s] = max(0, Σ_teams reserved_offline[s] − free_at_cut[s])`, summed over shelters; an outage "overbooks" if
that sum is > 0. Walk-ins and arrivals are not counted here (they are the simulator's own OVERFLOW outcome).

## 2. Files (Lane X; LANES.md updated)
New: `src/escrow/__init__.py`, `src/escrow/shares.py`, `src/escrow/ledger.py`, `src/escrow/outage.py`, `src/escrow/session.py`,
`scripts/phase35lite_outages.py`, `data/eval_results/phase35lite/outages.json`, `tests/test_lx_p35*.py`; `src/api/**` (escrow
endpoints), `web/**`. **Never edit `src/certify/**` or any Lane S file**: Lane S code is imported read-only —
`build_v4_runtime`, `load_road_graph`, `CertifiedGate`, `SimLedgerAdapter`, `LedgerConflict`, `LedgerView`,
`ledger_view_from_state`, `forecast_from_state`, `evaluate_actions`, `get_cert_params`, `replay_certificate`,
`CertificateInputs`, `validate_certificate`. Modified copies of Lane S dataclasses (`dataclasses.replace`) are allowed.

## 3. Components and signatures
- `TEAMS = ("TEAM-A", "TEAM-B")`; `team_zones(scenario) -> dict[str, tuple[str, ...]]`: zone ids sorted; TEAM-A gets the first
  `ceil(n/2)`, TEAM-B the rest.
- `split_shares(free: Mapping[str, int], weights: Mapping[str, float]) -> dict[str, dict[str, int]]`: per shelter `s` and team `t`,
  `share[t][s] = floor(free[s] * w_t / Σw)` (all weights 0 → equal weights); every share ≥ 0, `Σ_t share[t][s] ≤ free[s]`;
  the remainder stays in the pool. **Forecast weights:** `w_t = Σ_{z in team} population_remaining(z) * (1 + severity(z))`
  with `severity` from `forecast_from_state(state_at_cut, road_state, scenario).zone_severity`.
- `EscrowLedgerAdapter(base: SimLedgerAdapter, team, *, cut_view: LedgerView, seats: Mapping[str, int])` — the `Ledger`
  protocol for one team while offline. `view()` = `cut_view` with `capacity_total[s] = occupancy[s] + reserved[s] + left[s]`
  where `left[s]` = seats − this team's offline reservations at `s` (so the gate sees exactly the team's seats as free).
  `transaction()` records the reservation and the certificate in the team's **local outage log** (no simulator step);
  reserving more than `left[s]` raises `LedgerConflict`. `certificates()`, `inputs(cert_id)` and `next_cert_id()` cover the
  local log (ids keep the `CERT-NNNNNN` form and never collide: TEAM-A numbers from the last base id + 1, TEAM-B from the last base
  id + 501; each team's offline certificates form their own hash chain starting from the last base certificate; group ids
  `offline-<team>-NNNN`). `seats` = the share (escrow) or the whole `free_at_cut` (without escrow).
- `believed_state(state_at_cut, left) -> EpisodeState`: copy whose shelters have `capacity_reserved = capacity_total −
  occupancy_current − left[s]`, so `validate_action` sizes groups to what the team believes is free.
- `simulate_outage(seed, world_id, cut_step, rounds, mode, *, params_id="v4-cert-test-v1", futures_factory=None, rollout=None,
  graph=None) -> OutageReport` (`src/escrow/outage.py`), `mode` ∈ {`escrow`, `last_known`}:
  ```text
  runtime = build_v4_runtime(world_id, generator_seed=seed); gate0 = CertifiedGate(..., SimLedgerAdapter(sim))
  advance to cut_step: each step observe -> gate0.evaluate -> gate0.commit(ACCEPT, actor "online")   # one shared team online
  cut: state_c, view_c = prepared state, ledger view; free_at_cut[s] = view_c capacity − occupancy − reserved
  seats = split_shares(free_at_cut, weights) if mode == "escrow" else {t: free_at_cut for t in TEAMS}
  for r in range(rounds): for team in TEAMS:                                   # world frozen while offline
      ledger_t = EscrowLedgerAdapter(..., seats[team]); gate_t = CertifiedGate(..., ledger_t, futures/rollout as given)
      st = believed_state(state_c, ledger_t.left); snap = only team-zone dispatches of evaluate_actions(scenario, st)
      result, inputs = gate_t.evaluate(st, road_state, snap); decision = gate_t.commit(result, inputs, operator AUTO/team)
      if mode == "escrow": desired = the choice a last-known gate would make (same inputs, seats = free_at_cut);
          if desired dispatch needs more seats than left: blocked row {team, round, action_key, people, seats_left,
          reason "needs {p} seats; {team} has {l} left at {S}", suggested: decision's key (or "HOLD")}
  restore: reserved_offline = Σ local reservations; overbooked_seats per §1; returned = Σ_t (seats_t − used_t) back to pool
           (escrow); then execute every offline DISPATCH in commit order with `sim.step(DispatchAction)` and record
           `executed_people` vs `certified_people` per dispatch (truncation shows a collision physically).
  ```
  `OutageReport` fields (all ints except where named): `seed, world_id, cut_step, rounds, mode, free_at_cut{s}, seats{team{s}},
  reserved_offline{s}, reserved_by_team{team{s}}, overbooked_seats, overbooked (bool), blocked[...], returned_to_pool, executed[...],
  certificates[{certificate, inputs (CertificateInputs.to_dict())}]` (the offline certificates, in commit order).
- `EscrowSession` (`src/escrow/session.py`) for the console: `start(seed, world_id, mode)`, `step()` (ONLINE: one shared
  certified decision, ACCEPT; OFFLINE: one round, both teams), `cut()`, `restore()`, `status()`.

## 4. Study and evidence
`python scripts/phase35lite_outages.py` (real futures, `v4-cert-test-v1`): seeds 1_070_000–1_070_039, world `v4-medium-dt2-v1`,
`cut_step = 2 + (seed % 5)`, `rounds = 2`, both modes per seed → `data/eval_results/phase35lite/outages.json`
(`phase35lite_result.schema.json`): `exploratory: true`, `not_preregistered: true`, the config, one row per (seed, mode) with
the report's counts, and totals `outages` (= distinct seeds, 40: each outage is run once per mode), `overbooked_outages_escrow`, `overbooked_outages_last_known`,
`overbooked_seats_escrow`, `overbooked_seats_last_known`, `blocked_escrow`. Run once, commit the file, never hand-edit it.
Manifest items (already added): `p35lite-outages`, `p35lite-overbooked-escrow`, `p35lite-overbooked-last-known` — group
"Exploratory: network outage (not pre-registered)".

## 5. API (`src/api/**`) — `escrow_status.schema.json`
`POST /api/escrow/sessions {seed, regime (three v4 worlds), mode: "escrow"|"last_known"}` → status; `POST …/{id}/step`,
`…/{id}/cut`, `…/{id}/restore` → status; `GET …/{id}` → status. Status: `network` ONLINE|OFFLINE, `label` (exactly
`"Simulated network outage"` while OFFLINE, else null), `mode`, `timestep`, `teams[{team, zones, seats_total, seats_left}]`
(OFFLINE; empty ONLINE), `blocked`, `last_reconciliation` (`{overbooked_seats, returned_to_pool, executed}` after a restore),
`certificates` (newest first, ids), `note` = `"Exploratory: not part of the pre-registered evaluation."`. Cutting while
OFFLINE or restoring while ONLINE → 409. Endpoints are `def` (threadpool) with a per-session lock; max 4 escrow sessions (LRU).

## 6. Web
Live session mode gets a checkbox `Two-team network demo`; with it, Start creates an escrow session and shows a **Network**
panel (`aria-label="Network"`): status word ONLINE/OFFLINE with shape, buttons `Cut network` / `Restore network`, a radiogroup
`Escrow` (`With escrow` / `Without escrow`, chosen before Start; changing it starts a new session), per-team lines
`TEAM-A: x of y seats left`, held dispatches with their reason and suggestion, and after a restore `Rebalanced: n seats back to
the pool · overbooked seats: m`. The live session's `Step on` button advances the escrow session (ONLINE: one shared
certified decision; OFFLINE: one round for both teams) with the `Certifying…` status while it runs. While OFFLINE a banner `Simulated network outage` is shown. Evidence & Results shows the three
manifest items in their group with the note "Exploratory — not pre-registered". No other number, no banned wording.

## 7. Acceptance and scope
`tests/test_p35l_escrow_lite.py`: shares never exceed free seats (many random cases); the adapter's view equals the team's
seats and refuses an over-share reservation; **safety: with escrow no outage overbooks**, over 60 seeded random outages (fast
fake futures); rebalance conserves seats; the last-known mode overbooks in at least one of those outages; blocked rows carry a
reason and suggestion; offline certificates validate and replay MATCH; API status flow and schema; result file valid and
consistent; honest labels. Out of scope: more than two teams, partial partitions, re-checks of groups while offline, any
change to Lane S code, any claim about evacuation outcomes.

## Amendments
- 2026-10-17 (Lead, Wave C review): repeated outages in one console session. `restore()` reconciles and executes only the
  offline dispatches of the outage being restored (it re-ran earlier outages' dispatches). Offline ids now start above every id
  issued so far in the engine, online or offline: TEAM-A at that maximum + 1001, TEAM-B at + 1501 (the old + 1 / + 501 reused ids
  after a restore, because the online ledger continues at its own last id + 1). `EscrowLedgerAdapter` gains an optional
  `first_number`. Ids do not enter the futures root or any count, so the committed study file is unaffected.
