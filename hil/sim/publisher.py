"""Deterministic simulated sensor publisher for local HIL development."""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timezone
from typing import Callable

from src.hil.bridge import Bus, InMemoryBus


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def publish_sample(bus: Bus, *, seed: int = 2800, step: int = 0,
                   timestamp: Callable[[], str] = _utc_now) -> None:
    rng = random.Random(seed + step)
    count = 100 + rng.randint(-4, 4)
    now = timestamp()
    bus.publish("sentinel/v1/shelter/S-04/occupancy", {
        "schema": "occupancy-v1", "device_id": "sim-shelter-01", "shelter_id": "S-04",
        "count": count, "sigma": round(0.5 + 0.02 * count, 2), "seq": step,
        "ts_utc": now,
    })
    bus.publish("sentinel/v1/zone/Z-03/water_level", {
        "schema": "water-level-v1", "device_id": "sim-level-01", "zone_id": "Z-03",
        "level_cm": round(18 + rng.uniform(-1, 1), 2), "seq": step,
        "ts_utc": now,
    })
    bus.publish("sentinel/v1/status/sim-shelter-01", {
        "schema": "status-v1", "device_id": "sim-shelter-01", "kind": "simulated",
        "uptime_s": step * 5, "rssi_dbm": None, "firmware": "hil-sim-0.1.0",
        "ts_utc": now,
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2800)
    parser.add_argument("--steps", type=int, default=1)
    args = parser.parse_args()
    bus = InMemoryBus()
    for step in range(args.steps):
        publish_sample(bus, seed=args.seed, step=step)
    print(f"Published {args.steps} simulated sensor steps in memory; no hardware result recorded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
