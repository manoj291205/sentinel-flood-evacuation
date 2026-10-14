"""Sequential fail-closed certifier (Phase 24, confidential core element D).

A candidate dispatch is FEASIBLE only when a one-sided Clopper-Pearson lower bound on the joint
arrival-feasibility probability reaches 1 - eps. Anything not proven is UNDECIDED and blocked.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from scipy.stats import beta

from .rollout import HOLD_KEY, Candidate, rollout_joint


class Verdict(str, Enum):
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNDECIDED = "UNDECIDED"


def clopper_pearson(successes: int, n: int, alpha: float) -> tuple[float, float]:
    """One-sided bounds, each at level ``alpha``."""
    lo = 0.0 if successes == 0 else float(beta.ppf(alpha, successes, n - successes + 1))
    hi = 1.0 if successes == n else float(beta.ppf(1 - alpha, successes + 1, n - successes))
    return lo, hi


@dataclass(frozen=True)
class CandidateCertificate:
    action_key: str
    verdict: Verdict
    successes: int
    n: int
    lower: float
    upper: float
    mean_utility: float
    outcome_counts: Mapping[str, int]


@dataclass(frozen=True)
class CertificationResult:
    root: str
    params_id: str
    a_max: int
    looks: int
    n_final: int
    elapsed_ms: float
    deadline_hit: bool
    candidates: tuple[CandidateCertificate, ...]
    chosen_key: str

    def allowed_keys(self) -> frozenset[str]:
        return frozenset(
            {c.action_key for c in self.candidates if c.verdict is Verdict.FEASIBLE}
            | {HOLD_KEY}
        )


def paired_argmax(feasible: Sequence[str], utilities: Mapping[str, Sequence[float]]) -> str:
    """Best mean utility over the common futures; ties go to the earliest key in ``feasible``."""
    common = min(len(utilities[key]) for key in feasible)
    best_key, best_value = feasible[0], None
    for key in feasible:
        value = sum(utilities[key][:common]) / common if common else 0.0
        if best_value is None or value > best_value:
            best_key, best_value = key, value
    return best_key


def certify(
    candidates: Sequence[Candidate],
    futures: Any,
    ledger: Any,
    world: Any,
    params: Any,
    graph: Any,
    *,
    clock: Callable[[], float] = time.perf_counter,
    rollout: Callable = rollout_joint,
) -> CertificationResult:
    ordered = sorted(candidates, key=lambda c: (c.zone_id, c.shelter_id))
    alpha = params.delta / (params.max_looks * futures.A_MAX)
    keys = [c.action_key for c in ordered]
    status = {k: Verdict.UNDECIDED for k in keys}
    successes = {k: [] for k in keys}  # per-future z, in future order
    utilities = {k: [] for k in keys}
    outcomes = {k: [] for k in keys}
    frozen: dict[str, tuple[int, int, float, float]] = {}  # key -> (S, n, lo, hi) at decision look
    start = clock()
    deadline_s = params.deadline_ms / 1000.0
    deadline_hit = False
    n = 0
    completed_n = 0
    looks = 0
    target = params.k0
    for look in range(1, params.max_looks + 1):
        for k in range(n + 1, target + 1):
            future = futures.future(k)
            for c in ordered:
                key = c.action_key
                if status[key] is Verdict.INFEASIBLE:
                    continue
                r = rollout(c, future, ledger, world, params, graph)
                successes[key].append(bool(r.z))
                utilities[key].append(r.utility)
                outcomes[key].append(r.outcome.value)
            if clock() - start > deadline_s:
                deadline_hit = True
                break
        if deadline_hit:
            # A partial look is discarded: verdicts only ever use planned look sizes.
            break
        n = completed_n = target
        looks = look
        for key in keys:
            if status[key] is not Verdict.UNDECIDED:
                continue
            s = sum(successes[key][:n])
            lo, hi = clopper_pearson(s, n, alpha)
            frozen[key] = (s, n, lo, hi)
            if lo >= 1.0 - params.eps_dispatch:
                status[key] = Verdict.FEASIBLE
            elif hi < 1.0 - params.eps_dispatch:
                status[key] = Verdict.INFEASIBLE
        if all(v is not Verdict.UNDECIDED for v in status.values()):
            break
        target *= 2
    certificates = []
    for key in keys:
        s, m, lo, hi = frozen.get(key, (0, 0, 0.0, 1.0))
        used = utilities[key][:m]
        certificates.append(
            CandidateCertificate(
                action_key=key,
                verdict=status[key],
                successes=s,
                n=m,
                lower=lo,
                upper=hi,
                mean_utility=sum(used) / len(used) if used else 0.0,
                outcome_counts=dict(Counter(outcomes[key][:m])),
            )
        )
    feasible = [key for key in keys if status[key] is Verdict.FEASIBLE]
    chosen = (
        paired_argmax(feasible, {k: utilities[k][:completed_n] for k in feasible})
        if feasible
        else HOLD_KEY
    )
    return CertificationResult(
        root=getattr(futures, "root", ""),
        params_id=params.params_id,
        a_max=futures.A_MAX,
        looks=looks,
        n_final=completed_n,
        elapsed_ms=(clock() - start) * 1000.0,
        deadline_hit=deadline_hit,
        candidates=tuple(certificates),
        chosen_key=chosen,
    )
