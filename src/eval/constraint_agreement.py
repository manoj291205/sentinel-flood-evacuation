"""Is the LLM constraint step actually right, and does retrieval change what it says?

Two questions the prototype asserts answers to but never measured:

  D. AGREEMENT -- how often does the Gemini verdict match the deterministic safety rule?
     The two error types are reported SEPARATELY because they are not equally bad:
       false-allow    permitted an unsafe shelter        -> a SAFETY failure
       false-exclude  barred a usable shelter            -> a COST failure

  E. RAG ABLATION -- run the same scenarios with the retrieved NDMA excerpts REMOVED
     from the prompt. If the verdicts barely move, the retrieval layer is doing less
     than the project claims, and that needs saying.

The deterministic rule is the yardstick, not ground truth handed down from the NDMA text.
It encodes three uncontroversial conditions (severe flooding, no headroom, not
operational). Disagreement is informative in both directions and is reported, not
silently scored as LLM error.

Costs real free-tier quota. Results are cached per scenario so reruns are free.

Run:  .venv/bin/python -m src.eval.constraint_agreement            (uses cache)
      .venv/bin/python -m src.eval.constraint_agreement --refresh  (re-calls the API)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from ..constraints.generate import (
    ConstraintError,
    build_prompt,
    check_grounding,
    gather_context,
    generate_constraints,
    shelter_facts,
    validate,
)
from .baselines import is_unsafe

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = PROJECT_ROOT / "data" / "eval_scenarios.json"
RESULTS_DIR = PROJECT_ROOT / "data" / "eval_results"
CACHE_PATH = RESULTS_DIR / "constraint_agreement_cache.json"

# HARD FREE-TIER LIMIT, measured on 2026-09-02: gemini-3.6-flash allows
#   GenerateRequestsPerDayPerProjectPerModel-FreeTier = 20 requests PER DAY
# (not per minute). Each scenario costs 2 calls (with-retrieval + ablation), so at most
# 10 scenarios can be scored per day. The per-scenario cache below is what makes this
# survivable: rerun on later days and it resumes where it stopped.
N_SUBSET = 10
THROTTLE_SECONDS = 2.0
DAILY_REQUEST_BUDGET = 20

WIDTH = 88


def _retry_delay_from(exc: Exception) -> float | None:
    """Seconds Google says to wait, if the error carries a retryDelay."""
    match = re.search(r"'retryDelay': '(\d+)s'", str(exc))
    return float(match.group(1)) if match else None


def call_with_quota_retry(fn, *, label: str, budget_seconds: float = 900.0):
    """Run `fn`, waiting out 429s until the rolling quota frees a slot.

    MEASURED BEHAVIOUR, 2026-09-02: the cap really is a fixed daily budget of 20
    requests that resets at midnight Pacific -- NOT a rolling window whose slots free
    individually. Waiting it out does not work: a 15-minute grind against an exhausted
    budget freed zero slots, and the `retryDelay` the server returns (14s, then a flat
    ~59s) is a generic backoff hint, not a prediction of when capacity returns.

    So this retry is only worth anything for short-lived transient 429s. When the daily
    budget is genuinely spent, the budget below expires and the caller stops cleanly with
    everything cached -- resume after the next midnight Pacific.
    """
    waited = 0.0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - inspect, then re-raise if not a quota error
            if "RESOURCE_EXHAUSTED" not in str(exc) and "429" not in str(exc):
                raise
            delay = _retry_delay_from(exc)
            if delay is None:
                delay = 30.0
            delay += 3.0  # small buffer so we do not race the window
            if waited + delay > budget_seconds:
                raise
            print(f"    quota full on {label}; waiting {delay:.0f}s for a slot "
                  f"({waited + delay:.0f}s/{budget_seconds:.0f}s used)")
            time.sleep(delay)
            waited += delay


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def generate_without_retrieval(scenario: dict) -> dict:
    """Same call, but with NO guideline excerpts in the prompt.

    Implemented by passing an empty chunk list, so the prompt keeps its structure and
    only the evidence disappears -- the ablation isolates retrieval, not phrasing.
    """
    return generate_constraints(scenario, chunks=[], verbose=False)


def verdicts_of(payload: dict) -> dict[str, str]:
    return {c["action_id"]: c["status"] for c in payload["constraints"]}


def main() -> int:
    refresh = "--refresh" in sys.argv
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    scenarios = suite["scenarios"][:N_SUBSET]
    cache = {} if refresh else load_cache()

    grounded_tally = {"tp": 0, "tn": 0, "false_allow": 0, "false_exclude": 0}
    ablated_tally = {"tp": 0, "tn": 0, "false_allow": 0, "false_exclude": 0}
    verdict_flips = 0
    total_shelters = 0
    cited_verbatim_grounded = 0
    cited_verbatim_ablated = 0
    failures: list[str] = []
    quota_stop = False
    scored = 0

    print(f"Scoring {len(scenarios)} scenarios "
          f"({'live API calls' if refresh or not cache else 'cache where available'})...\n")

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        entry = cache.get(sid)

        if entry is None:
            # Each arm fails independently: a broken ablation must not discard a good
            # RAG result, and vice versa.
            try:
                with_rag = call_with_quota_retry(
                    lambda: generate_constraints(scenario, verbose=False),
                    label=f"{sid} with-rag")
                time.sleep(THROTTLE_SECONDS)
            except ConstraintError as exc:
                print(f"  {sid}: RAG arm FAILED — {str(exc)[:90]}")
                failures.append(f"{sid}:with_rag")
                continue
            except Exception as exc:  # noqa: BLE001 - API/quota errors must not lose work
                print(f"\n  {sid}: API error, stopping and keeping what is cached.")
                print(f"  {str(exc)[:200]}")
                quota_stop = True
                break
            try:
                without_rag = call_with_quota_retry(
                    lambda: generate_without_retrieval(scenario),
                    label=f"{sid} ablation")
                time.sleep(THROTTLE_SECONDS)
            except ConstraintError as exc:
                print(f"  {sid}: ablation arm FAILED — {str(exc)[:90]}")
                failures.append(f"{sid}:without_rag")
                continue
            except Exception as exc:  # noqa: BLE001 - API/quota errors must not lose work
                print(f"\n  {sid}: API error, stopping and keeping what is cached.")
                print(f"  {str(exc)[:200]}")
                quota_stop = True
                break
            entry = {"with_rag": with_rag, "without_rag": without_rag}
            cache[sid] = entry
            save_cache(cache)
            print(f"  {sid}: generated")
        else:
            print(f"  {sid}: cached")

        scored += 1
        facts = {f["shelter_id"]: f for f in shelter_facts(scenario)}
        v_rag = verdicts_of(entry["with_rag"])
        v_abl = verdicts_of(entry["without_rag"])

        for shelter_id, fact in facts.items():
            total_shelters += 1
            unsafe = is_unsafe(fact)
            for verdicts, tally in ((v_rag, grounded_tally), (v_abl, ablated_tally)):
                allowed = verdicts.get(shelter_id) == "allowed"
                if unsafe and allowed:
                    tally["false_allow"] += 1
                elif unsafe and not allowed:
                    tally["tp"] += 1
                elif not unsafe and allowed:
                    tally["tn"] += 1
                else:
                    tally["false_exclude"] += 1
            if v_rag.get(shelter_id) != v_abl.get(shelter_id):
                verdict_flips += 1

        cited_verbatim_grounded += sum(
            1 for c in entry["with_rag"]["constraints"] if c.get("citation_verified")
        )
        cited_verbatim_ablated += sum(
            1 for c in entry["without_rag"]["constraints"] if c.get("citation_verified")
        )

    if not total_shelters:
        print("\nNo results.")
        return 1

    def report(name: str, tally: dict) -> None:
        correct = tally["tp"] + tally["tn"]
        n = sum(tally.values())
        print(f"\n{name}")
        print(f"  agreement with the safety rule : {correct}/{n} ({correct / n * 100:.1f}%)")
        print(f"  correctly excluded (unsafe)    : {tally['tp']}")
        print(f"  correctly allowed  (safe)      : {tally['tn']}")
        print(f"  FALSE-ALLOW  (unsafe permitted): {tally['false_allow']}"
              f"   <-- SAFETY failures")
        print(f"  false-exclude (usable barred)  : {tally['false_exclude']}"
              f"   <-- cost failures")

    print()
    print("=" * WIDTH)
    print(f"D. DOES THE LLM AGREE WITH THE DETERMINISTIC SAFETY RULE?  "
          f"({total_shelters} shelter verdicts)")
    print("=" * WIDTH)
    report("WITH retrieved NDMA excerpts (the real pipeline)", grounded_tally)
    report("WITHOUT retrieval (ablation — no excerpts in the prompt)", ablated_tally)

    print()
    print("=" * WIDTH)
    print("E. DOES RETRIEVAL CHANGE ANYTHING?")
    print("=" * WIDTH)
    print(f"  verdicts that flipped when retrieval was removed : "
          f"{verdict_flips}/{total_shelters} ({verdict_flips / total_shelters * 100:.1f}%)")
    print(f"  citations verifiable verbatim, WITH retrieval    : "
          f"{cited_verbatim_grounded}/{total_shelters}")
    print(f"  citations verifiable verbatim, WITHOUT retrieval : "
          f"{cited_verbatim_ablated}/{total_shelters}")
    print()
    print("  The citation rows are the point. Without retrieval the model still emits")
    print("  a source_excerpt, but there is no retrieved text for it to be checked")
    print("  against — so it cannot be verified, and an unverifiable citation is exactly")
    print("  what the grounding check exists to catch.")

    if failures:
        print(f"\n  scenarios that failed to generate: {failures}")
    if quota_stop:
        print()
        print("  NOTE: stopped early on an API error (most likely the 20-requests-per-DAY")
        print("  free-tier cap). Everything generated so far is cached — rerun tomorrow")
        print("  and it resumes from where it stopped. Results above cover only the")
        print(f"  {scored} of {len(scenarios)} scenario(s) actually scored.")

    out = RESULTS_DIR / "constraint_agreement.json"
    out.write_text(json.dumps(
        {
            "n_scenarios_scored": scored,
            "n_scenarios_requested": len(scenarios),
            "stopped_early_on_api_error": quota_stop,
            "n_shelter_verdicts": total_shelters,
            "with_retrieval": grounded_tally,
            "without_retrieval": ablated_tally,
            "verdict_flips": verdict_flips,
            "citations_verbatim_with_retrieval": cited_verbatim_grounded,
            "citations_verbatim_without_retrieval": cited_verbatim_ablated,
            "failures": failures,
            "_note": (
                "The deterministic safety rule is a yardstick, not ground truth from the "
                "NDMA text. false_allow (unsafe permitted) is a safety failure; "
                "false_exclude (usable barred) is a cost failure. They are not equivalent."
            ),
        },
        indent=2,
    ) + "\n", encoding="utf-8")
    print(f"\nWrote {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
