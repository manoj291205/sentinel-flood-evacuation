"""Create Phase 9 aggregate learning and semantic-permutation artifacts."""

from __future__ import annotations

from src.training_v3.reporting import finalize_training_artifacts


if __name__ == "__main__":
    summary = finalize_training_artifacts()
    print("representative seed", summary["representative_seed"])
    print("across-seed validation", summary["across_seed"]["validation_return"])
