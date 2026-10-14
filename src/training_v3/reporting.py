"""Aggregate frozen Phase 9 artifacts and draw dependency-free SVG learning curves."""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from sb3_contrib import MaskablePPO

from .config import FROZEN_TRAINING_CONFIG, PRIMARY_TRAINING_SEEDS, representative_seed
from .evaluation import run_permutation_diagnostic
from .training import DATA_DIR, MODEL_DIR, model_metadata


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metric_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "std": statistics.pstdev(values),
        "min": min(values),
        "max": max(values),
    }


def _learning_rows(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    individual = []
    aggregate = []
    for index in range(len(results[0]["validation_history"])):
        timestep = results[0]["validation_history"][index]["training_timestep"]
        for result in results:
            row = result["validation_history"][index]
            if row["training_timestep"] != timestep:
                raise RuntimeError("seed learning curves use different timesteps")
            individual.append(
                {
                    "timestep": timestep,
                    "seed": result["training_seed"],
                    "validation_return": row["mean_episode_return"],
                    "safe_population_fraction": row["mean_safe_population_fraction"],
                    "exposure": row["mean_exposure"],
                }
            )
        same_time = [row for row in individual if row["timestep"] == timestep]
        aggregate.append(
            {
                "timestep": timestep,
                "mean_validation_return": statistics.fmean(
                    row["validation_return"] for row in same_time
                ),
                "std_validation_return": statistics.pstdev(
                    row["validation_return"] for row in same_time
                ),
                "mean_safe_population_fraction": statistics.fmean(
                    row["safe_population_fraction"] for row in same_time
                ),
                "std_safe_population_fraction": statistics.pstdev(
                    row["safe_population_fraction"] for row in same_time
                ),
                "mean_exposure": statistics.fmean(row["exposure"] for row in same_time),
                "std_exposure": statistics.pstdev(row["exposure"] for row in same_time),
            }
        )
    return individual, aggregate


def _write_learning_csv(individual: list[dict[str, Any]], aggregate: list[dict[str, Any]]) -> None:
    aggregate_by_timestep = {row["timestep"]: row for row in aggregate}
    rows = []
    for row in individual:
        combined = dict(row)
        combined.update(aggregate_by_timestep[row["timestep"]])
        rows.append(combined)
    with (DATA_DIR / "learning_curves.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _svg_learning_curves(individual: list[dict[str, Any]], aggregate: list[dict[str, Any]]) -> None:
    width, height = 1000, 850
    left, right, panel_height = 90, 970, 210
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c"]
    panels = [
        ("validation_return", "Validation return", 65),
        ("safe_population_fraction", "Safe-population fraction", 320),
        ("exposure", "Cumulative normalized exposure", 575),
    ]
    by_seed = {
        seed: [row for row in individual if row["seed"] == seed]
        for seed in PRIMARY_TRAINING_SEEDS
    }
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="500" y="28" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="bold">Phase 9 validation learning curves — all five primary seeds</text>',
    ]
    min_x = min(row["timestep"] for row in individual)
    max_x = max(row["timestep"] for row in individual)
    for metric, title, top in panels:
        values = [float(row[metric]) for row in individual]
        low, high = min(values), max(values)
        pad = max((high - low) * 0.12, 1e-6)
        low -= pad
        high += pad

        def point(timestep: int, value: float) -> tuple[float, float]:
            x = left + (timestep - min_x) / (max_x - min_x) * (right - left)
            y = top + panel_height - (value - low) / (high - low) * panel_height
            return x, y

        pieces.extend(
            [
                f'<text x="{left}" y="{top - 12}" font-family="sans-serif" font-size="15" font-weight="bold">{title}</text>',
                f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + panel_height}" stroke="#555"/>',
                f'<line x1="{left}" y1="{top + panel_height}" x2="{right}" y2="{top + panel_height}" stroke="#555"/>',
                f'<text x="{left - 8}" y="{top + 5}" text-anchor="end" font-family="monospace" font-size="11">{high:.3f}</text>',
                f'<text x="{left - 8}" y="{top + panel_height}" text-anchor="end" font-family="monospace" font-size="11">{low:.3f}</text>',
            ]
        )
        for color, seed in zip(colors, PRIMARY_TRAINING_SEEDS):
            coords = " ".join(
                f"{x:.1f},{y:.1f}" for x, y in (point(row["timestep"], row[metric]) for row in by_seed[seed])
            )
            pieces.append(
                f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.3" opacity="0.55"/>'
            )
        aggregate_metric = {
            "validation_return": "mean_validation_return",
            "safe_population_fraction": "mean_safe_population_fraction",
            "exposure": "mean_exposure",
        }[metric]
        mean_coords = " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in (
                point(row["timestep"], row[aggregate_metric]) for row in aggregate
            )
        )
        pieces.append(
            f'<polyline points="{mean_coords}" fill="none" stroke="#111827" stroke-width="3"/>'
        )
        pieces.append(
            f'<text x="{right}" y="{top - 12}" text-anchor="end" font-family="sans-serif" font-size="11">thin: seeds; thick: mean</text>'
        )
    pieces.extend(
        [
            '<text x="530" y="838" text-anchor="middle" font-family="sans-serif" font-size="13">Training timesteps (10k–250k)</text>',
            '</svg>',
        ]
    )
    (DATA_DIR / "learning_curves.svg").write_text("\n".join(pieces) + "\n", encoding="utf-8")


def finalize_training_artifacts() -> dict[str, Any]:
    config = FROZEN_TRAINING_CONFIG
    results = [_read_json(DATA_DIR / f"seed_{seed}.json") for seed in PRIMARY_TRAINING_SEEDS]
    debug = _read_json(DATA_DIR / "debug_seed1101.json")
    debug_repeat = _read_json(DATA_DIR / "debug_repeat_seed1101.json")
    validation_manifest = _read_json(DATA_DIR / "validation_manifest.json")
    permutation_manifest = _read_json(DATA_DIR / "permutation_manifest.json")

    debug_deltas = []
    for left, right in zip(debug["validation_history"], debug_repeat["validation_history"]):
        debug_deltas.extend(
            abs(left[key] - right[key])
            for key in (
                "mean_episode_return",
                "mean_safe_population_fraction",
                "mean_exposure",
                "mean_travel",
                "mean_completion",
            )
        )
    reproducibility = {
        "same_seed": 1101,
        "timesteps_each": config.debug_timesteps,
        "maximum_absolute_validation_metric_difference": max(debug_deltas),
        "exact_validation_metrics_match": max(debug_deltas) == 0.0,
        "model_sha256_first": _sha256(MODEL_DIR / "debug_seed1101.zip"),
        "model_sha256_repeat": _sha256(MODEL_DIR / "debug_repeat_seed1101.zip"),
    }
    reproducibility["exact_model_bytes_match"] = (
        reproducibility["model_sha256_first"] == reproducibility["model_sha256_repeat"]
    )
    _write_json(MODEL_DIR / "debug_seed1101.metadata.json", model_metadata(debug, "debug"))
    _write_json(
        MODEL_DIR / "debug_repeat_seed1101.metadata.json",
        model_metadata(debug_repeat, "debug"),
    )

    permutation_by_seed = {}
    for seed in PRIMARY_TRAINING_SEEDS:
        model = MaskablePPO.load(MODEL_DIR / f"ppo_seed{seed}_best.zip", device="cpu")
        permutation_by_seed[str(seed)] = run_permutation_diagnostic(
            model, validation_manifest, permutation_manifest
        )
        print(
            f"permutation seed {seed}: equivalence="
            f"{permutation_by_seed[str(seed)]['mean_action_equivalence_rate']:.6f} "
            f"alarm={permutation_by_seed[str(seed)]['alarm']}"
        )
    all_pairs = [
        pair
        for seed in PRIMARY_TRAINING_SEEDS
        for pair in permutation_by_seed[str(seed)]["pairs"]
    ]
    permutation_summary = {
        "diagnostic_version": permutation_manifest["diagnostic_version"],
        "all_five_best_validation_models": True,
        "base_scenarios": 30,
        "permutations_per_base": 5,
        "paired_variants_per_model": 150,
        "total_paired_variants": 750,
        "aggregate": {
            "mean_action_equivalence_rate": statistics.fmean(
                pair["action_equivalence_rate"] for pair in all_pairs
            ),
            "mean_return_delta": statistics.fmean(pair["return_delta"] for pair in all_pairs),
            "median_absolute_normalized_return_delta": statistics.median(
                pair["absolute_normalized_return_delta"] for pair in all_pairs
            ),
            "mean_absolute_safe_population_delta": statistics.fmean(
                pair["absolute_safe_population_delta"] for pair in all_pairs
            ),
            "mean_exposure_delta": statistics.fmean(
                pair["exposure_delta"] for pair in all_pairs
            ),
        },
        "alarm": any(item["alarm"] for item in permutation_by_seed.values()),
        "alarm_label": "POTENTIAL_SLOT_SHORTCUT",
        "v1_comparison": {
            "v1_failure": "S6/S7 selected 0/0 times in 60 scenarios while oracle selected them 7/8; fixed statuses made those training slots permanently masked.",
            "v3_test": "Only semantic IDs change in paired deterministic physical scenarios; outcome and action-equivalence deltas are reported for every best seed.",
        },
        "by_seed": permutation_by_seed,
    }
    _write_json(DATA_DIR / "permutation_diagnostic.json", permutation_summary)

    individual, aggregate_curves = _learning_rows(results)
    _write_learning_csv(individual, aggregate_curves)
    _svg_learning_curves(individual, aggregate_curves)
    seed_rows = []
    for result in results:
        best = result["best_validation"]
        seed_rows.append(
            {
                "seed": result["training_seed"],
                "best_timestep": result["best_timestep"],
                "validation_return": best["mean_episode_return"],
                "safe_population_fraction": best["mean_safe_population_fraction"],
                "exposure": best["mean_exposure"],
                "completion": best["mean_completion"],
                "invalid_actions": best["invalid_actions"] + result["training_invalid_actions"],
                "wall_clock_seconds": result["wall_clock_seconds"],
                "timesteps_per_second": result["timesteps_per_second"],
            }
        )
    scores = {row["seed"]: row["validation_return"] for row in seed_rows}
    summary = {
        "training_spec_version": config.spec_version,
        "source_git_commit": results[0]["source_git_commit"],
        "primary_training_seeds": list(PRIMARY_TRAINING_SEEDS),
        "timesteps_per_seed": config.total_timesteps,
        "total_primary_timesteps": config.total_timesteps * len(PRIMARY_TRAINING_SEEDS),
        "validation_scenarios": config.validation_scenarios,
        "seed_results": seed_rows,
        "across_seed": {
            "validation_return": _metric_summary([row["validation_return"] for row in seed_rows]),
            "safe_population_fraction": _metric_summary([row["safe_population_fraction"] for row in seed_rows]),
            "exposure": _metric_summary([row["exposure"] for row in seed_rows]),
            "completion": _metric_summary([row["completion"] for row in seed_rows]),
        },
        "representative_seed": representative_seed(scores),
        "training_invalid_actions": sum(row["invalid_actions"] for row in seed_rows),
        "debug": {
            "status": debug["result_status"],
            "timesteps": debug["requested_and_actual_timesteps"],
            "invalid_actions": debug["training_invalid_actions"],
            "reward_min": debug["training_reward_min"],
            "reward_max": debug["training_reward_max"],
            "best_validation": debug["best_validation"],
            "save_load_verified": True,
            "deterministic_inference_verified": True,
            "reproducibility": reproducibility,
        },
        "compute": {
            "device": "cpu",
            "per_seed": {
                str(row["seed"]): {
                    "wall_clock_seconds": row["wall_clock_seconds"],
                    "timesteps_per_second": row["timesteps_per_second"],
                }
                for row in seed_rows
            },
            "sum_process_wall_clock_seconds": sum(row["wall_clock_seconds"] for row in seed_rows),
            "approximate_peak_memory": "not measured",
            "note": "Seeds 2202/3303 and 4404/5505 ran as two concurrent CPU pairs; process wall times include shared-machine contention.",
        },
        "learning_curves": aggregate_curves,
        "permutation_diagnostic_file": "data/eval_v3/training/permutation_diagnostic.json",
        "claim_boundary": (
            "Training/validation results do not establish PPO superiority. Final "
            "comparison occurs only on the frozen Phase 10 held-out suite."
        ),
    }
    _write_json(DATA_DIR / "training_summary.json", summary)
    return summary
