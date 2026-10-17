"""Phase 26 flip-flop study: re-certification with hysteresis never oscillates between shelters.

    python scripts/phase26_flipflop.py --seeds 1000

Each seed simulates one in-transit group over 40 steps against fake futures whose per-shelter success
probability follows a random walk with random closures (a shelter's probability collapses for a while).
Writes data/eval_results/phase26/flipflop.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.certify.certifier import Verdict  # noqa: E402
from src.certify.ledger_view import LedgerView  # noqa: E402
from src.certify.params import CertParams  # noqa: E402
from src.certify.recertify import GroupHistory, RecertPolicy, recertify_group  # noqa: E402
from src.certify.rollout import Candidate, Outcome, RolloutResult  # noqa: E402

OUT = ROOT / "data/eval_results/phase26/flipflop.json"
SHELTERS = ("S1", "S2", "S3", "S4")
STEPS = 40


class FakeFutures:
    A_MAX = 21
    root = "f" * 64

    def future(self, k):
        return k


def make_rollout(p_by_shelter, step):
    def rollout(c, k, *args, **kwargs):
        u = int(hashlib.sha256(f"{c.shelter_id}|{k}|{step}".encode()).hexdigest()[:8], 16) / 2**32
        ok = u < p_by_shelter[c.shelter_id]
        return RolloutResult(ok, Outcome.OK if ok else Outcome.STRANDED, 5,
                             float(c.people if ok else -c.people), ok, True if ok else None,
                             True if ok else None)
    return rollout


def cand(shelter):
    return Candidate("Z1", shelter, 30, ("e",), 0, 0.0)


def run_seed(seed: int, policy: RecertPolicy, params: CertParams) -> dict:
    rng = random.Random(seed)
    p = {s: rng.uniform(0.85, 1.0) for s in SHELTERS}
    closed_until = {s: -1 for s in SHELTERS}
    view = LedgerView(0, {}, {}, {}, (), {}, {})
    current, history = "S1", GroupHistory()
    visited, returns, migrations = [current], 0, 0
    for step in range(STEPS):
        for s in SHELTERS:
            if step > closed_until[s] and rng.random() < 0.06:
                closed_until[s] = step + rng.randint(2, 8)
            p[s] = 0.30 if step <= closed_until[s] else min(1.0, max(0.85, p[s] + rng.uniform(-0.03, 0.03)))
        alts = tuple(cand(s) for s in SHELTERS if s != current)
        d = recertify_group("E-1", cand(current), alts, FakeFutures(), view, None, params, None,
                            timestep=step, history=history, policy=policy,
                            rollout=make_rollout(p, step))
        if d.action == "MIGRATE":
            if d.new_shelter_id in history.left_shelters or d.new_shelter_id in visited:
                returns += 1
            history = GroupHistory(history.migrations + 1, step, history.left_shelters | {current})
            current = d.new_shelter_id
            visited.append(current)
            migrations += 1
    return {"migrations": migrations, "returns": returns}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=1000)
    args = parser.parse_args()
    policy, params = RecertPolicy(), CertParams()
    started = time.perf_counter()
    rows = [run_seed(seed, policy, params) for seed in range(args.seeds)]
    result = {
        "seeds": args.seeds, "steps": STEPS, "policy": {"cooldown_steps": policy.cooldown_steps,
                                                         "max_migrations": policy.max_migrations},
        "returns_to_left_shelter": sum(r["returns"] for r in rows),
        "max_migrations_observed": max(r["migrations"] for r in rows),
        "seeds_with_migration": sum(r["migrations"] > 0 for r in rows),
        "total_migrations": sum(r["migrations"] for r in rows),
        "wall_seconds": round(time.perf_counter() - started),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["returns_to_left_shelter"] == 0 and result["max_migrations_observed"] <= 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
