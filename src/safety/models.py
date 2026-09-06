"""Serializable value models for the deterministic V3 safety engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

from src.sim.events import DispatchAction, SimulationAction, WaitAction

SafetyValue: TypeAlias = str | int | float | bool | None


class RuleLayer(str, Enum):
    MECHANICAL = "MECHANICAL"
    HARD_SAFETY = "HARD_SAFETY"


class RuleProvenance(str, Enum):
    SIMULATOR_MECHANIC = "SIMULATOR_MECHANIC"
    SYNTHETIC_SAFETY_RULE = "SYNTHETIC_SAFETY_RULE"
    DOCUMENT_POLICY = "DOCUMENT_POLICY"


@dataclass(frozen=True)
class RuleVerdict:
    """One deterministic rule outcome with machine and human explanations."""

    rule_id: str
    layer: RuleLayer
    provenance: RuleProvenance
    allowed: bool
    reason_code: str
    reason: str
    current_values: tuple[tuple[str, SafetyValue], ...]
    config_version: str
    enforced: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "layer": self.layer.value,
            "provenance": self.provenance.value,
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "current_values": dict(self.current_values),
            "config_version": self.config_version,
            "enforced": self.enforced,
        }


@dataclass(frozen=True)
class ActionSafetyEvaluation:
    """Mechanical and hard-safety outcomes for one semantic action."""

    action: SimulationAction
    mechanically_valid: bool
    hard_safety_allowed: bool
    hard_safety_enabled: bool
    final_allowed: bool
    rule_verdicts: tuple[RuleVerdict, ...]
    exclusions: tuple[RuleVerdict, ...]

    def __post_init__(self) -> None:
        if self.final_allowed and not self.mechanically_valid:
            raise ValueError("a mechanically invalid action cannot be finally allowed")
        if not self.final_allowed and not self.exclusions:
            raise ValueError("every excluded action must have at least one reason")
        if any(verdict.allowed or not verdict.enforced for verdict in self.exclusions):
            raise ValueError("exclusions must be failed, enforced verdicts")

    @property
    def action_key(self) -> str:
        if isinstance(self.action, WaitAction):
            return "WAIT"
        return f"{self.action.zone_id}->{self.action.shelter_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_key": self.action_key,
            "action": self.action.to_dict(),
            "mechanically_valid": self.mechanically_valid,
            "hard_safety_allowed": self.hard_safety_allowed,
            "hard_safety_enabled": self.hard_safety_enabled,
            "final_allowed": self.final_allowed,
            "rule_verdicts": [verdict.to_dict() for verdict in self.rule_verdicts],
            "exclusions": [verdict.to_dict() for verdict in self.exclusions],
        }


@dataclass(frozen=True)
class SafetySnapshot:
    """An immutable mask bundled with the exact semantic action ordering it uses."""

    scenario_id: str
    timestep: int
    safety_config_id: str
    hard_safety_enabled: bool
    canonical_actions: tuple[SimulationAction, ...]
    allowed_mask: tuple[bool, ...]
    evaluations: tuple[ActionSafetyEvaluation, ...]

    def __post_init__(self) -> None:
        if not (
            len(self.canonical_actions)
            == len(self.allowed_mask)
            == len(self.evaluations)
        ):
            raise ValueError("actions, mask, and evaluations must have equal lengths")
        if tuple(item.action for item in self.evaluations) != self.canonical_actions:
            raise ValueError("evaluation ordering must match canonical actions")
        if tuple(item.final_allowed for item in self.evaluations) != self.allowed_mask:
            raise ValueError("mask values must match evaluation outcomes")

    @property
    def allowed_actions(self) -> tuple[SimulationAction, ...]:
        return tuple(
            action
            for action, allowed in zip(self.canonical_actions, self.allowed_mask)
            if allowed
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "timestep": self.timestep,
            "safety_config_id": self.safety_config_id,
            "hard_safety_enabled": self.hard_safety_enabled,
            "canonical_actions": [action.to_dict() for action in self.canonical_actions],
            "allowed_mask": list(self.allowed_mask),
            "actions": [evaluation.to_dict() for evaluation in self.evaluations],
        }


SemanticAction = DispatchAction | WaitAction
