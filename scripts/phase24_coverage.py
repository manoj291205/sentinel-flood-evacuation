"""P24 coverage study: false-accept and accept rates of the certifier on synthetic Bernoulli candidates."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path

from src.certify.certifier import Verdict, certify
from src.certify.params import CertParams
from src.certify.rollout import Outcome, RolloutResult

OUT = Path(__file__).resolve().parents[1] / "data/eval_results/phase24/coverage.json"


@dataclass(frozen=True)
class Cand:
    zone_id: str
    shelter_id: str
    people: int = 20

    @property
    def action_key(self) -> str:
        return f"{self.zone_id}->{self.shelter_id}"


class Futures:
    A_MAX = 21

    def future(self, k):
        return k


def run(p: float, reps: int) -> dict:
    cand = Cand("Z-01", "S-01")
    accepted = infeasible = 0
    for rep in range(reps):
        def rollout(c, k, *_):
            ok = random.Random(f"{rep}|{k}").random() < p
            return RolloutResult(ok, Outcome.OK if ok else Outcome.STRANDED, 3, 20.0 if ok else -20.0, ok, True, True)

        verdict = certify([cand], Futures(), None, None, CertParams(), None, rollout=rollout).candidates[0].verdict
        accepted += verdict is Verdict.FEASIBLE
        infeasible += verdict is Verdict.INFEASIBLE
    return {"true_p": p, "reps": reps, "accept_rate": accepted / reps, "infeasible_rate": infeasible / reps}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reps", type=int, default=10000)
    args = parser.parse_args()
    rows = [run(p, args.reps) for p in (0.90, 0.94, 0.949, 0.96, 0.99)]
    result = {"delta": CertParams().delta, "threshold": 1 - CertParams().eps_dispatch, "rows": rows,
              "false_accept_ok": all(r["accept_rate"] <= CertParams().delta for r in rows if r["true_p"] < 0.95)}
    if args.reps == 10000:
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
