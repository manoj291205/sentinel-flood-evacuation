"""Minimal deterministic hard-safety rules for Sentinel-Agent V3 Phase 5.

The configured threshold is a synthetic project modeling assumption. It is not an
official NDMA flood-safety cutoff and is not sourced from natural-language policy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.sim.events import DispatchAction
from src.sim.state import EpisodeState

from .models import RuleLayer, RuleProvenance, RuleVerdict

SAFETY_MODELING_ASSUMPTION_DISCLAIMER = (
    "SYNTHETIC V3 SAFETY MODELING ASSUMPTION — NOT AN OFFICIAL NDMA "
    "FLOOD-SAFETY CUTOFF."
)
DESTINATION_HAZARD_RULE_ID = "SAFETY_DESTINATION_HAZARD"


@dataclass(frozen=True)
class SafetyConfig:
    """Versioned parameters for deterministic hard-safety evaluation."""

    config_id: str
    version: int
    max_destination_hazard: float
    description: str
    disclaimer: str = SAFETY_MODELING_ASSUMPTION_DISCLAIMER

    def __post_init__(self) -> None:
        if not self.config_id or self.version < 1 or not self.description:
            raise ValueError("safety config identity and description are required")
        if (
            not math.isfinite(self.max_destination_hazard)
            or not 0.0 <= self.max_destination_hazard <= 1.0
        ):
            raise ValueError("max_destination_hazard must be finite and in [0, 1]")
        if self.disclaimer != SAFETY_MODELING_ASSUMPTION_DISCLAIMER:
            raise ValueError("the safety modeling-assumption disclaimer may not be removed")

    def to_dict(self) -> dict[str, str | int | float]:
        return {
            "config_id": self.config_id,
            "version": self.version,
            "max_destination_hazard": self.max_destination_hazard,
            "comparison": "destination_hazard < max_destination_hazard",
            "description": self.description,
            "disclaimer": self.disclaimer,
        }


V3_SAFETY_V1 = SafetyConfig(
    config_id="v3-safety-v1",
    version=1,
    max_destination_hazard=0.70,
    description=(
        "Minimal Phase 5 synthetic destination-hazard limit, reused from the V1 "
        "project proxy for continuity and frozen before any V3 planner results."
    ),
)

SAFETY_CONFIGS = {V3_SAFETY_V1.config_id: V3_SAFETY_V1}


def get_safety_config(config: str | SafetyConfig) -> SafetyConfig:
    if isinstance(config, SafetyConfig):
        return config
    try:
        return SAFETY_CONFIGS[config]
    except KeyError as exc:
        known = ", ".join(sorted(SAFETY_CONFIGS))
        raise ValueError(f"unknown safety config {config!r}; choose {known}") from exc


def evaluate_destination_hazard(
    state: EpisodeState,
    action: DispatchAction,
    config: SafetyConfig,
    *,
    enforced: bool,
) -> RuleVerdict:
    """Require current destination severity to be strictly below the limit."""
    shelter = state.shelter(action.shelter_id)
    if shelter is None:
        raise ValueError("destination hazard may only be checked for a known shelter")
    severity = shelter.flood_severity_current
    allowed = severity < config.max_destination_hazard
    if allowed:
        code = "DESTINATION_HAZARD_BELOW_LIMIT"
        reason = (
            f"Current shelter severity {severity:.6f} is below the configured "
            f"synthetic V3 safety limit of {config.max_destination_hazard:.6f}."
        )
    else:
        code = "DESTINATION_HAZARD_AT_OR_ABOVE_LIMIT"
        reason = (
            f"Current shelter severity {severity:.6f} is at or above the configured "
            f"synthetic V3 safety limit of {config.max_destination_hazard:.6f}."
        )
    return RuleVerdict(
        rule_id=DESTINATION_HAZARD_RULE_ID,
        layer=RuleLayer.HARD_SAFETY,
        provenance=RuleProvenance.SYNTHETIC_SAFETY_RULE,
        allowed=allowed,
        reason_code=code,
        reason=reason,
        current_values=(
            ("destination_shelter_id", action.shelter_id),
            ("destination_hazard_current", severity),
            ("max_destination_hazard", config.max_destination_hazard),
            ("comparison", "<"),
        ),
        config_version=config.config_id,
        enforced=enforced,
    )
