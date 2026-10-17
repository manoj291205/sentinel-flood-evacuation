"""Exploratory two-team outage simulation over the existing certified gate."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.certify.gate import CertifiedGate
from src.certify.ledger import SimLedgerAdapter
from src.certify.params import get_cert_params
from src.geospatial.v4_runtime import build_v4_runtime
from src.safety import evaluate_actions
from src.sim import DispatchAction

from .ledger import EscrowLedgerAdapter, believed_state
from .shares import TEAMS, forecast_weights, split_shares, team_zones


@dataclass
class OutageReport:
    seed: int
    world_id: str
    cut_step: int
    rounds: int
    mode: str
    free_at_cut: dict[str, int]
    seats: dict[str, dict[str, int]]
    reserved_offline: dict[str, int]
    reserved_by_team: dict[str, dict[str, int]]
    overbooked_seats: int
    overbooked: bool
    blocked: list[dict]
    returned_to_pool: int
    executed: list[dict]
    certificates: list[dict]


def _team_snapshot(scenario, state, zones):
    snapshot = evaluate_actions(scenario, state)
    keep = [index for index, action in enumerate(snapshot.canonical_actions)
            if not isinstance(action, DispatchAction) or action.zone_id in zones]
    return replace(snapshot, canonical_actions=tuple(snapshot.canonical_actions[i] for i in keep),
                   allowed_mask=tuple(snapshot.allowed_mask[i] for i in keep),
                   evaluations=tuple(snapshot.evaluations[i] for i in keep))


class OutageEngine:
    def __init__(self, seed, world_id, mode, *, params_id="v4-cert-test-v1",
                 futures_factory=None, rollout=None, graph=None) -> None:
        if mode not in {"escrow", "last_known"}:
            raise ValueError("mode must be escrow or last_known")
        self.seed, self.world_id, self.mode = seed, world_id, mode
        self.scenario, self.sim, self.graph, self.overlay, self.world = build_v4_runtime(
            world_id, generator_seed=seed, graph=graph)
        self.base = SimLedgerAdapter(self.sim)
        options = {"world_id": world_id}
        if futures_factory is not None:
            options["futures_factory"] = futures_factory
        if rollout is not None:
            options["rollout"] = rollout
        self.gate_options = options
        self.params = get_cert_params(params_id)
        self.online_gate = CertifiedGate(self.scenario, self.graph, self.world, self.params,
                                         self.base, **options)
        self.zones = team_zones(self.scenario)
        self.network = "ONLINE"
        self.rounds = 0
        self.blocked: list[dict] = []
        self.certificates: list[dict] = []
        self.last_reconciliation = None
        self._outage_start = 0

    def online_step(self) -> None:
        if self.sim.state.terminal:
            return
        self.sim.observe()
        state = self.sim.prepared_state_for_debug()
        result, inputs = self.online_gate.evaluate(state, self.overlay.road_state,
                                                    evaluate_actions(self.scenario, state))
        self.online_gate.commit(result, inputs, operator={"decision": "ACCEPT", "actor": "online", "reason": ""})

    def cut(self) -> None:
        if self.network != "ONLINE":
            raise ValueError("network is already offline")
        self.sim.observe()
        self.state_at_cut = self.sim.prepared_state_for_debug()
        self.cut_step = self.state_at_cut.current_timestep
        self.cut_view = self.base.view()
        self.free_at_cut = {s: max(0, self.cut_view.capacity_total[s] - self.cut_view.occupancy[s]
                                    - self.cut_view.reserved[s]) for s in self.cut_view.capacity_total}
        self.seats = (split_shares(self.free_at_cut, forecast_weights(
            self.scenario, self.state_at_cut, self.overlay.road_state)) if self.mode == "escrow"
                      else {team: dict(self.free_at_cut) for team in TEAMS})
        # Offline ids sit above every id issued so far (online or offline) with room for the online steps
        # that follow a restore, so repeated outages in one console session never reuse an id.
        self._outage_start = len(self.certificates)
        issued = [*self.base.certificates(), *(item["certificate"] for item in self.certificates)]
        floor = max((int(cert["cert_id"].split("-")[1]) for cert in issued), default=0)
        first = {TEAMS[0]: floor + 1001, TEAMS[1]: floor + 1501}
        self.adapters = {team: EscrowLedgerAdapter(self.base, team, cut_view=self.cut_view,
                                                  seats=self.seats[team], first_number=first[team])
                         for team in TEAMS}
        self.gates = {team: CertifiedGate(self.scenario, self.graph, self.world, self.params,
                                         self.adapters[team], **self.gate_options) for team in TEAMS}
        if self.mode == "escrow":
            self.shadow_adapters = {team: EscrowLedgerAdapter(self.base, team, cut_view=self.cut_view,
                                                              seats=self.free_at_cut) for team in TEAMS}
            self.shadow_gates = {team: CertifiedGate(self.scenario, self.graph, self.world, self.params,
                                                    self.shadow_adapters[team], **self.gate_options)
                                 for team in TEAMS}
        self.network = "OFFLINE"

    def offline_step(self) -> None:
        if self.network != "OFFLINE":
            raise ValueError("network is online")
        for team in TEAMS:
            adapter, gate = self.adapters[team], self.gates[team]
            state = believed_state(self.state_at_cut, adapter.left)
            snapshot = _team_snapshot(self.scenario, state, self.zones[team])
            result, inputs = gate.evaluate(state, self.overlay.road_state, snapshot)
            desired_key = None
            if self.mode == "escrow":
                shadow, shadow_gate = self.shadow_adapters[team], self.shadow_gates[team]
                shadow_state = believed_state(self.state_at_cut, shadow.left)
                shadow_result, shadow_inputs = shadow_gate.evaluate(
                    shadow_state, self.overlay.road_state,
                    _team_snapshot(self.scenario, shadow_state, self.zones[team]))
                desired_key = shadow_result.chosen_key
                if desired_key != "WAIT":
                    desired = next(c for c in shadow_inputs.candidates if c.action_key == desired_key)
                    left = adapter.left[desired.shelter_id]
                    if desired.people > left:
                        self.blocked.append({
                            "team": team, "round": self.rounds, "action_key": desired_key,
                            "people": desired.people, "seats_left": left,
                            "reason": (f"needs {desired.people} seats; {team} has {left} left "
                                       f"at {desired.shelter_id}"),
                            "suggested": result.chosen_key,
                        })
                shadow_gate.commit(shadow_result, shadow_inputs,
                                   operator={"decision": "AUTO", "actor": team, "reason": "last-known comparison"})
            decision = gate.commit(result, inputs, operator={
                "decision": "AUTO", "actor": team, "reason": "simulated network outage"})
            self.certificates.append({"certificate": decision.certificate,
                                      "inputs": adapter.inputs(decision.certificate["cert_id"]).to_dict()})
        self.rounds += 1

    def restore(self) -> None:
        if self.network != "OFFLINE":
            raise ValueError("network is online")
        self.reserved_by_team = {team: self.adapters[team].reserved for team in TEAMS}
        self.reserved_offline = {s: sum(self.reserved_by_team[t].get(s, 0) for t in TEAMS)
                                 for s in self.free_at_cut}
        self.overbooked_seats = sum(max(0, self.reserved_offline[s] - free)
                                    for s, free in self.free_at_cut.items())
        self.returned_to_pool = (sum(sum(seats.values()) for seats in self.seats.values())
                                 - sum(self.reserved_offline.values()) if self.mode == "escrow" else 0)
        self.executed = []
        for item in self.certificates[self._outage_start:]:
            cert = item["certificate"]
            key = cert["chosen"]["action_key"]
            if key == "WAIT":
                continue
            zone, shelter = key.split("->", 1)
            transition = self.sim.step(DispatchAction(zone, shelter))
            self.executed.append({
                "cert_id": cert["cert_id"], "action_key": key,
                "certified_people": cert["chosen"]["people"],
                "executed_people": transition.people_dispatched if transition.accepted else 0,
            })
        self.last_reconciliation = {"overbooked_seats": self.overbooked_seats,
                                    "returned_to_pool": self.returned_to_pool,
                                    "executed": self.executed}
        self.network = "ONLINE"

    def report(self) -> OutageReport:
        if self.last_reconciliation is None:
            raise ValueError("restore the network before reporting")
        return OutageReport(
            self.seed, self.world_id, self.cut_step, self.rounds, self.mode,
            self.free_at_cut, self.seats, self.reserved_offline, self.reserved_by_team,
            self.overbooked_seats, self.overbooked_seats > 0, self.blocked,
            self.returned_to_pool, self.executed, self.certificates,
        )


def simulate_outage(seed, world_id, cut_step, rounds, mode, *, params_id="v4-cert-test-v1",
                    futures_factory=None, rollout=None, graph=None) -> OutageReport:
    engine = OutageEngine(seed, world_id, mode, params_id=params_id,
                          futures_factory=futures_factory, rollout=rollout, graph=graph)
    for _ in range(cut_step):
        engine.online_step()
    engine.cut()
    for _ in range(rounds):
        engine.offline_step()
    engine.restore()
    return engine.report()
