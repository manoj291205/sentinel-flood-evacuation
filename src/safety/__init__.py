"""Deterministic hard-safety evaluation and semantic action masks for V3."""

from .audit import MECHANICS_CONFIG_VERSION, format_evaluation, snapshot_to_json
from .hard_rules import (
    DESTINATION_HAZARD_RULE_ID,
    SAFETY_CONFIGS,
    SAFETY_MODELING_ASSUMPTION_DISCLAIMER,
    V3_SAFETY_V1,
    SafetyConfig,
    evaluate_destination_hazard,
    get_safety_config,
)
from .masks import enumerate_canonical_actions, evaluate_action, evaluate_actions
from .models import (
    ActionSafetyEvaluation,
    RuleLayer,
    RuleProvenance,
    RuleVerdict,
    SafetySnapshot,
)

__all__ = [
    "ActionSafetyEvaluation",
    "DESTINATION_HAZARD_RULE_ID",
    "MECHANICS_CONFIG_VERSION",
    "RuleLayer",
    "RuleProvenance",
    "RuleVerdict",
    "SAFETY_CONFIGS",
    "SAFETY_MODELING_ASSUMPTION_DISCLAIMER",
    "SafetyConfig",
    "SafetySnapshot",
    "V3_SAFETY_V1",
    "enumerate_canonical_actions",
    "evaluate_action",
    "evaluate_actions",
    "evaluate_destination_hazard",
    "format_evaluation",
    "get_safety_config",
    "snapshot_to_json",
]
