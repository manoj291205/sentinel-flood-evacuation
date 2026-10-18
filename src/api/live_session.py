"""Read-only presentation of the pending live certification and re-check log."""

from __future__ import annotations

from src.api.why import action_label, reasons
from src.certify.params import get_cert_params

NOTE = ("Every step, groups already on the road are re-checked; a group whose route loses its "
        "certificate is re-routed to a certified alternative or escalated.")


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
