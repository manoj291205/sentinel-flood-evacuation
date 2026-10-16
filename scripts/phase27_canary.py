"""Phase 27 canary: prove this machine reproduces the reference results exactly.

    python scripts/phase27_canary.py

Re-runs five episodes already finished on the reference laptop (A, A2, HOLD on medium; P-noFC on stress;
Baseline B on high) and compares every field with data/eval_results/phase27/canary_expected.json.
Prints CANARY PASS (exit 0) only if all five match exactly; otherwise CANARY FAIL and the differing fields.
Writes nothing into data/eval_results/phase27/runs/. Takes about 10-25 minutes.
"""

from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import phase27_run as runner  # noqa: E402

EXPECTED = ROOT / "data/eval_results/phase27/canary_expected.json"
IGNORED = {"wall_seconds", "attempts"}


def run(task):
    return runner.run_episode(task)


def main() -> int:
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))["episodes"]
    tasks = [(e["system"], e["regime"], e["seed"]) for e in expected]
    started = time.perf_counter()
    print(f"running {len(tasks)} canary episodes (about 10-25 minutes)...", flush=True)
    with Pool(len(tasks), initializer=runner._init) as pool:
        results = pool.map(run, tasks)
    ok = True
    for want, got in zip(expected, results):
        diffs = [k for k in sorted(set(want) | set(got) - IGNORED)
                 if k not in IGNORED and want.get(k) != got.get(k)]
        label = f"{want['system']:8s} {want['regime']:18s} {want['seed']}"
        if diffs:
            ok = False
            print(f"FAIL {label}: " + ", ".join(f"{k} expected {want.get(k)!r} got {got.get(k)!r}" for k in diffs))
        else:
            print(f"ok   {label}")
    print(f"{'CANARY PASS' if ok else 'CANARY FAIL'} in {round(time.perf_counter() - started)} s")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
