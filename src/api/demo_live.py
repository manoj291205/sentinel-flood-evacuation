"""Build and load the deterministic six-epoch recorded gate demonstration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.api.why import action_label, reasons
from src.certify.gate import CertifiedGate
from src.certify.ledger import SimLedgerAdapter
from src.certify.params import get_cert_params
from src.certify.recertify import RecertPolicy, recertify_in_transit
from src.geospatial import load_road_graph
from src.geospatial.v4_runtime import build_v4_runtime
from src.safety import evaluate_actions

ROOT = Path(__file__).resolve().parents[2]
TRACE_PATH = ROOT / "data" / "demo_v4" / "demo_trace.json"
DEMO_CONFIG = {
    "config_id": "v4-demo-trace-v1", "world_id": "v4-medium-dt2-v1", "seed": 620003,
    "params_id": "v4-cert-test-v1", "epochs": 6,
    "operator": {"decision": "ACCEPT", "actor": "demo-operator", "reason": ""},
    "seed_note": "Seed chosen during planning (2026-10-17) because its first six epochs include an escalated hold, dispatches, in-transit re-checks and a re-route; a demonstration, not a performance sample. Parameters v4-cert-test-v1 are the fast CI set, not the evaluated configuration (v4-cert-eval-v1).",
}


def _recert_row(timestep, decision):
    return {
        "timestep": timestep, "group_id": decision.event_id, "action": decision.action,
        "verdict": decision.keep_verdict.value if decision.action != "COOLDOWN" else None,
        "lower": decision.keep_lower if decision.action != "COOLDOWN" else None,
        "upper": decision.keep_upper if decision.action != "COOLDOWN" else None,
        "cert_id": decision.certificate["cert_id"] if decision.certificate else None,
    }


def _step(epoch, state, result, decision, recert, certs, audit):
    cert = decision.certificate
    candidates = cert["candidates"]
    chosen_key = cert["chosen"]["action_key"]
    label = action_label(chosen_key)
    n = cert["futures_used"]
    migration = next((c for c in certs if c["kind"] == "MIGRATION"), None)
    count = lambda verdict: sum(c["verdict"] == verdict for c in candidates)  # noqa: E731
    if cert["kind"] == "DISPATCH":
        caption = (f"{n} sampled futures checked for every option; {count('FEASIBLE')} option(s) cleared the bar, "
                   f"{count('UNDECIDED')} undecided, {count('INFEASIBLE')} infeasible. Suggested: {label}.")
        kind = "NEW DISPATCH"
    else:
        caption = (f"No dispatch option cleared the bar across {n} sampled futures, so the gate holds (fail-closed) "
                   "and escalates to the field team.") if decision.escalate else "The gate holds; no dispatch was committed."
        kind = "HOLD + ESCALATE" if decision.escalate else "HOLD"
    if recert:
        keep = sum(d.action in {"KEEP", "COOLDOWN"} for d in recert)
        migrate = sum(d.action == "MIGRATE" for d in recert)
        caption += f" {len(recert)} group(s) on the road re-checked: {keep} keep, {migrate} re-routed."
    current = [e for e in state.dispatch_events if e.status.value == "IN_TRANSIT"]
    groups = [
        {"group_id": e.event_id, "route": action_label(f"{e.source_zone_id}->{e.destination_shelter_id}"),
         "meta": f"{e.people} people", "state": e.status.value, "tone": "info"}
        for e in current
    ]
    shelters = [
        {"shelter_id": f"S-{int(s.shelter_id[1:]):02d}", "name": f"Shelter {s.shelter_id}",
         "capacity_total": s.capacity_total, "occupied": s.occupancy_current,
         "reserved": s.capacity_reserved, "status": s.status_current.value}
        for s in state.shelters
    ]
    events = []
    for event in audit:
        name = event.event_type.value
        tone = ("ok" if name == "ARRIVAL_PROCESSED" else
                "bad" if name in {"GROUP_STRANDED", "ARRIVAL_UNSAFE", "ARRIVAL_OVERFLOW"} else
                "warn" if "CLOSED" in name else "info")
        events.append({"timestep": event.timestep, "kind": tone, "text": event.message or name.replace("_", " ")})
    zone = chosen_key.split("->")[0] if chosen_key != "WAIT" else None
    return {
        "step_index": epoch, "timestep": epoch, "pipeline_stage": 4 if cert["kind"] in {"DISPATCH", "HOLD"} else 3,
        "highlight_zone": f"Z-{int(zone[1:]):02d}" if zone else None,
        "default_selection": label, "kind": kind, "caption": caption,
        "suggestion": {"title": label, "meta": f"{cert['chosen']['people']} people · certificate {cert['cert_id']}",
                       "why": reasons(cert)},
        "gate": {"meta": f"n = {n} futures · {cert['looks']} look(s) · 1 − ε = {1 - cert['params']['eps_dispatch']:.2f} · {DEMO_CONFIG['params_id']}",
                 "candidates": [
                     {"id": c["action_key"], "label": action_label(c["action_key"]),
                      "status": "ALWAYS ALLOWED" if c["verdict"] == "ALWAYS_ALLOWED" else c["verdict"],
                      "lower": c["lower"], "upper": c["upper"],
                      "meta": "always allowed" if c["action_key"] == "WAIT" else f"{c['successes']}/{c['n']} futures OK"}
                     for c in candidates]},
        "decision_required": True,
        "override_alternatives": [action_label(c["action_key"]) for c in candidates
                                  if c["verdict"] == "FEASIBLE" and c["action_key"] != chosen_key],
        "certificate_id": cert["cert_id"] if cert["kind"] == "DISPATCH" else None,
        "hold_record": f"HOLD logged as {cert['cert_id']}" if cert["kind"] == "HOLD" else None,
        "auto_note": f"Re-routed automatically as {migration['cert_id']} (operator notified)." if migration else None,
        "events": events,
        "kpis": {"waiting": state.population_remaining, "on_road": state.people_in_transit,
                 "safe": state.people_safely_arrived, "certificates_issued": len(certs)},
        "moving_group": None, "g0009_label": "", "groups": groups, "shelters": shelters,
    }


def build_demo_trace(config: dict = DEMO_CONFIG, graph=None) -> dict:
    graph = graph or load_road_graph()
    scenario, sim, graph, overlay, world = build_v4_runtime(
        config["world_id"], generator_seed=config["seed"], graph=graph)
    ledger = SimLedgerAdapter(sim)
    gate = CertifiedGate(scenario, graph, world, get_cert_params(config["params_id"]), ledger,
                         world_id=config["world_id"])
    histories = {}
    steps, step_certificates, recert = [], [], []
    for epoch in range(config["epochs"]):
        if sim.state.terminal:
            raise RuntimeError("demo ended before six epochs")
        sim.observe()
        state = sim.prepared_state_for_debug()
        before = len(ledger.certificates())
        old_audit = len(state.audit_log)
        checks = recertify_in_transit(gate, state, overlay.road_state,
                                     sim.transit_plans(), histories, RecertPolicy())
        state = sim.prepared_state_for_debug()
        result, inputs = gate.evaluate(state, overlay.road_state, evaluate_actions(scenario, state))
        decision = gate.commit(result, inputs, operator=config["operator"])
        state = sim.state
        issued = ledger.certificates()
        recert.extend(_recert_row(epoch, row) for row in checks)
        step = _step(epoch, state, result, decision, checks, issued[before:], state.audit_log[old_audit:])
        step["kpis"]["certificates_issued"] = len(issued)
        steps.append(step)
        step_certificates.append([c["cert_id"] for c in issued[before:]])
    certs = ledger.certificates()
    return {"contract": "sentinel-demo-trace-v1", "config": dict(config),
            "graph_fingerprint": graph.graph_fingerprint, "steps": steps,
            "step_certificates": step_certificates, "certificates": certs,
            "inputs": {c["cert_id"]: ledger.inputs(c["cert_id"]).to_dict() for c in certs},
            "recert": recert}


def load_demo_trace(path: Path = TRACE_PATH) -> dict:
    import jsonschema

    trace = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "specs/contracts/demo_trace.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(trace, schema)
    return trace


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build_demo_trace(), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    if args.check:
        return 0 if TRACE_PATH.is_file() and TRACE_PATH.read_bytes() == raw else 1
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_bytes(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
