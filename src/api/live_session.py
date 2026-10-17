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


def _route(session, group_id: str) -> str:
    event = next((item for item in session.state.dispatch_events if item.event_id == group_id), None)
    if event is None:
        return group_id
    return action_label(f"{event.source_zone_id}->{event.destination_shelter_id}")


def recheck_rows(session, rows: list[dict]) -> list[dict]:
    return [{**row, "route": _route(session, row["group_id"])} for row in rows]


def certified_context(session) -> dict:
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
        alternatives.append({key: alt[key] for key in ("action_key", "label", "verdict", "lower", "upper")} |
                            {"certified": item.verdict.value == "FEASIBLE", "comparison": comparison})
    step = session.state.current_timestep
    return {
        "params_id": session.params_id, "timestep": step, "threshold": threshold,
        "futures_used": result.n_final, "looks": result.looks,
        "recommendation": recommendation, "why": reasons(synthetic), "candidates": candidates,
        "alternatives": alternatives,
        "rechecks": recheck_rows(session, [row for row in session.recert_log if row["timestep"] == step]),
        "note": NOTE,
    }
