"""Stable, keyed pseudo-random values for paired stochastic evaluation.

There is no mutable global or per-episode draw cursor. Every value is a pure function of
the root seed, replication, config, subsystem namespace, timestep, and entity/event key.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class RandomStream(str, Enum):
    REGIONAL_HAZARD = "regional_hazard"
    LOCAL_HAZARD = "local_hazard"
    TRAVEL = "travel"
    ROUTE_CLOSURE = "route_closure"
    SHELTER_DEGRADATION = "shelter_degradation"
    WALK_IN = "walk_in"


@dataclass(frozen=True)
class EpisodeRandomStreams:
    root_seed: int
    config_id: str
    replication_id: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.root_seed, bool) or not isinstance(self.root_seed, int):
            raise ValueError("root_seed must be an integer")
        if self.root_seed < 0:
            raise ValueError("root_seed must be nonnegative")
        if not self.config_id:
            raise ValueError("config_id must be nonempty")
        if isinstance(self.replication_id, bool) or not isinstance(
            self.replication_id, int
        ):
            raise ValueError("replication_id must be an integer")
        if self.replication_id < 0:
            raise ValueError("replication_id must be nonnegative")

    def _digest(self, stream: RandomStream, key: tuple[Any, ...], lane: int) -> bytes:
        payload = json.dumps(
            [
                "sentinel-agent-v3-keyed-rng-v1",
                self.root_seed,
                self.config_id,
                self.replication_id,
                stream.value,
                list(key),
                lane,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).digest()

    def uniform(self, stream: RandomStream, *key: Any) -> float:
        """Stable value in [0, 1), independent of calls made for other keys."""
        integer = int.from_bytes(self._digest(stream, key, 0)[:8], "big")
        return integer / 2**64

    def normal(self, stream: RandomStream, *key: Any) -> float:
        """Stable standard-normal value using two independently keyed digest lanes."""
        first = int.from_bytes(self._digest(stream, key, 0)[:8], "big")
        second = int.from_bytes(self._digest(stream, key, 1)[:8], "big")
        u1 = (first + 1) / (2**64 + 1)
        u2 = (second + 1) / (2**64 + 1)
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
