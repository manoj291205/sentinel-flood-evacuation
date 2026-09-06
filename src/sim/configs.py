"""Frozen synthetic uncertainty configurations for Sentinel-Agent V3 Phase 4.

These values are SIMULATION MODELING ASSUMPTIONS. They are not empirically calibrated
flood, road-closure, travel, or shelter-failure probabilities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


MODELING_ASSUMPTION_DISCLAIMER = (
    "SIMULATION MODELING ASSUMPTIONS — NOT EMPIRICALLY CALIBRATED FLOOD, "
    "ROAD-CLOSURE, TRAVEL, OR SHELTER-FAILURE PROBABILITIES."
)


class UncertaintyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class UncertaintyConfig:
    """Versioned parameters and their units for the synthetic Phase 4 process."""

    config_id: str
    version: int
    level: UncertaintyLevel
    description: str
    regional_hazard_sigma: float
    regional_hazard_persistence: float
    local_hazard_sigma: float
    hazard_drift_scale: float
    travel_noise_fraction: float
    route_hazard_travel_factor: float
    minimum_travel_multiplier: float
    maximum_travel_multiplier: float
    base_closure_multiplier: float
    hazard_to_closure_strength: float
    maximum_closure_probability: float
    restricted_threshold: float
    closed_threshold: float
    shelter_degradation_probability: float
    disclaimer: str = MODELING_ASSUMPTION_DISCLAIMER

    def __post_init__(self) -> None:
        if not self.config_id or self.version < 1 or not self.description:
            raise ValueError("uncertainty config identity and description are required")
        if not isinstance(self.level, UncertaintyLevel):
            raise ValueError("level must be an UncertaintyLevel")
        for name in (
            "regional_hazard_sigma",
            "local_hazard_sigma",
            "hazard_drift_scale",
            "travel_noise_fraction",
            "route_hazard_travel_factor",
            "base_closure_multiplier",
            "hazard_to_closure_strength",
            "shelter_degradation_probability",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if not 0 <= self.regional_hazard_persistence < 1:
            raise ValueError("regional_hazard_persistence must be in [0, 1)")
        if not 0 < self.minimum_travel_multiplier <= 1:
            raise ValueError("minimum_travel_multiplier must be in (0, 1]")
        if self.maximum_travel_multiplier < 1:
            raise ValueError("maximum_travel_multiplier must be >= 1")
        for name in (
            "maximum_closure_probability",
            "restricted_threshold",
            "closed_threshold",
            "shelter_degradation_probability",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.restricted_threshold >= self.closed_threshold:
            raise ValueError("restricted_threshold must be below closed_threshold")
        if self.disclaimer != MODELING_ASSUMPTION_DISCLAIMER:
            raise ValueError("the modeling-assumption disclaimer may not be removed")

    @property
    def forecast_std_next(self) -> float:
        """One-step marginal innovation scale on the normalized severity scale."""
        return math.sqrt(
            self.regional_hazard_sigma**2 + self.local_hazard_sigma**2
        )

    def to_dict(self) -> dict[str, str | int | float]:
        return {
            "config_id": self.config_id,
            "version": self.version,
            "level": self.level.value,
            "description": self.description,
            "regional_hazard_sigma": self.regional_hazard_sigma,
            "regional_hazard_persistence": self.regional_hazard_persistence,
            "local_hazard_sigma": self.local_hazard_sigma,
            "hazard_drift_scale": self.hazard_drift_scale,
            "travel_noise_fraction": self.travel_noise_fraction,
            "route_hazard_travel_factor": self.route_hazard_travel_factor,
            "minimum_travel_multiplier": self.minimum_travel_multiplier,
            "maximum_travel_multiplier": self.maximum_travel_multiplier,
            "base_closure_multiplier": self.base_closure_multiplier,
            "hazard_to_closure_strength": self.hazard_to_closure_strength,
            "maximum_closure_probability": self.maximum_closure_probability,
            "restricted_threshold": self.restricted_threshold,
            "closed_threshold": self.closed_threshold,
            "shelter_degradation_probability": self.shelter_degradation_probability,
            "disclaimer": self.disclaimer,
        }


LOW = UncertaintyConfig(
    config_id="v3-low-v1",
    version=1,
    level=UncertaintyLevel.LOW,
    description="Small innovations, travel variation, closure risk, and degradation.",
    regional_hazard_sigma=0.008,
    regional_hazard_persistence=0.30,
    local_hazard_sigma=0.005,
    hazard_drift_scale=0.006,
    travel_noise_fraction=0.04,
    route_hazard_travel_factor=0.20,
    minimum_travel_multiplier=0.60,
    maximum_travel_multiplier=1.60,
    base_closure_multiplier=0.35,
    hazard_to_closure_strength=0.015,
    maximum_closure_probability=0.12,
    restricted_threshold=0.78,
    closed_threshold=0.95,
    shelter_degradation_probability=0.006,
)

MEDIUM = UncertaintyConfig(
    config_id="v3-medium-v1",
    version=1,
    level=UncertaintyLevel.MEDIUM,
    description="Moderate, overlapping synthetic operational uncertainty.",
    regional_hazard_sigma=0.018,
    regional_hazard_persistence=0.50,
    local_hazard_sigma=0.012,
    hazard_drift_scale=0.008,
    travel_noise_fraction=0.10,
    route_hazard_travel_factor=0.30,
    minimum_travel_multiplier=0.55,
    maximum_travel_multiplier=1.80,
    base_closure_multiplier=0.70,
    hazard_to_closure_strength=0.035,
    maximum_closure_probability=0.25,
    restricted_threshold=0.68,
    closed_threshold=0.90,
    shelter_degradation_probability=0.018,
)

HIGH = UncertaintyConfig(
    config_id="v3-high-v1",
    version=1,
    level=UncertaintyLevel.HIGH,
    description="Larger but bounded synthetic uncertainty; not a worst-case stress test.",
    regional_hazard_sigma=0.035,
    regional_hazard_persistence=0.65,
    local_hazard_sigma=0.025,
    hazard_drift_scale=0.010,
    travel_noise_fraction=0.18,
    route_hazard_travel_factor=0.45,
    minimum_travel_multiplier=0.50,
    maximum_travel_multiplier=2.00,
    base_closure_multiplier=1.15,
    hazard_to_closure_strength=0.070,
    maximum_closure_probability=0.40,
    restricted_threshold=0.60,
    closed_threshold=0.84,
    shelter_degradation_probability=0.040,
)

UNCERTAINTY_CONFIGS = {
    config.config_id: config for config in (LOW, MEDIUM, HIGH)
}


def get_uncertainty_config(config: str | UncertaintyConfig) -> UncertaintyConfig:
    if isinstance(config, UncertaintyConfig):
        return config
    try:
        return UNCERTAINTY_CONFIGS[config]
    except KeyError as exc:
        known = ", ".join(sorted(UNCERTAINTY_CONFIGS))
        raise ValueError(f"unknown uncertainty config {config!r}; choose {known}") from exc
