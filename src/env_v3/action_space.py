"""Stable integer-to-semantic action mapping for the fixed V3 envelope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from src.safety import SafetySnapshot
from src.sim import WAIT, DispatchAction, ScenarioV3
from src.sim.events import SimulationAction

from .config import ACTION_COUNT, DEFAULT_ENV_CONFIG, EnvV3Config, WAIT_INDEX


class EnvironmentConfigurationError(ValueError):
    """Raised when a scenario cannot be represented by the frozen environment."""


@dataclass(frozen=True)
class DecodedAction:
    index: int
    action_type: str
    zone_slot: int | None = None
    shelter_slot: int | None = None
    zone_id: str | None = None
    shelter_id: str | None = None
    semantic: SimulationAction | None = None

    @property
    def present(self) -> bool:
        return self.semantic is not None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "index": self.index,
            "action_type": self.action_type,
        }
        if self.zone_slot is not None:
            payload["zone_slot"] = self.zone_slot
            payload["shelter_slot"] = self.shelter_slot
            payload["zone_id"] = self.zone_id
            payload["shelter_id"] = self.shelter_id
        return payload


class FixedActionMap:
    """Scenario-specific IDs placed into globally fixed 6x9 action slots."""

    def __init__(
        self,
        scenario: ScenarioV3,
        config: EnvV3Config = DEFAULT_ENV_CONFIG,
    ) -> None:
        if len(scenario.zones) > config.max_zones:
            raise EnvironmentConfigurationError(
                f"scenario has {len(scenario.zones)} zones; v3-env-v1 supports at most {config.max_zones}"
            )
        if len(scenario.shelters) > config.max_shelters:
            raise EnvironmentConfigurationError(
                f"scenario has {len(scenario.shelters)} shelters; v3-env-v1 supports at most {config.max_shelters}"
            )
        pairs = [(r.source_zone_id, r.destination_shelter_id) for r in scenario.network.routes]
        if len(pairs) != len(set(pairs)):
            raise EnvironmentConfigurationError(
                "v3-env-v1 supports at most one route per zone-shelter pair"
            )
        self.scenario = scenario
        self.config = config
        self.zone_ids = tuple(zone.zone_id for zone in scenario.canonical_zones)
        self.shelter_ids = tuple(shelter.shelter_id for shelter in scenario.canonical_shelters)
        self.zone_slots = {zone_id: slot for slot, zone_id in enumerate(self.zone_ids)}
        self.shelter_slots = {
            shelter_id: slot for slot, shelter_id in enumerate(self.shelter_ids)
        }

    @property
    def zone_slot_to_id(self) -> tuple[str | None, ...]:
        return self.zone_ids + (None,) * (self.config.max_zones - len(self.zone_ids))

    @property
    def shelter_slot_to_id(self) -> tuple[str | None, ...]:
        return self.shelter_ids + (None,) * (
            self.config.max_shelters - len(self.shelter_ids)
        )

    def encode_dispatch(self, zone_id: str, shelter_id: str) -> int:
        try:
            zone_slot = self.zone_slots[zone_id]
            shelter_slot = self.shelter_slots[shelter_id]
        except KeyError as exc:
            raise KeyError(f"unknown environment entity ID: {exc.args[0]}") from exc
        return zone_slot * self.config.max_shelters + shelter_slot

    def decode_action(self, index: int) -> DecodedAction:
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)):
            raise ValueError("action must be an integer")
        index = int(index)
        if not 0 <= index < self.config.action_count:
            raise ValueError(f"action index must be in [0, {self.config.action_count - 1}]")
        if index == self.config.wait_index:
            return DecodedAction(index, "WAIT", semantic=WAIT)
        zone_slot, shelter_slot = divmod(index, self.config.max_shelters)
        zone_id = self.zone_slot_to_id[zone_slot]
        shelter_id = self.shelter_slot_to_id[shelter_slot]
        if zone_id is None or shelter_id is None:
            return DecodedAction(
                index,
                "ABSENT_SLOT",
                zone_slot,
                shelter_slot,
                zone_id,
                shelter_id,
                None,
            )
        semantic = DispatchAction(zone_id, shelter_id)
        return DecodedAction(
            index,
            "DISPATCH",
            zone_slot,
            shelter_slot,
            zone_id,
            shelter_id,
            semantic,
        )

    def semantic_action(self, index: int) -> SimulationAction | None:
        return self.decode_action(index).semantic

    def fixed_mask(self, snapshot: SafetySnapshot) -> np.ndarray:
        if snapshot.scenario_id != self.scenario.scenario_id:
            raise ValueError("safety snapshot scenario does not match action mapping")
        mask = np.zeros(self.config.action_count, dtype=bool)
        for action, allowed in zip(snapshot.canonical_actions, snapshot.allowed_mask):
            if action == WAIT:
                mask[self.config.wait_index] = allowed
            elif isinstance(action, DispatchAction):
                mask[self.encode_dispatch(action.zone_id, action.shelter_id)] = allowed
        return mask


def decode_action(index: int, mapping: FixedActionMap) -> DecodedAction:
    return mapping.decode_action(index)


def encode_dispatch(zone_id: str, shelter_id: str, mapping: FixedActionMap) -> int:
    return mapping.encode_dispatch(zone_id, shelter_id)


assert WAIT_INDEX == 54 and ACTION_COUNT == 55
