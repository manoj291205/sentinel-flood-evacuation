"""Explanations derived from a sealed certificate, without replaying its decision."""

from __future__ import annotations


def action_label(key: str) -> str:
    if key == "WAIT":
        return "HOLD"
    zone, shelter = key.split("->", 1)
    return f"Z-{int(zone[1:]):02d} → S-{int(shelter[1:]):02d}"


def reasons(cert: dict) -> list[str]:
    threshold = 1 - cert["params"]["eps_dispatch"]
    candidates = [c for c in cert["candidates"] if c["action_key"] != "WAIT"]
    if cert["kind"] == "HOLD":
        best = max(candidates, key=lambda c: c["lower"] or 0, default=None)
        second = (
            f"Best option {action_label(best['action_key'])}: lower bound {best['lower']:.3f}, {best['verdict']}."
            if best else "No dispatch option was available for certification."
        )
        return [
            f"No dispatch option reached the threshold {threshold:.2f} over {cert['futures_used']} sampled futures.",
            second,
            "The gate holds (fail-closed) and escalates; nothing was dispatched.",
        ]
    chosen = next(c for c in candidates if c["action_key"] == cert["chosen"]["action_key"])
    counts = chosen["outcome_counts"]
    parts = [f"{counts.get(name, 0)} {name.lower()}" for name in ("STRANDED", "UNSAFE", "OVERFLOW")]
    if "POLICY" in counts:
        parts.append(f"{counts['POLICY']} POLICY rule-blocked")
    feasible = sum(c["verdict"] == "FEASIBLE" for c in candidates) - 1
    undecided = sum(c["verdict"] == "UNDECIDED" for c in candidates)
    infeasible = sum(c["verdict"] == "INFEASIBLE" for c in candidates)
    return [
        f"Certified lower bound {chosen['lower']:.3f} ≥ threshold {threshold:.2f} over {cert['futures_used']} sampled futures ({cert['looks']} look(s)).",
        f"In {counts.get('OK', chosen['successes'])} of {chosen['n']} futures the group arrives safely; {', '.join(parts)}.",
        f"{feasible} other option(s) also cleared the bar, {undecided} undecided, {infeasible} infeasible; HOLD is always allowed.",
    ]


def explanation(cert: dict, source: str = "RECORDED") -> dict:
    chosen = next((c for c in cert["candidates"] if c["action_key"] == cert["chosen"]["action_key"]), None)
    return {
        "decision_id": cert["cert_id"], "source": source,
        "title": "HOLD" if cert["kind"] == "HOLD" else action_label(cert["chosen"]["action_key"]),
        "reasons": reasons(cert),
        "certified_lower": None if cert["kind"] == "HOLD" else chosen["lower"],
        "threshold": 1 - cert["params"]["eps_dispatch"],
        "futures_used": cert["futures_used"],
    }
