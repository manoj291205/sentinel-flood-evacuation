"""Authoritative fixed-dimension configuration for the Phase 7 V3 environment."""

from __future__ import annotations

from dataclasses import dataclass


ENV_CONFIG_ID = "v3-env-v1"
MAX_ZONES = 6
MAX_SHELTERS = 9
INVALID_ACTION_BEHAVIOR = "WAIT"
PLACEHOLDER_REWARD_VERSION = "PHASE7_PLACEHOLDER_ZERO"


@dataclass(frozen=True)
class EnvV3Config:
    config_id: str = ENV_CONFIG_ID
    max_zones: int = MAX_ZONES
    max_shelters: int = MAX_SHELTERS
    enable_hard_safety: bool = True
    invalid_action_behavior: str = INVALID_ACTION_BEHAVIOR
    placeholder_reward_enabled: bool = True

    def __post_init__(self) -> None:
        if self.config_id != ENV_CONFIG_ID:
            raise ValueError(f"Phase 7 config_id must be {ENV_CONFIG_ID!r}")
        if (self.max_zones, self.max_shelters) != (MAX_ZONES, MAX_SHELTERS):
            raise ValueError("v3-env-v1 dimensions are frozen at 6 zones and 9 shelters")
        if self.invalid_action_behavior != INVALID_ACTION_BEHAVIOR:
            raise ValueError("Phase 7 masked-action behavior is frozen as WAIT")
        if not self.placeholder_reward_enabled:
            raise ValueError("Phase 7 requires its explicit zero placeholder reward")

    @property
    def dispatch_slots(self) -> int:
        return self.max_zones * self.max_shelters

    @property
    def wait_index(self) -> int:
        return self.dispatch_slots

    @property
    def action_count(self) -> int:
        return self.dispatch_slots + 1


DEFAULT_ENV_CONFIG = EnvV3Config()
WAIT_INDEX = DEFAULT_ENV_CONFIG.wait_index
ACTION_COUNT = DEFAULT_ENV_CONFIG.action_count


class RewardProvider:
    """Narrow Phase 8 injection boundary; no meaningful reward exists in Phase 7."""

    version: str
    defined: bool

    def reward(self, transition_result: object) -> float:
        raise NotImplementedError


class ZeroPlaceholderReward(RewardProvider):
    version = PLACEHOLDER_REWARD_VERSION
    defined = False

    def reward(self, transition_result: object) -> float:
        return 0.0


ZERO_PLACEHOLDER_REWARD = ZeroPlaceholderReward()
