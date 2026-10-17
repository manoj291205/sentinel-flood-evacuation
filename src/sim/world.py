"""V4 world configurations (Phase 21): finer time step, multi-step trips, edge-only closures.

Every value here is a SIMULATION MODELING ASSUMPTION. Legacy v3 configs are never modified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .configs import UNCERTAINTY_CONFIGS, UncertaintyConfig, get_uncertainty_config


@dataclass(frozen=True)
class V4WorldConfig:
    world_id: str
    base_uncertainty_id: str
    timestep_minutes: float = 2.0
    horizon_steps: int = 45
    boarding_minutes: float = 4.0
    flood_speed_reduction: float = 0.6
    evacuation_speed_cap_kph: float = 15.0
    closure_model: str = "EDGE"
    walk_in_rate: float = 0.6
    enable_transit_failures: bool = True

    def __post_init__(self) -> None:
        if not self.world_id or self.timestep_minutes <= 0 or self.horizon_steps < 1:
            raise ValueError("invalid world configuration")
        if self.closure_model != "EDGE":
            raise ValueError("only the EDGE closure model is supported")


def _world(level: str) -> V4WorldConfig:
    return V4WorldConfig(
        world_id=f"v4-{level}-dt2-v1", base_uncertainty_id=f"v3-{level}-v1"
    )


V4_WORLDS: dict[str, V4WorldConfig] = {
    w.world_id: w for w in (_world("low"), _world("medium"), _world("high"))
}
# Phase 27 secondary stress regime (pre-registered): HIGH hazards with heavy walk-ins.
V4_WORLDS["v4-stress-dt2-v1"] = replace(_world("high"), world_id="v4-stress-dt2-v1", walk_in_rate=2.0)


def get_world_config(world_id: str | V4WorldConfig) -> V4WorldConfig:
    if isinstance(world_id, V4WorldConfig):
        return world_id
    try:
        return V4_WORLDS[world_id]
    except KeyError as exc:
        known = ", ".join(sorted(V4_WORLDS))
        raise ValueError(f"unknown v4 world {world_id!r}; choose {known}") from exc


def scaled_uncertainty(world: V4WorldConfig) -> UncertaintyConfig:
    """Per-step uncertainty derived from the 10-minute base with f = dt / 10."""
    base = get_uncertainty_config(world.base_uncertainty_id)
    f = world.timestep_minutes / 10.0

    def per_step(p: float) -> float:
        return 1.0 - (1.0 - p) ** f

    return replace(
        base,
        config_id=f"{world.world_id}-unc",
        version=1,
        description=f"{base.description} Rescaled to {world.timestep_minutes:g}-minute steps.",
        regional_hazard_sigma=base.regional_hazard_sigma * math.sqrt(f),
        local_hazard_sigma=base.local_hazard_sigma * math.sqrt(f),
        regional_hazard_persistence=base.regional_hazard_persistence**f,
        hazard_drift_scale=base.hazard_drift_scale * f,
        maximum_closure_probability=per_step(base.maximum_closure_probability),
        shelter_degradation_probability=per_step(base.shelter_degradation_probability),
        base_closure_multiplier=base.base_closure_multiplier * f,
        hazard_to_closure_strength=base.hazard_to_closure_strength * f,
    )


for _world_cfg in V4_WORLDS.values():
    _scaled = scaled_uncertainty(_world_cfg)
    UNCERTAINTY_CONFIGS.setdefault(_scaled.config_id, _scaled)
