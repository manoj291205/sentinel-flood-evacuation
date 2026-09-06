"""Audit helpers for Phase 5 mechanical and hard-safety decisions."""

from __future__ import annotations

import json

from src.sim.events import ActionRejectionCode, DispatchAction, SimulationAction, WaitAction
from src.sim.transition import ActionValidation

from .models import (
    ActionSafetyEvaluation,
    RuleLayer,
    RuleProvenance,
    RuleVerdict,
    SafetySnapshot,
)

MECHANICS_CONFIG_VERSION = "simulator-mechanics-phase3-v1"


def mechanical_verdict(
    action: SimulationAction,
    validation: ActionValidation,
) -> RuleVerdict:
    """Translate the simulator's authoritative validation into an audit verdict."""
    action_values: list[tuple[str, str | int | float | bool | None]] = [
        ("action_type", "WAIT" if isinstance(action, WaitAction) else "DISPATCH")
    ]
    if isinstance(action, DispatchAction):
        action_values.extend(
            (("zone_id", action.zone_id), ("shelter_id", action.shelter_id))
        )
    if validation.valid:
        action_values.extend(
            (
                ("route_id", validation.route_id),
                ("dispatch_people", validation.people),
                ("travel_lag_steps", validation.travel_lag_steps),
            )
        )
        return RuleVerdict(
            rule_id="MECHANICAL_VALID",
            layer=RuleLayer.MECHANICAL,
            provenance=RuleProvenance.SIMULATOR_MECHANIC,
            allowed=True,
            reason_code="SIMULATOR_VALIDATION_PASSED",
            reason="The simulator reports that the semantic action can execute.",
            current_values=tuple(action_values),
            config_version=MECHANICS_CONFIG_VERSION,
        )

    code = validation.rejection_code or ActionRejectionCode.INVALID_ACTION_TYPE
    return RuleVerdict(
        rule_id=f"MECHANICAL_{code.value}",
        layer=RuleLayer.MECHANICAL,
        provenance=RuleProvenance.SIMULATOR_MECHANIC,
        allowed=False,
        reason_code=code.value,
        reason=validation.message or "The simulator rejected the action.",
        current_values=tuple(action_values),
        config_version=MECHANICS_CONFIG_VERSION,
    )


def snapshot_to_json(snapshot: SafetySnapshot, *, indent: int | None = None) -> str:
    """Serialize with stable key ordering for reproducible audit comparisons."""
    return json.dumps(snapshot.to_dict(), indent=indent, sort_keys=True)


def format_evaluation(evaluation: ActionSafetyEvaluation) -> str:
    """Render one actual structured result without hardcoded decision text."""
    if not evaluation.mechanically_valid:
        status = "MECHANICALLY INVALID"
    elif not evaluation.hard_safety_allowed:
        status = "MECHANICALLY VALID\nHARD SAFETY: EXCLUDED"
    else:
        status = "MECHANICALLY VALID\nHARD SAFETY: ALLOWED"
    failures = [item for item in evaluation.rule_verdicts if not item.allowed]
    details = [f"reason: {item.rule_id} — {item.reason}" for item in failures]
    return "\n".join((evaluation.action_key, status, *details))
