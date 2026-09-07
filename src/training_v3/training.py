"""Exact-budget MaskablePPO training orchestration for frozen Phase 9."""

from __future__ import annotations

import csv
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import gymnasium
import numpy as np
import sb3_contrib
import stable_baselines3
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback

from .config import FROZEN_TRAINING_CONFIG, TRAINING_SPEC_VERSION
from .envs import make_training_vec_env
from .evaluation import checkpoint_rank, evaluate_validation


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "eval_v3" / "training"
MODEL_DIR = ROOT / "models" / "v3"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def software_metadata() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "Apple Silicon arm64",
        "logical_cpu_count": os.cpu_count(),
        "torch": torch.__version__,
        "gymnasium": gymnasium.__version__,
        "stable_baselines3": stable_baselines3.__version__,
        "sb3_contrib": sb3_contrib.__version__,
        "mps_available": torch.backends.mps.is_available(),
        "torch_threads": torch.get_num_threads(),
        "device": FROZEN_TRAINING_CONFIG.device,
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "exact_model_byte_reproducibility_guaranteed": False,
    }


class EpisodeDiagnostics(BaseCallback):
    """Collect per-episode physical diagnostics from vector-environment infos."""

    def __init__(self, n_envs: int) -> None:
        super().__init__(verbose=0)
        self.n_envs = n_envs
        self.episodes: list[dict[str, Any]] = []
        self._initialized = False

    def _on_training_start(self) -> None:
        if not self._initialized:
            self._returns = [0.0] * self.n_envs
            self._exposures = [0.0] * self.n_envs
            self._travels = [0.0] * self.n_envs
            self._safe = [0.0] * self.n_envs
            self._invalid = [0] * self.n_envs
            self._allowed: list[list[int]] = [[] for _ in range(self.n_envs)]
            self._wait_only = [0] * self.n_envs
            self._initialized = True

    def _on_step(self) -> bool:
        rewards = self.locals["rewards"]
        dones = self.locals["dones"]
        infos = self.locals["infos"]
        for rank, (reward, done, info) in enumerate(zip(rewards, dones, infos)):
            self._returns[rank] += float(reward)
            self._exposures[rank] += float(info["reward_exposure"])
            self._travels[rank] += float(info["reward_travel"])
            self._safe[rank] += float(info["reward_safe_gain"])
            self._invalid[rank] += int(info["invalid_action_attempted"])
            allowed = int(info["allowed_action_count_before"])
            self._allowed[rank].append(allowed)
            self._wait_only[rank] += int(allowed == 1)
            if done:
                self.episodes.append(
                    {
                        "training_timestep": int(self.num_timesteps),
                        "environment_rank": rank,
                        "scenario_id": info["scenario_id"],
                        "episode_return": self._returns[rank],
                        "exposure": self._exposures[rank],
                        "travel": self._travels[rank],
                        "safe_population_fraction": self._safe[rank],
                        "completion": float(info["evacuation_complete"]),
                        "invalid_actions": self._invalid[rank],
                        "mean_allowed_actions": (
                            float(np.mean(self._allowed[rank])) if self._allowed[rank] else 0.0
                        ),
                        "minimum_allowed_actions": (
                            min(self._allowed[rank]) if self._allowed[rank] else 0
                        ),
                        "wait_only_timesteps": self._wait_only[rank],
                        "terminal_reason": info["terminal_reason"],
                    }
                )
                self._returns[rank] = 0.0
                self._exposures[rank] = 0.0
                self._travels[rank] = 0.0
                self._safe[rank] = 0.0
                self._invalid[rank] = 0
                self._allowed[rank] = []
                self._wait_only[rank] = 0
        return True


def build_model(training_seed: int, env) -> MaskablePPO:
    config = FROZEN_TRAINING_CONFIG
    return MaskablePPO(
        config.policy,
        env,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        n_epochs=config.n_epochs,
        gamma=config.gamma,
        gae_lambda=config.gae_lambda,
        clip_range=config.clip_range,
        ent_coef=config.ent_coef,
        vf_coef=config.vf_coef,
        max_grad_norm=config.max_grad_norm,
        policy_kwargs={"net_arch": list(config.net_arch), "activation_fn": torch.nn.ReLU},
        seed=training_seed,
        device=config.device,
        verbose=0,
    )


def _finite_logger_values(model) -> dict[str, float]:
    result = {}
    for name, value in model.logger.name_to_value.items():
        if isinstance(value, (int, float, np.number)):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise RuntimeError(f"non-finite training log value {name}={numeric}")
            result[name] = numeric
    return result


def _episode_csv(path: Path, episodes: list[dict[str, Any]]) -> None:
    fields = list(episodes[0]) if episodes else ["training_timestep"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(episodes)


def train_run(
    training_seed: int,
    *,
    total_timesteps: int,
    label: str,
    persist_best: bool,
) -> dict[str, Any]:
    config = FROZEN_TRAINING_CONFIG
    if total_timesteps % config.validation_interval:
        raise ValueError("training budget must align with frozen validation interval")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    validation_manifest = _read_json(DATA_DIR / "validation_manifest.json")
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(4)
    vec_env = make_training_vec_env(training_seed)
    diagnostics = EpisodeDiagnostics(config.n_envs)
    model = build_model(training_seed, vec_env)
    source_commit = _git_commit()
    validation_history = []
    best_rank = None
    best_timestep = None
    best_summary = None
    temporary = MODEL_DIR / f".{label}_checkpoint.zip"
    start = time.perf_counter()
    try:
        for timestep in range(config.validation_interval, total_timesteps + 1, config.validation_interval):
            model.learn(
                total_timesteps=config.validation_interval,
                callback=diagnostics,
                reset_num_timesteps=False,
                progress_bar=False,
            )
            if model.num_timesteps != timestep:
                raise RuntimeError(
                    f"exact budget failure: expected {timestep}, got {model.num_timesteps}"
                )
            training_logs = _finite_logger_values(model)
            model.save(temporary)
            summary, _ = evaluate_validation(model, validation_manifest)
            summary.update(
                {
                    "training_timestep": timestep,
                    "training_logs": training_logs,
                }
            )
            validation_history.append(summary)
            rank = checkpoint_rank(summary, timestep)
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best_timestep = timestep
                best_summary = summary
                if persist_best:
                    shutil.copyfile(
                        temporary,
                        MODEL_DIR / f"ppo_seed{training_seed}_best.zip",
                    )
            print(
                f"{label}: {timestep}/{total_timesteps} "
                f"validation={summary['mean_episode_return']:.6f} "
                f"safe={summary['mean_safe_population_fraction']:.6f}"
            )
        wall_seconds = time.perf_counter() - start
        final_path = MODEL_DIR / (
            f"ppo_seed{training_seed}_final.zip"
            if persist_best
            else f"{label}.zip"
        )
        model.save(final_path)
    finally:
        vec_env.close()
        if temporary.exists():
            temporary.unlink()
    assert best_summary is not None and best_timestep is not None
    invalid_training = sum(row["invalid_actions"] for row in diagnostics.episodes)
    if invalid_training:
        raise RuntimeError(f"masked training produced {invalid_training} invalid actions")
    result = {
        "label": label,
        "primary_result": persist_best,
        "training_seed": training_seed,
        "source_git_commit": source_commit,
        "training_spec_version": TRAINING_SPEC_VERSION,
        "requested_and_actual_timesteps": total_timesteps,
        "best_timestep": best_timestep,
        "best_validation": best_summary,
        "final_validation": validation_history[-1],
        "validation_history": validation_history,
        "training_episode_count": len(diagnostics.episodes),
        "training_invalid_actions": invalid_training,
        "training_reward_min": min(row["episode_return"] for row in diagnostics.episodes),
        "training_reward_max": max(row["episode_return"] for row in diagnostics.episodes),
        "wall_clock_seconds": wall_seconds,
        "timesteps_per_second": total_timesteps / wall_seconds,
        "software": software_metadata(),
        "config": config.to_dict(),
        "model_files": (
            {
                "best": f"models/v3/ppo_seed{training_seed}_best.zip",
                "final": f"models/v3/ppo_seed{training_seed}_final.zip",
            }
            if persist_best
            else {"debug": f"models/v3/{label}.zip"}
        ),
    }
    _episode_csv(DATA_DIR / f"{label}_episodes.csv", diagnostics.episodes)
    _write_json(DATA_DIR / f"{label}.json", result)
    return result


def model_metadata(result: dict[str, Any], kind: str) -> dict[str, Any]:
    config = FROZEN_TRAINING_CONFIG
    if kind == "best":
        checkpoint = result["best_timestep"]
        validation = result["best_validation"]
        artifact_kind = "BEST VALIDATION"
    elif kind == "final":
        checkpoint = result["requested_and_actual_timesteps"]
        validation = result["final_validation"]
        artifact_kind = "FINAL TIMESTEP"
    elif kind == "debug":
        checkpoint = result["requested_and_actual_timesteps"]
        validation = result["final_validation"]
        artifact_kind = "DEBUG — NOT A PRIMARY RESULT"
    else:
        raise ValueError(f"unknown model artifact kind {kind!r}")
    return {
        "artifact_kind": artifact_kind,
        "git_commit": result["source_git_commit"],
        "training_spec_version": TRAINING_SPEC_VERSION,
        "environment_config_id": "v3-env-v1",
        "reward_config_id": config.reward_config_id,
        "safety_config_id": config.safety_config_id,
        "training_seed": result["training_seed"],
        "software": result["software"],
        "total_training_timesteps": result["requested_and_actual_timesteps"],
        "checkpoint_timestep": checkpoint,
        "validation_score": validation["mean_episode_return"],
        "observation_dimension": config.observation_dim,
        "action_dimension": config.action_dim,
        "wall_clock_seconds": result["wall_clock_seconds"],
        "timesteps_per_second": result["timesteps_per_second"],
        "approximate_peak_memory": "not measured",
    }


def run_debug(label: str = "debug_seed1101") -> dict[str, Any]:
    result = train_run(
        1101,
        total_timesteps=FROZEN_TRAINING_CONFIG.debug_timesteps,
        label=label,
        persist_best=False,
    )
    result["result_status"] = "NOT A PRIMARY RESULT"
    _write_json(DATA_DIR / f"{label}.json", result)
    _write_json(MODEL_DIR / f"{label}.metadata.json", model_metadata(result, "debug"))
    return result


def run_primary(training_seed: int) -> dict[str, Any]:
    result = train_run(
        training_seed,
        total_timesteps=FROZEN_TRAINING_CONFIG.total_timesteps,
        label=f"seed_{training_seed}",
        persist_best=True,
    )
    for kind in ("best", "final"):
        _write_json(
            MODEL_DIR / f"ppo_seed{training_seed}_{kind}.metadata.json",
            model_metadata(result, kind),
        )
    return result
