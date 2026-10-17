"""Write the one-time exploratory network-outage count ledger from real futures."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.escrow.outage import simulate_outage  # noqa: E402

OUT = ROOT / "data" / "eval_results" / "phase35lite" / "outages.json"
SCHEMA = ROOT / "specs" / "contracts" / "phase35lite_result.schema.json"
FIRST_SEED = 1_070_000
SEEDS = 40
MODES = ("escrow", "last_known")


def _run(item: tuple[int, str]) -> dict:
    seed, mode = item
    report = simulate_outage(seed, "v4-medium-dt2-v1", 2 + seed % 5, 2, mode)
    return {
        "seed": seed, "mode": mode, "cut_step": report.cut_step,
        "free_at_cut": sum(report.free_at_cut.values()),
        "reserved_offline": sum(report.reserved_offline.values()),
        "overbooked_seats": report.overbooked_seats, "overbooked": report.overbooked,
        "blocked": len(report.blocked), "returned_to_pool": report.returned_to_pool,
        "dispatches_offline": sum(item["certificate"]["kind"] == "DISPATCH"
                                  for item in report.certificates),
    }


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"Refusing to overwrite {OUT}")
    work = [(seed, mode) for seed in range(FIRST_SEED, FIRST_SEED + SEEDS) for mode in MODES]
    with ProcessPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(_run, work))
    payload = {
        "schema": "phase35lite-outages-v1", "exploratory": True, "not_preregistered": True,
        "config": {
            "world_id": "v4-medium-dt2-v1", "params_id": "v4-cert-test-v1",
            "first_seed": FIRST_SEED, "seeds": SEEDS, "rounds": 2,
            "cut_step_rule": "2 + (seed % 5)", "modes": list(MODES),
        },
        "rows": rows,
        "totals": {
            "outages": SEEDS,
            "overbooked_outages_escrow": sum(row["overbooked"] for row in rows if row["mode"] == "escrow"),
            "overbooked_outages_last_known": sum(row["overbooked"] for row in rows if row["mode"] == "last_known"),
            "overbooked_seats_escrow": sum(row["overbooked_seats"] for row in rows if row["mode"] == "escrow"),
            "overbooked_seats_last_known": sum(row["overbooked_seats"] for row in rows if row["mode"] == "last_known"),
            "blocked_escrow": sum(row["blocked"] for row in rows if row["mode"] == "escrow"),
        },
    }
    import jsonschema

    jsonschema.validate(payload, json.loads(SCHEMA.read_text(encoding="utf-8")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["totals"], sort_keys=True))


if __name__ == "__main__":
    main()
