"""Read-only presentation of the pending live certification and re-check log."""

from __future__ import annotations

import hashlib

from src.api.why import action_label, reasons
from src.certify.params import get_cert_params
from src.geospatial import path_for_action
from src.presentation.map_geometry import edge_path_svg
from src.sim import DispatchAction

NOTE = ("Every step, groups already on the road are re-checked; a group whose route loses its "
        "certificate is re-routed to a certified alternative or escalated.")


def _geometry(graph, action_key, edge_ids, timestep, *, reachable=True):
    edges = tuple(edge_ids)
    fingerprint = hashlib.sha256("\n".join(edges).encode()).hexdigest() if edges else None
    return {"action_key": action_key, "edge_ids": list(edges), "reachable": reachable,
            "path_sha256": fingerprint, "path_id": f"path-{fingerprint[:16]}" if fingerprint else None,
            "svg_path": edge_path_svg(graph, edges), "graph_fingerprint": graph.graph_fingerprint,
            "timestep": timestep, "distance_m": round(sum(graph.edges_by_id[e].length_m for e in edges), 3)
            if reachable and edges else None}


def current_route_geometry(session, *, state_version=None):
    """Current engine paths; static background routes never determine a live route."""
    state = session.state
    paths = {}
    for route in state.routes:
        key = f"{route.source_zone_id}->{route.destination_shelter_id}"
        path = path_for_action(session.graph, session.overlay.road_state,
                               DispatchAction(route.source_zone_id, route.destination_shelter_id))
        reachable = route.reachable_current and path.reachable
        paths[key] = _geometry(session.graph, key, path.edge_ids if reachable else (),
                               state.current_timestep, reachable=reachable)
    if session.certified:
        pending = session.certification()
        if pending is not None:
            for candidate in pending[1].candidates:
                paths[candidate.action_key] = _geometry(session.graph, candidate.action_key,
                                                        candidate.edge_ids, state.current_timestep)
    closed = [edge.edge_id for edge in session.overlay.road_state.edges if not edge.open]
    return {"graph_fingerprint": session.graph.graph_fingerprint, "timestep": state.current_timestep,
            "state_version": state_version, "routes": paths,
            "closed_edge_svg_path": edge_path_svg(session.graph, closed)}


def certificate_route_geometry(session, certificates):
    """Pin executed/replayed routes to committed inputs, even after later closures."""
    routes = {}
    for certificate in certificates:
        if certificate["graph_fingerprint"] != session.graph.graph_fingerprint:
            raise ValueError("certificate route belongs to a different graph")
        key = certificate["chosen"]["action_key"]
        inputs = session.ledger.inputs(certificate["cert_id"])
        candidate = next((item for item in inputs.candidates if item.action_key == key), None)
        if key != "WAIT" and candidate is None:
            raise ValueError("committed route is absent from certificate inputs")
        routes[certificate["cert_id"]] = _geometry(session.graph, key,
            candidate.edge_ids if candidate else (), certificate["timestep"])
    return routes


def _candidate(candidate) -> dict:
    return {
        "action_key": candidate.action_key, "label": action_label(candidate.action_key),
        "verdict": candidate.verdict.value, "lower": candidate.lower, "upper": candidate.upper,
        "successes": candidate.successes, "n": candidate.n,
        "outcome_counts": dict(candidate.outcome_counts),
    }


def _subject(session, key: str) -> dict:
    """Describe a candidate using only the current simulator snapshot."""
    empty = {
        "action_key": key, "kind": "HOLD" if key == "WAIT" else "DISPATCH",
        "people": None, "zone_id": None, "zone_name": None,
        "zone_waiting": None, "zone_flood_severity": None,
        "shelter_id": None, "shelter_name": None,
        "shelter_seats_free_before": None, "shelter_seats_free_after": None,
        "route_label": None, "route_length_km": None,
        "eta_minutes": None, "closed_edges_on_route": None,
    }
    if key == "WAIT" or "->" not in key:
        return empty
    zone_id, shelter_id = key.split("->", 1)
    state = session.state
    zone = next((row for row in state.zones if row.zone_id == zone_id), None)
    shelter = next((row for row in state.shelters if row.shelter_id == shelter_id), None)
    route = next((row for row in state.routes if row.source_zone_id == zone_id
                  and row.destination_shelter_id == shelter_id), None)
    if zone is None or shelter is None:
        return empty
    people = min(session.scenario.fleet.vehicle_capacity, zone.population_remaining,
                 shelter.capacity_available)
    return {**empty, "people": people, "zone_id": zone_id,
            "zone_waiting": zone.population_remaining,
            "zone_flood_severity": zone.flood_severity_current,
            "shelter_id": shelter_id,
            "shelter_seats_free_before": shelter.capacity_available,
            "shelter_seats_free_after": shelter.capacity_available - people,
            "route_label": route.route_id if route else None,
            "eta_minutes": route.travel_time_current if route else None}


def _route(session, group_id: str) -> str:
    event = next((item for item in session.state.dispatch_events if item.event_id == group_id), None)
    if event is None:
        return group_id
    return action_label(f"{event.source_zone_id}->{event.destination_shelter_id}")


def recheck_rows(session, rows: list[dict]) -> list[dict]:
    return [{**row, "route": _route(session, row["group_id"])} for row in rows]


def certified_context(session, *, include_subject: bool = False) -> dict:
    pending = session.certification()
    if pending is None:
        raise ValueError("episode is complete")
    result, _ = pending
    params = get_cert_params(session.params_id)
    threshold = 1 - params.eps_dispatch
    candidates = [_candidate(item) for item in result.candidates]
    by_key = {item.action_key: item for item in result.candidates}
    chosen = by_key.get(result.chosen_key)
    recommendation = (_candidate(chosen) if chosen is not None else {
        "action_key": "WAIT", "label": "HOLD", "verdict": "ALWAYS_ALLOWED",
        "lower": None, "upper": None, "successes": 0, "n": 0, "outcome_counts": {},
    })
    if include_subject:
        recommendation["subject"] = _subject(session, recommendation["action_key"])
    synthetic = {"kind": "HOLD" if chosen is None else "DISPATCH", "params": {"eps_dispatch": params.eps_dispatch},
                 "candidates": candidates, "chosen": {"action_key": result.chosen_key},
                 "futures_used": result.n_final, "looks": result.looks}
    others = [item for item in result.candidates if item.action_key != result.chosen_key]
    feasible = sorted((item for item in others if item.verdict.value == "FEASIBLE"),
                      key=lambda item: item.mean_utility, reverse=True)[:3]
    remaining = sorted((item for item in others if item not in feasible),
                       key=lambda item: item.lower, reverse=True)[:3]
    alternatives = []
    for item in [*feasible, *remaining]:
        alt = _candidate(item)
        if chosen is not None and item.verdict.value == "FEASIBLE":
            comparison = (f"Chosen over {alt['label']}: both cleared the bar; the choice has the higher "
                          f"mean utility over the same {result.n_final} futures "
                          f"({chosen.mean_utility:.2f} vs {item.mean_utility:.2f}).")
        else:
            comparison = (f"{alt['label']} is not certified ({item.verdict.value}, lower bound "
                          f"{item.lower:.3f} < {threshold:.2f}), so the gate will not dispatch it.")
        alternative = ({key: alt[key] for key in ("action_key", "label", "verdict", "lower", "upper")} |
                       {"certified": item.verdict.value == "FEASIBLE", "comparison": comparison})
        if include_subject:
            alternative["subject"] = _subject(session, item.action_key)
        alternatives.append(alternative)
    step = session.state.current_timestep
    return {
        "params_id": session.params_id, "timestep": step, "threshold": threshold,
        "futures_used": result.n_final, "looks": result.looks,
        "recommendation": recommendation, "why": reasons(synthetic), "candidates": candidates,
        "alternatives": alternatives,
        "rechecks": recheck_rows(session, [row for row in session.recert_log if row["timestep"] == step]),
        "note": NOTE,
    }
