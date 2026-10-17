"""Pure semantic action enumeration and mask construction for V3 Phase 5."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Mapping

from src.sim.events import WAIT, DispatchAction, SimulationAction
from src.sim.schemas import ScenarioV3
from src.sim.state import EpisodeState
from src.sim.transition import validate_action

from .audit import mechanical_verdict
from .hard_rules import SafetyConfig, V3_SAFETY_V1, evaluate_destination_hazard, get_safety_config
from .models import (
    ActionSafetyEvaluation,
    RuleLayer,
    RuleProvenance,
    RuleVerdict,
    SafetySnapshot,
)


def enumerate_canonical_actions(scenario: ScenarioV3) -> tuple[SimulationAction, ...]:
    """Canonical zone-major Cartesian dispatch pairs followed by semantic WAIT."""
    dispatches = tuple(
        DispatchAction(zone.zone_id, shelter.shelter_id)
        for zone in scenario.canonical_zones
        for shelter in scenario.canonical_shelters
    )
    return dispatches + (WAIT,)


def evaluate_action(
    scenario: ScenarioV3,
    state: EpisodeState,
    action: SimulationAction,
    safety_config: str | SafetyConfig = V3_SAFETY_V1,
    *,
    enable_hard_safety: bool = True,
) -> ActionSafetyEvaluation:
    """Evaluate mechanics once, then the additional current-hazard safety rule."""
    config = get_safety_config(safety_config)
    validation = validate_action(scenario, state, action)
    mechanics = mechanical_verdict(action, validation)
    verdicts = [mechanics]

    if not validation.valid:
        return ActionSafetyEvaluation(
            action=action,
            mechanically_valid=False,
            hard_safety_allowed=False,
            hard_safety_enabled=enable_hard_safety,
            final_allowed=False,
            rule_verdicts=tuple(verdicts),
            exclusions=(mechanics,),
        )

    hard_safety_allowed = True
    if isinstance(action, DispatchAction):
        safety = evaluate_destination_hazard(
            state,
            action,
            config,
            enforced=enable_hard_safety,
        )
        verdicts.append(safety)
        hard_safety_allowed = safety.allowed

    final_allowed = validation.valid and (
        hard_safety_allowed or not enable_hard_safety
    )
    exclusions = tuple(
        verdict for verdict in verdicts if not verdict.allowed and verdict.enforced
    )
    return ActionSafetyEvaluation(
        action=action,
        mechanically_valid=True,
        hard_safety_allowed=hard_safety_allowed,
        hard_safety_enabled=enable_hard_safety,
        final_allowed=final_allowed,
        rule_verdicts=tuple(verdicts),
        exclusions=exclusions,
    )


def evaluate_actions(
    scenario: ScenarioV3,
    state: EpisodeState,
    safety_config: str | SafetyConfig = V3_SAFETY_V1,
    *,
    enable_hard_safety: bool = True,
    certifier: Callable[[ScenarioV3, EpisodeState, tuple[DispatchAction, ...]], Mapping[str, Any]] | None = None,
) -> SafetySnapshot:
    """Recompute a fully aligned semantic mask for the current decision state."""
    config = get_safety_config(safety_config)
    actions = enumerate_canonical_actions(scenario)
    evaluations = tuple(
        evaluate_action(
            scenario,
            state,
            action,
            config,
            enable_hard_safety=enable_hard_safety,
        )
        for action in actions
    )
    if certifier is not None:
        evaluations = _apply_certifier(scenario, state, evaluations, certifier)
    return SafetySnapshot(
        scenario_id=state.scenario_id,
        timestep=state.current_timestep,
        safety_config_id=config.config_id,
        hard_safety_enabled=enable_hard_safety,
        canonical_actions=actions,
        allowed_mask=tuple(item.final_allowed for item in evaluations),
        evaluations=evaluations,
    )


def _apply_certifier(scenario, state, evaluations, certifier):
    """Gate every mechanically valid, hard-safe dispatch on its certificate (fail-closed)."""
    candidates = tuple(
        e.action for e in evaluations
        if e.final_allowed and isinstance(e.action, DispatchAction)
    )
    certificates = certifier(scenario, state, candidates) if candidates else {}
    threshold = getattr(certificates, "threshold", 0.95)
    params_id = getattr(certificates, "params_id", "v4-cert-v1")
    gated = []
    for evaluation in evaluations:
        action = evaluation.action
        if not (evaluation.final_allowed and isinstance(action, DispatchAction)):
            gated.append(evaluation)
            continue
        certificate = certificates.get(evaluation.action_key)
        feasible = certificate is not None and certificate.verdict.value == "FEASIBLE"
        verdict = RuleVerdict(
            rule_id="CERTIFIED_ARRIVAL_FEASIBILITY",
            layer=RuleLayer.CERTIFIED,
            provenance=RuleProvenance.CERTIFIED_CHANCE,
            allowed=feasible,
            reason_code=certificate.verdict.value if certificate is not None else "UNDECIDED",
            reason=(
                "certified arrival feasibility lower bound meets the dispatch threshold"
                if feasible
                else "arrival feasibility is not certified; the dispatch is blocked (fail-closed)"
            ),
            current_values=(
                ("lower", certificate.lower if certificate else 0.0),
                ("upper", certificate.upper if certificate else 1.0),
                ("n", certificate.n if certificate else 0),
                ("threshold", threshold),
            ),
            config_version=params_id,
        )
        gated.append(
            replace(
                evaluation,
                final_allowed=feasible,
                rule_verdicts=evaluation.rule_verdicts + (verdict,),
                exclusions=evaluation.exclusions if feasible else evaluation.exclusions + (verdict,),
            )
        )
    return tuple(gated)
