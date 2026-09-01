"""The safety-critical invariant: an excluded shelter must never be selectable.

This is the property the whole project rests on. If it can be violated, the citations and
the dashboard are decoration.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.env.shelter_env import ShelterChoiceEnv


def test_action_masks_matches_mask():
    env = ShelterChoiceEnv(randomise=True, seed=0)
    for episode in range(50):
        env.reset(seed=episode)
        assert np.array_equal(env.action_masks(), env.mask)


def test_mask_is_never_entirely_empty():
    """An empty mask would leave the agent with no legal action at all."""
    env = ShelterChoiceEnv(randomise=True, seed=1)
    for episode in range(300):
        env.reset(seed=episode)
        assert env.mask.any(), f"episode {episode} produced an empty action mask"


def test_best_allowed_index_is_always_allowed():
    env = ShelterChoiceEnv(randomise=True, seed=2)
    for episode in range(200):
        env.reset(seed=episode)
        assert env.mask[env.best_allowed_index()]


def test_best_allowed_ignores_higher_scoring_excluded_shelters():
    """The oracle must not be tempted by an excluded shelter, however good it looks."""
    env = ShelterChoiceEnv(randomise=True, seed=3)
    for episode in range(200):
        env.reset(seed=episode)
        best = env.best_allowed_index()
        excluded = np.flatnonzero(~env.mask)
        if excluded.size and env.rewards[excluded].max() > env.rewards[best]:
            # An excluded shelter scores higher -- exactly the S1 case. Still not chosen.
            assert env.mask[best]


def test_selecting_a_masked_action_is_penalised():
    """Defensive: unreachable under MaskablePPO, but a masking bug must be loud."""
    env = ShelterChoiceEnv(randomise=True, seed=4)
    for episode in range(100):
        env.reset(seed=episode)
        excluded = np.flatnonzero(~env.mask)
        if excluded.size:
            _, reward, terminated, _, info = env.step(int(excluded[0]))
            assert reward < 0
            assert terminated
            assert info["allowed"] is False
            return
    pytest.skip("no excluded shelter appeared in 100 episodes")


def test_constraint_payload_mask_is_honoured():
    payload = {
        "scenario_id": "x",
        "constraints": [
            {"action_id": f"S{i}", "status": "excluded" if i != 4 else "allowed"}
            for i in range(1, 8)
        ],
    }
    env = ShelterChoiceEnv(randomise=False, constraint_payload=payload)
    env.reset()
    assert env.mask.tolist() == [False, False, False, True, False, False, False]
    assert env.shelter_ids[env.best_allowed_index()] == "S4"


def test_episode_is_single_step():
    """DEVELOPMENT.md fixes this as a single-decision task."""
    env = ShelterChoiceEnv(randomise=True, seed=5)
    env.reset(seed=0)
    _, _, terminated, truncated, _ = env.step(env.best_allowed_index())
    assert terminated and not truncated
