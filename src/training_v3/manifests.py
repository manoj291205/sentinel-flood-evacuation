"""Frozen Phase 9 validation and permutation-manifest construction."""

from __future__ import annotations

from typing import Any

from .config import (
    PERMUTATION_DIAGNOSTIC_VERSION,
    TRAINING_SPEC_VERSION,
    VALIDATION_GENERATOR_SEEDS,
    VALIDATION_GENERATOR_VERSION,
)
from .generator import UNCERTAINTY_IDS, generate_ppo_scenario


def validation_manifest() -> dict[str, Any]:
    entries = []
    for index, seed in enumerate(VALIDATION_GENERATOR_SEEDS):
        generated = generate_ppo_scenario(
            seed,
            generator_version=VALIDATION_GENERATOR_VERSION,
            uncertainty_config_id=UNCERTAINTY_IDS[index % len(UNCERTAINTY_IDS)],
        )
        entries.append(generated.manifest_entry(index))
    return {
        "training_spec_version": TRAINING_SPEC_VERSION,
        "generator_version": VALIDATION_GENERATOR_VERSION,
        "number_of_scenarios": len(entries),
        "use": "checkpoint selection and learning-curve monitoring only; not Phase 10 test",
        "uncertainty_counts": {
            "LOW": 50,
            "MEDIUM": 50,
            "HIGH": 50,
        },
        "entries": entries,
    }


def permutation_manifest() -> dict[str, Any]:
    base_indices = list(range(30))
    return {
        "training_spec_version": TRAINING_SPEC_VERSION,
        "diagnostic_version": PERMUTATION_DIAGNOSTIC_VERSION,
        "base_validation_indices": base_indices,
        "permutations_per_base": 5,
        "paired_variants": len(base_indices) * 5,
        "permutation_seeds": {
            str(index): [950_000 + index * 5 + offset for offset in range(5)]
            for index in base_indices
        },
        "dynamics": (
            "deterministic diagnostic transform of each scenario's frozen uncertainty "
            "configuration; random innovations, closures, degradation, and travel noise "
            "are zeroed so semantic IDs are the only changed input"
        ),
        "alarm": {
            "median_absolute_normalized_episode_return_difference": 0.05,
            "mean_absolute_safe_population_difference": 0.05,
            "conditioned_slot_selection_bias": "report qualitatively and flag if large/systematic",
            "label": "POTENTIAL_SLOT_SHORTCUT",
        },
    }
