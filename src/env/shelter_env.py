"""Single-decision Gymnasium environment for evacuation shelter choice.

Per DEVELOPMENT.md this is a contextual-bandit-style task, NOT a multi-step city simulation:
one action per candidate shelter, exactly one step per episode. Deliberately small so
training finishes in minutes.

Excluded shelters are made STRUCTURALLY UNSELECTABLE through `action_masks()`, which
MaskablePPO consumes -- they are not merely discouraged with a penalty.

=======================================================================================
IMPORTANT SIMPLIFICATION -- read before describing this system to anyone
=======================================================================================
The action mask has two different sources depending on what you are doing:

  * TRAINING (`randomise=True`): the mask comes from `proxy_exclusion_rule()`, a small
    deterministic rule. Training runs tens of thousands of episodes; calling the Gemini
    API once per episode would be neither free nor fast, and DEVELOPMENT.md forbids paid
    usage. The proxy imitates the KIND of exclusions the LLM makes (severe flooding,
    no headroom, not operational) -- it is NOT the LLM, and it is not derived from the
    NDMA documents.

  * DEMO / INFERENCE (`randomise=False` with `constraint_payload=...`): the mask comes
    from the REAL Step 3 Gemini output, grounded in real NDMA guideline text.

So the LLM constraint step does not run inside the training loop. Do not describe the
policy as "trained against LLM-generated constraints".
=======================================================================================
"""

from __future__ import annotations

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:  # pragma: no cover
    raise ImportError("gymnasium is required: pip install gymnasium") from exc

from ..constraints.generate import load_scenario, shelter_facts

# Reward weights. Fit is capped at 1.0, so extra space beyond "can take everyone" earns
# nothing and travel cost breaks the tie between shelters that both fit.
WEIGHT_FIT = 0.65
WEIGHT_TRAVEL = 0.35

FEATURES_PER_SHELTER = 4  # severity, headroom ratio, travel norm, allowed flag

# Thresholds for the TRAINING-ONLY proxy rule (see the module docstring).
PROXY_SEVERITY_LIMIT = 0.70  # the 'severe' band in data/scenario.json
PROXY_MIN_HEADROOM = 1


def proxy_exclusion_rule(fact: dict) -> bool:
    """TRAINING ONLY. True if this shelter should be masked out.

    A deterministic stand-in for the LLM constraint step, used because the real step
    cannot be called once per training episode. Not derived from the NDMA documents.
    """
    if fact["status"] != "operational":
        return True
    if fact["flood_severity"] >= PROXY_SEVERITY_LIMIT:
        return True
    if fact["capacity_headroom"] < PROXY_MIN_HEADROOM:
        return True
    return False


def compute_rewards(facts: list[dict], population: int) -> np.ndarray:
    """Reward for choosing each shelter, ignoring whether it is allowed.

    fit          = min(headroom / population, 1.0)
    travel_score = 1 - normalised travel cost
    reward       = 0.65 * fit + 0.35 * travel_score
    """
    headroom = np.array([f["capacity_headroom"] for f in facts], dtype=np.float32)
    travel = np.array([f["travel_cost_minutes"] for f in facts], dtype=np.float32)

    fit = np.clip(headroom / float(population), 0.0, 1.0)

    span = float(travel.max() - travel.min())
    if span <= 0:  # every shelter equidistant -- travel carries no information
        travel_score = np.ones_like(travel)
    else:
        travel_score = 1.0 - (travel - travel.min()) / span

    return (WEIGHT_FIT * fit + WEIGHT_TRAVEL * travel_score).astype(np.float32)


class ShelterChoiceEnv(gym.Env):
    """Pick one shelter for the evacuees. One decision, one step, episode over."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        randomise: bool = True,
        constraint_payload: dict | None = None,
        seed: int | None = None,
        scenario: dict | None = None,
    ):
        """`scenario` defaults to data/scenario.json; pass a dict to evaluate another one."""
        super().__init__()
        self.scenario = scenario if scenario is not None else load_scenario()
        self.base_facts = shelter_facts(self.scenario)
        self.population = self.scenario["source"]["population_to_evacuate"]
        self.randomise = randomise
        self.shelter_ids = [f["shelter_id"] for f in self.base_facts]
        self.n = len(self.base_facts)

        # A fixed mask from the real Step 3 output, used for demo/inference.
        self.fixed_mask: np.ndarray | None = None
        if constraint_payload is not None:
            self.fixed_mask = self._mask_from_constraints(constraint_payload)

        self.action_space = spaces.Discrete(self.n)
        self.observation_space = spaces.Box(
            low=0.0, high=np.inf, shape=(self.n * FEATURES_PER_SHELTER,), dtype=np.float32
        )

        self._rng = np.random.default_rng(seed)
        self.facts: list[dict] = []
        self.mask: np.ndarray = np.ones(self.n, dtype=bool)
        self.rewards: np.ndarray = np.zeros(self.n, dtype=np.float32)

    def _mask_from_constraints(self, payload: dict) -> np.ndarray:
        """Boolean allowed-vector from a Step 3 constraint payload, ordered like shelters."""
        status = {c["action_id"]: c["status"] for c in payload["constraints"]}
        return np.array(
            [status.get(sid) == "allowed" for sid in self.shelter_ids], dtype=bool
        )

    def _perturb(self) -> list[dict]:
        """Draw a fresh scenario so the policy learns the trade-off, not slot identities.

        Every attribute is drawn INDEPENDENTLY per shelter rather than scaled from that
        slot's values in the demo scenario.

        This matters, and it was found by measurement rather than by inspection. The
        first version scaled each attribute from `base` and kept `status = base["status"]`.
        Because S6 is `at_capacity` and S7 is `closed_structural_damage` in the demo
        scenario, those two slots were masked out in EVERY training episode -- so the
        policy learned "slots 6 and 7 are never available" as a positional prior and
        never selected them even when they were allowed. On a held-out suite it picked
        S6/S7 zero times out of 60 where the oracle picked them 17 times, and scored 45%
        optimal against the oracle's 93%.

        Drawing independently removes any stable slot identity, so the policy has to read
        the features. The ranges match the family used by src/eval/generate_scenarios.py;
        the evaluation instances themselves are generated from a different seed and are
        never trained on.
        """
        facts = []
        for base in self.base_facts:
            capacity = int(self._rng.integers(150, 1301))
            occupancy = int(capacity * self._rng.uniform(0.0, 1.0))
            severity = round(float(self._rng.uniform(0.0, 1.0)), 2)
            travel = float(self._rng.integers(5, 46))

            draw = self._rng.random()
            if draw < 0.08:
                status = "at_capacity"
                occupancy = capacity
            elif draw < 0.20:
                status = "closed_structural_damage"
            else:
                status = "operational"

            facts.append(
                {
                    "shelter_id": base["shelter_id"],
                    "cell_id": base["cell_id"],
                    "flood_severity": severity,
                    "capacity_total": capacity,
                    "current_occupancy": occupancy,
                    "capacity_headroom": capacity - occupancy,
                    "status": status,
                    "travel_cost_minutes": travel,
                }
            )
        return facts

    def _observation(self) -> np.ndarray:
        travel = np.array([f["travel_cost_minutes"] for f in self.facts], dtype=np.float32)
        span = float(travel.max() - travel.min()) or 1.0
        rows = []
        for index, fact in enumerate(self.facts):
            rows.append(
                [
                    fact["flood_severity"],
                    min(fact["capacity_headroom"] / float(self.population), 2.0),
                    (fact["travel_cost_minutes"] - travel.min()) / span,
                    1.0 if self.mask[index] else 0.0,
                ]
            )
        return np.array(rows, dtype=np.float32).flatten()

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        if seed is not None:
            self._rng = np.random.default_rng(seed)

        self.facts = self._perturb() if self.randomise else [dict(f) for f in self.base_facts]

        if self.fixed_mask is not None and not self.randomise:
            self.mask = self.fixed_mask.copy()
        else:
            self.mask = np.array(
                [not proxy_exclusion_rule(f) for f in self.facts], dtype=bool
            )

        # Never hand the agent an episode with nothing to pick; keep the least-bad option.
        if not self.mask.any():
            self.mask[int(np.argmin([f["flood_severity"] for f in self.facts]))] = True

        self.rewards = compute_rewards(self.facts, self.population)
        return self._observation(), {}

    def action_masks(self) -> np.ndarray:
        """Consumed by MaskablePPO to make excluded shelters structurally unselectable."""
        return self.mask.copy()

    def step(self, action: int):
        action = int(action)
        if not self.mask[action]:
            # Unreachable under MaskablePPO; defensive only, so a masking bug is loud.
            reward = -1.0
        else:
            reward = float(self.rewards[action])

        best = self.best_allowed_index()
        info = {
            "shelter_id": self.shelter_ids[action],
            "allowed": bool(self.mask[action]),
            "optimal_index": best,
            "optimal_shelter_id": self.shelter_ids[best],
            "optimal_reward": float(self.rewards[best]),
            "regret": float(self.rewards[best] - reward),
        }
        return self._observation(), reward, True, False, info

    def best_allowed_index(self) -> int:
        """Index of the highest-reward ALLOWED shelter -- the oracle choice."""
        masked = np.where(self.mask, self.rewards, -np.inf)
        return int(np.argmax(masked))
