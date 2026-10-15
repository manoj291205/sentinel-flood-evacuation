"""Certified actuation gate (Phase 25, confidential core element E).

``evaluate`` turns a decision state into a ``CertificationResult``; ``commit`` writes the reservation
and the hash-chained certificate in one ledger transaction and only then emits commands.
"""

from __future__ import annotations

import dataclasses
import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from src.actuation.commands import AdmissionCommand, Command, CommandSink, InMemorySink, VehicleCommand
from src.geospatial import shortest_valid_path
from src.sim.events import DispatchAction
from src.sim.transit import edge_travel_minutes
from src.sim.transition import validate_action

from .certificate import (
    CertificateInputs,
    build_certificate,
    canonical_json,
    certificate_hash,
    edge_set_digest,
)
from .certifier import CertificationResult, Verdict, certify
from .forecast import forecast_from_state
from .futures import FutureSet, root_key
from .ledger import Ledger
from .ledger_view import LedgerView
from .params import CertParams
from .rollout import HOLD_KEY, Candidate, rollout_joint


class GateError(ValueError):
    pass


class CertificateMap(dict):
    """``{action_key: CandidateCertificate}`` that also carries the threshold / params id for masks."""

    def __init__(self, items, *, threshold: float, params_id: str) -> None:
        super().__init__(items)
        self.threshold = threshold
        self.params_id = params_id


def ledger_view_hash(view: LedgerView) -> str:
    return hashlib.sha256(canonical_json(dataclasses.asdict(view))).hexdigest()


def canonical_paths(graph, road_state, scenario) -> dict[tuple[str, str], tuple[str, ...]]:
    """Open shortest path per canonical (zone, shelter) pair that is reachable now."""
    paths = {}
    for zone in scenario.zones:
        for shelter in scenario.shelters:
            p = shortest_valid_path(
                graph, road_state, graph.zone_node_map[zone.zone_id], graph.shelter_node_map[shelter.shelter_id]
            )
            if p.reachable:
                paths[(zone.zone_id, shelter.shelter_id)] = p.edge_ids
    return paths


def canonical_edge_union(graph, road_state, scenario) -> tuple[str, ...]:
    """Sorted union of path edges over ALL canonical dispatches (the A_MAX set)."""
    return tuple(sorted({e for p in canonical_paths(graph, road_state, scenario).values() for e in p}))


def _horizon(paths, graph, world, remaining: int) -> int:
    worst = 0.0
    for edge_ids in paths.values():
        worst = max(worst, sum(
            edge_travel_minutes(graph.edges_by_id[e].length_m, graph.edges_by_id[e].assumed_speed_kph, 0.0, world)
            for e in edge_ids))
    h = math.ceil((world.boarding_minutes + 1.5 * worst) / world.timestep_minutes) + 1
    return max(1, min(remaining, h))


@dataclass(frozen=True)
class GateDecision:
    action: Any
    certificate: dict
    commands: tuple[Command, ...]
    escalate: bool


class CertifiedGate:
    def __init__(
        self, scenario, graph, world, params: CertParams, ledger: Ledger, *,
        sink: CommandSink | None = None, clock=time.perf_counter,
        futures_factory: Callable[..., Any] | None = None, rollout: Callable = rollout_joint,
        world_id: str | None = None,
    ) -> None:
        self.scenario, self.graph, self.world, self.params = scenario, graph, world, params
        self.ledger = ledger
        self.sink = sink if sink is not None else InMemorySink()
        self.clock = clock
        self.futures_factory = futures_factory or FutureSet
        self.rollout = rollout
        self.world_id = world_id or getattr(world, "world_id", "")

    def evaluate(self, state, road_state, snapshot) -> tuple[CertificationResult, CertificateInputs]:
        view = self.ledger.view()
        fc = forecast_from_state(state, road_state, self.scenario)
        paths = canonical_paths(self.graph, road_state, self.scenario)
        edges = tuple(sorted({e for p in paths.values() for e in p}))
        root = root_key(
            incident_id=fc.incident_id, forecast_hash=fc.forecast_hash(),
            graph_fingerprint=self.graph.graph_fingerprint, ledger_hash=ledger_view_hash(view),
            params_id=self.params.params_id, backend=self.params.backend,
        )
        t = state.current_timestep
        horizon = _horizon(paths, self.graph, self.world, self.world.horizon_steps - t)
        candidates = []
        for action in snapshot.allowed_actions:
            if not isinstance(action, DispatchAction):
                continue
            path = paths.get((action.zone_id, action.shelter_id))
            if path is None:
                continue
            people = validate_action(self.scenario, state, action).people
            if people > 0:
                candidates.append(Candidate(action.zone_id, action.shelter_id, people, path, t))
        candidates.sort(key=lambda c: (c.zone_id, c.shelter_id))
        fs = self.futures_factory(fc, self.graph, self.world, root, horizon, edge_ids=edges)
        result = certify(candidates, fs, view, self.world, self.params, self.graph,
                         clock=self.clock, rollout=self.rollout)
        inputs = CertificateInputs(
            cert_id="", world_id=self.world_id, params_id=self.params.params_id, horizon_steps=horizon,
            forecast=fc, ledger=view, candidates=tuple(candidates), edge_ids=edges,
        )
        return result, inputs

    def certificate_map(self, result: CertificationResult) -> CertificateMap:
        return CertificateMap(
            {c.action_key: c for c in result.candidates},
            threshold=1.0 - self.params.eps_dispatch, params_id=self.params.params_id,
        )

    def commit(self, result: CertificationResult, inputs: CertificateInputs, *,
               operator: Mapping[str, str], selected_key: str | None = None,
               group_id: str | None = None) -> GateDecision:
        key = selected_key or result.chosen_key
        override = operator.get("decision") == "OVERRIDE"
        if key != HOLD_KEY:
            if key not in result.allowed_keys():
                raise GateError(f"{key} is not certified feasible; only certified actions may be committed")
            if not override and key != result.chosen_key:
                raise GateError("only the certifier's choice may be committed without an OVERRIDE")
        kind = "HOLD" if key == HOLD_KEY else ("OVERRIDE" if override else "DISPATCH")
        chosen = next((c for c in inputs.candidates if c.action_key == key), None)
        people = chosen.people if chosen is not None else 0
        fc = inputs.forecast
        with self.ledger.transaction() as tx:
            cert_id = self.ledger.next_cert_id()
            gid = None
            if kind != "HOLD":
                gid = group_id or (self.ledger.next_group_id() if hasattr(self.ledger, "next_group_id") else None)
                tx.reserve(chosen.shelter_id, people, cert_id)
            commands = (
                [{"target": "vehicle-terminal", "command": f"route {key}"},
                 {"target": f"shelter-{chosen.shelter_id}", "command": f"reserve {people}"}]
                if kind != "HOLD" else []
            )
            certs = self.ledger.certificates()
            cert = build_certificate(
                cert_id=cert_id, kind=kind, incident_id=fc.incident_id,
                scenario_id=self.scenario.scenario_id, timestep=fc.timestep, root=result.root,
                forecast_hash=fc.forecast_hash(), graph_fingerprint=self.graph.graph_fingerprint,
                ledger_hash=ledger_view_hash(inputs.ledger), params=self.params, a_max=result.a_max,
                result=result, candidates=inputs.candidates, chosen_key=key, chosen_people=people,
                group_id=gid, operator=operator, commands=commands,
                prev_cert_hash=certs[-1]["cert_hash"] if certs else None,
                edge_set_digest=edge_set_digest(inputs.edge_ids),
            )
            tx.append_certificate(cert, dataclasses.replace(inputs, cert_id=cert_id))
        out: list[Command] = []
        if kind != "HOLD":
            out = [
                VehicleCommand(cert_id, cert["cert_hash"], gid, chosen.zone_id, chosen.shelter_id,
                               people, chosen.edge_ids),
                AdmissionCommand(cert_id, cert["cert_hash"], chosen.shelter_id, people, gid),
            ]
            for command in out:
                self.sink.send(command)
        escalate = key == HOLD_KEY and not (result.allowed_keys() - {HOLD_KEY})
        action = self._action(key)
        return GateDecision(action, cert, tuple(out), escalate)

    @staticmethod
    def _action(key: str):
        from src.sim import DispatchAction as D, WaitAction

        if key == HOLD_KEY:
            return WaitAction()
        zone, shelter = key.split("->", 1)
        return D(zone, shelter)
