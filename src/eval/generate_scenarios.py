"""Generate a held-out evaluation suite of scenarios.

WHY THIS EXISTS
===============
Every claim the prototype makes rests on ONE hand-built scenario that was deliberately
tuned so the constraint step would look decisive (S1's capacity was raised specifically
to make it the most attractive AND unsafe option). That is fine for a demo and useless as
evidence.

This module generates a suite so those claims can be measured instead of asserted.

NOT RIGGED -- the generation distribution is declared below and deliberately includes
cases where the constraint layer adds NOTHING, and cases where NO shelter is safe. A
suite that only contains flattering cases would be worse than no suite at all.

This is a DIFFERENT thing from the training-time perturbation in shelter_env.py: that one
jitters the demo scenario to give the policy something to learn. This one is a held-out
evaluation set with a fixed seed, committed so results are reproducible.

Run:  .venv/bin/python -m src.eval.generate_scenarios
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = PROJECT_ROOT / "data" / "eval_scenarios.json"

N_SCENARIOS = 60
SEED = 20260902
N_SHELTERS = 7
GRID_ROWS, GRID_COLS = 3, 3

# --- the declared generation distribution ----------------------------------------------
# Written out explicitly so a reader can judge whether the suite is fair, rather than
# taking the results on trust.
DISTRIBUTION = {
    "population_to_evacuate": "uniform integer 300-1200",
    "flood_severity_per_cell": (
        "uniform 0.0-1.0, independent per cell -- NOT a gradient, so shelter safety is "
        "uncorrelated with distance except by chance"
    ),
    "capacity_total": "uniform integer 150-1300",
    "current_occupancy": "uniform 0-100% of capacity",
    "travel_cost_minutes": "uniform integer 5-45",
    "status": "operational 80%, at_capacity 8%, closed_structural_damage 12%",
    "deliberate_edge_cases": (
        "the suite is post-filtered ONLY to guarantee coverage of three regimes: "
        "scenarios where every shelter is unsafe, scenarios where every shelter is safe, "
        "and scenarios where the constraint layer changes nothing. It is NOT filtered to "
        "favour scenarios where the constraint layer helps."
    ),
}

SEVERITY_BANDS = [
    (0.70, "severe"),
    (0.55, "high"),
    (0.30, "moderate"),
    (0.10, "low"),
    (0.00, "minimal"),
]


def band_for(severity: float) -> str:
    for threshold, name in SEVERITY_BANDS:
        if severity >= threshold:
            return name
    return "minimal"


def make_scenario(rng: np.random.Generator, index: int) -> dict:
    """One scenario in the same schema as data/scenario.json."""
    cells = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            severity = round(float(rng.uniform(0.0, 1.0)), 2)
            cells.append(
                {
                    "cell_id": f"C{row * GRID_COLS + col + 1}",
                    "row": row,
                    "col": col,
                    "descriptor": "generated evaluation cell",
                    "flood_severity": severity,
                    "severity_band": band_for(severity),
                }
            )

    # The source is the most-flooded cell; shelters occupy the others.
    source_cell = max(cells, key=lambda c: c["flood_severity"])
    other_cells = [c for c in cells if c["cell_id"] != source_cell["cell_id"]]
    chosen_cells = list(rng.choice(len(other_cells), size=N_SHELTERS, replace=False))

    shelters = []
    for slot, cell_index in enumerate(chosen_cells, start=1):
        capacity = int(rng.integers(150, 1301))
        occupancy = int(capacity * rng.uniform(0.0, 1.0))
        draw = rng.random()
        if draw < 0.08:
            status = "at_capacity"
            occupancy = capacity
        elif draw < 0.20:
            status = "closed_structural_damage"
        else:
            status = "operational"
        shelters.append(
            {
                "shelter_id": f"S{slot}",
                "cell_id": other_cells[int(cell_index)]["cell_id"],
                "capacity_total": capacity,
                "current_occupancy": occupancy,
                "status": status,
                "travel_cost_minutes": int(rng.integers(5, 46)),
            }
        )

    return {
        "_disclaimer": (
            "GENERATED EVALUATION SCENARIO. Fully synthetic, produced by "
            "src/eval/generate_scenarios.py for measurement purposes. Not real data of "
            "any kind, and not inspired by any specific real event."
        ),
        "scenario_id": f"eval-{index:03d}",
        "schema_version": 1,
        "hazard_model": {
            "severity_scale": "0.0-1.0, 0.0 dry, 1.0 fully inundated",
            "note": "Severity drawn independently per cell -- no gradient.",
        },
        "grid": {"rows": GRID_ROWS, "cols": GRID_COLS, "cells": cells},
        "source": {
            "cell_id": source_cell["cell_id"],
            "population_to_evacuate": int(rng.integers(300, 1201)),
            "note": "Most-flooded cell. Generated.",
        },
        "shelters": shelters,
    }


def regime_of(scenario: dict) -> str:
    """Which coverage regime a scenario falls into, by the deterministic safety rule."""
    from ..env.shelter_env import proxy_exclusion_rule
    from ..constraints.generate import shelter_facts

    unsafe = [proxy_exclusion_rule(f) for f in shelter_facts(scenario)]
    if all(unsafe):
        return "no_safe_shelter"
    if not any(unsafe):
        return "all_safe"
    return "mixed"


def main() -> int:
    rng = np.random.default_rng(SEED)
    scenarios: list[dict] = []
    counts = {"mixed": 0, "all_safe": 0, "no_safe_shelter": 0}

    # Generate until we have N, guaranteeing at least a few of each regime so the suite
    # covers the cases where our layer does nothing as well as where it does.
    attempts = 0
    while len(scenarios) < N_SCENARIOS and attempts < N_SCENARIOS * 200:
        attempts += 1
        candidate = make_scenario(rng, len(scenarios))
        regime = regime_of(candidate)

        remaining = N_SCENARIOS - len(scenarios)
        # Reserve slots near the end for under-represented regimes.
        if remaining <= 8:
            need = [r for r, c in counts.items() if c < 4]
            if need and regime not in need:
                continue

        candidate["_regime"] = regime
        scenarios.append(candidate)
        counts[regime] += 1

    payload = {
        "_note": (
            "Held-out evaluation suite. Fully synthetic and generated from a fixed seed, "
            "so these results are reproducible. The generation distribution is declared "
            "in '_distribution' below so a reader can judge whether the suite is fair. "
            "It is deliberately NOT filtered to favour scenarios where the constraint "
            "layer helps."
        ),
        "_seed": SEED,
        "_distribution": DISTRIBUTION,
        "_regime_counts": counts,
        "scenarios": scenarios,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Generated {len(scenarios)} scenarios (seed {SEED}) -> {OUTPUT_PATH.name}")
    print(f"  attempts needed: {attempts}")
    print("\nCoverage by regime (per the deterministic safety rule):")
    for regime, count in sorted(counts.items()):
        print(f"  {regime:<18} {count:>3}  ({count / len(scenarios) * 100:.0f}%)")
    print(
        "\n'all_safe' and 'no_safe_shelter' are the regimes where the constraint layer\n"
        "cannot help. They are included on purpose."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
