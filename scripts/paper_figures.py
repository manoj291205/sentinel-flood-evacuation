"""Phase 37 paper numbers, tables and figures, generated only from frozen result files.

    python scripts/paper_figures.py           # (re)write docs/paper/generated/*
    python scripts/paper_figures.py --check   # exit 1 if any generated file differs from what is on disk

Standard library only. Every number the paper prints comes from a LaTeX macro in
docs/paper/generated/numbers.tex; docs/paper/generated/NUMBERS_TRACE.md lists the file and JSON pointer
(or the derivation over frozen files) behind each macro. Tables and pgfplots figures are written as .tex
fragments that paper.tex \\input{}s, so the PDF needs no image files.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/paper/generated"

P27 = "data/eval_results/phase27/analysis.json"
P27_LAT = "data/eval_results/phase27/latency.json"
P27_RUNS = "data/eval_results/phase27/runs"
P24_COV = "data/eval_results/phase24/coverage.json"
P25 = "data/eval_results/phase25/replay_batch.json"
P26 = "data/eval_results/phase26/flipflop.json"
P14D = "data/eval_results/phase14d/test/score.json"
P14C = "data/eval_results/phase14c/score.json"
TIERS = "data/constraints_v4/p15t2/tier_results.json"
GRAPH = "data/geospatial_v3/fort_kochi_osm_drive_v1_manifest.json"
GRAPH_FULL = "data/geospatial_v3/fort_kochi_osm_drive_v1.json"

PRIMARY = ("v4-medium-dt2-v1", "v4-high-dt2-v1")
STRESS = "v4-stress-dt2-v1"
SYSTEMS = ("HOLD", "A", "A2", "B", "P", "P-noFC", "P-noHyst")
SYSTEM_LABEL = {
    "HOLD": "HOLD",
    "A": "A (greedy + mask)",
    "A2": "A2 (lookahead + mask)",
    "B": "B (known techniques)",
    "P": "P (certified gate)",
    "P-noFC": "P-noFC",
    "P-noHyst": "P-noHyst",
}

_cache: dict[str, object] = {}


def load(rel: str):
    if rel not in _cache:
        _cache[rel] = json.loads((ROOT / rel).read_text(encoding="utf-8"))
    return _cache[rel]


def ptr(rel: str, pointer: str):
    """RFC 6901 JSON pointer into a frozen file (list indices allowed)."""
    node = load(rel)
    for part in pointer.strip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def run_rows(system: str, regime: str) -> list[dict]:
    """Rows of one Phase 27 run file, keyed by seed (resumed runs contain identical duplicates)."""
    rows: dict[int, dict] = {}
    path = ROOT / P27_RUNS / f"{system}_{regime}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows.setdefault(row["seed"], row)
    return [rows[s] for s in sorted(rows)]


# ---------------------------------------------------------------- formatting

def f_int(x) -> str:
    n = int(x)
    if n != x:
        raise ValueError(f"not an integer: {x}")
    s = f"{n:,}"
    return s.replace(",", "{,}")


def f_fix(d: int):
    return lambda x: f"{x:.{d}f}"


def f_pct(d: int):
    return lambda x: f"{100 * x:.{d}f}\\,\\%"


def f_sci(x) -> str:
    mant, exp = f"{x:.2e}".split("e")
    return f"{mant}\\times10^{{{int(exp)}}}"


def f_text(x) -> str:
    return str(x)


# ---------------------------------------------------------------- numbers

class Numbers:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []   # macro, written, source, pointer/derivation
        self.values: dict[str, float] = {}

    def add(self, macro: str, value, fmt, source: str, how: str) -> None:
        if not macro.isalpha():
            raise ValueError(f"LaTeX macro names must be letters only: {macro}")
        if any(m == macro for m, *_ in self.rows):
            raise ValueError(f"duplicate macro {macro}")
        written = fmt(value)
        self.rows.append((macro, written, source, how))
        if isinstance(value, (int, float)):
            self.values[macro] = value

    def p(self, macro: str, rel: str, pointer: str, fmt) -> None:
        self.add(macro, ptr(rel, pointer), fmt, rel, pointer)


def primary_mean(system: str, field: str) -> float:
    """Mean over the two primary regimes (60 episodes each, so equal weights = pooled episode mean)."""
    vals = [ptr(P27, f"/episodes/systems/{system}/{r}/{field}") for r in PRIMARY]
    return sum(vals) / len(vals)


def groups_per_episode(system: str, regimes=PRIMARY) -> float:
    tot = sum(ptr(P27, f"/episodes/systems/{system}/{r}/dispatched_groups") for r in regimes)
    eps = sum(ptr(P27, f"/episodes/systems/{system}/{r}/episodes") for r in regimes)
    return tot / eps


SYS_MACRO = {"HOLD": "Hold", "A": "A", "A2": "Atwo", "B": "B", "P": "P", "P-noFC": "PnoFC", "P-noHyst": "PnoHyst"}


def collect() -> Numbers:
    n = Numbers()
    # --- world
    n.p("nGraphNodes", GRAPH, "/node_count", f_int)
    n.p("nGraphEdges", GRAPH, "/edge_count", f_int)
    zones = len(ptr(GRAPH_FULL, "/zone_node_map"))
    shelters = len(ptr(GRAPH_FULL, "/shelter_node_map"))
    n.add("nZones", zones, f_int, GRAPH_FULL, "len(/zone_node_map)")
    n.add("nShelters", shelters, f_int, GRAPH_FULL, "len(/shelter_node_map)")
    n.add("nAmax", zones * shelters + 1, f_int, GRAPH_FULL, "zones x shelters + 1 (HOLD) = A_MAX")
    pops = [r["initial_population"] for reg in PRIMARY for r in run_rows("A", reg)]
    n.add("nInitPop", sum(pops) / len(pops), f_fix(1), P27_RUNS + "/A_{medium,high}.jsonl",
          "mean initial_population over primary-regime episodes (keyed by seed)")
    # --- evaluation size
    n.p("nSeedsPerRegime", P27, "/budget/seeds_per_regime", f_int)
    total_eps = sum(ptr(P27, f"/episodes/systems/{s}/{r}/episodes") for s in SYSTEMS for r in PRIMARY + (STRESS,))
    n.add("nEpisodesTotal", total_eps, f_int, P27, "sum of /episodes/systems/*/*/episodes")
    n.p("nBudgetHours", P27, "/budget/projection_full_hours_on_16_workers", f_fix(1))
    n.p("nPEpisodeSeconds", P27, "/budget/mean_episode_seconds/P", f_int_round)
    # --- Bar 1
    n.p("nEOneDiff", P27, "/bars/bar1/numbers/E1/mean_diff", f_fix(3))
    n.add("nEOneLo", ptr(P27, "/bars/bar1/numbers/E1/ci95")[0], f_fix(3), P27, "/bars/bar1/numbers/E1/ci95/0")
    n.add("nEOneHi", ptr(P27, "/bars/bar1/numbers/E1/ci95")[1], f_fix(3), P27, "/bars/bar1/numbers/E1/ci95/1")
    n.p("nEOnePairs", P27, "/bars/bar1/numbers/E1/n_pairs", f_int)
    n.p("nRateA", P27, "/bars/bar1/numbers/E1/mean_rate_baseline", f_pct(1))
    p_rate = ptr(P27, "/bars/bar1/numbers/E1/mean_rate_baseline") + ptr(P27, "/bars/bar1/numbers/E1/mean_diff")
    n.add("nRateP", p_rate, f_pct(1), P27, "mean_rate_baseline + mean_diff (/bars/bar1/numbers/E1)")
    n.p("nRelReduction", P27, "/bars/bar1/numbers/E1/relative_reduction", f_pct(0))
    n.p("nR", P27, "/bars/bar1/numbers/R_P_over_A2", f_fix(3))
    n.p("nRpct", P27, "/bars/bar1/numbers/R_P_over_A2", f_pct(1))
    # --- Bar 2
    q2 = "/bars/bar2/numbers"
    n.p("nQtwoCandidates", P27, f"{q2}/candidates", f_int)
    n.p("nQtwoBorderline", P27, f"{q2}/borderline_excluded", f_int)
    n.p("nQtwoGraded", P27, f"{q2}/graded", f_int)
    n.p("nFBJoint", P27, f"{q2}/false_blocks/joint", f_int)
    n.p("nFBProduct", P27, f"{q2}/false_blocks/product_of_marginals", f_int)
    n.p("nFBSeparate", P27, f"{q2}/false_blocks/separate_checks", f_int)
    n.p("nFAJoint", P27, f"{q2}/false_accepts/joint", f_int)
    n.p("nFAProduct", P27, f"{q2}/false_accepts/product_of_marginals", f_int)
    n.p("nFASeparate", P27, f"{q2}/false_accepts/separate_checks", f_int)
    n.p("nMcNJointOnly", P27, f"{q2}/mcnemar/product_of_marginals/joint_only_right", f_int)
    n.p("nMcNOtherOnly", P27, f"{q2}/mcnemar/product_of_marginals/other_only_right", f_int)
    n.p("nMcNSepJointOnly", P27, f"{q2}/mcnemar/separate_checks/joint_only_right", f_int)
    n.p("nMcNSepOtherOnly", P27, f"{q2}/mcnemar/separate_checks/other_only_right", f_int)
    n.p("nMcNp", P27, f"{q2}/mcnemar/product_of_marginals/p", f_sci)
    n.p("nFBReduction", P27, f"{q2}/false_block_reduction_vs_product", f_pct(1))
    # --- Bar 3, 4
    n.p("nVarRatio", P27, "/bars/bar3/numbers/median_var_ratio", f_fix(3))
    n.p("nQthreeStates", P27, "/bars/bar3/numbers/states", f_int)
    n.p("nQfourStates", P27, "/bars/bar4/numbers/states", f_int)
    n.p("nQfourFA", P27, "/bars/bar4/numbers/states_with_false_accept", f_int)
    n.p("nQfourUpper", P27, "/bars/bar4/numbers/cp95_upper", f_fix(4))
    # --- per-system (primary regimes)
    for s in SYSTEMS:
        m = SYS_MACRO[s]
        n.add(f"nGroups{m}", groups_per_episode(s), f_fix(1), P27,
              f"sum dispatched_groups / sum episodes, /episodes/systems/{s}/{{medium,high}}")
        n.add(f"nSafe{m}", primary_mean(s, "mean_safe_arrivals"), f_fix(1), P27,
              f"mean of /episodes/systems/{s}/{{medium,high}}/mean_safe_arrivals")
        n.add(f"nFail{m}", primary_mean(s, "mean_group_failure_rate"), f_pct(1), P27,
              f"mean of /episodes/systems/{s}/{{medium,high}}/mean_group_failure_rate")
    mig_p = sum(ptr(P27, f"/episodes/systems/P/{r}/migrations") for r in PRIMARY)
    n.add("nMigrationsP", mig_p, f_int, P27, "sum of /episodes/systems/P/{medium,high}/migrations")
    arr_err = max(ptr(P27, f"/episodes/systems/P/{r}/median_arrival_abs_error_steps") for r in PRIMARY)
    n.add("nArrErrP", arr_err, f_fix(0), P27,
          "max over {medium,high} of /episodes/systems/P/<regime>/median_arrival_abs_error_steps")
    # --- secondary contrasts (reported, no bar)
    n.p("nPvBDiff", P27, "/secondary/P_vs_B/mean_diff", f_fix(3))
    n.add("nPvBLo", ptr(P27, "/secondary/P_vs_B/ci95")[0], f_fix(3), P27, "/secondary/P_vs_B/ci95/0")
    n.add("nPvBHi", ptr(P27, "/secondary/P_vs_B/ci95")[1], f_fix(3), P27, "/secondary/P_vs_B/ci95/1")
    # --- latency
    n.add("nLatCertPfifty", ptr(P27_LAT, "/0/certify_only_ms/p50"), f_int_round, P27_LAT, "/0/certify_only_ms/p50")
    n.add("nLatCertPninetyfive", ptr(P27_LAT, "/0/certify_only_ms/p95"), f_int_round, P27_LAT, "/0/certify_only_ms/p95")
    n.add("nLatEtePfifty", ptr(P27_LAT, "/0/end_to_end_ms/p50") / 1000, f_fix(1), P27_LAT, "/0/end_to_end_ms/p50 / 1000")
    n.add("nLatEtePninetyfive", ptr(P27_LAT, "/0/end_to_end_ms/p95") / 1000, f_fix(1), P27_LAT, "/0/end_to_end_ms/p95 / 1000")
    n.p("nLatTargetCert", P27_LAT, "/0/targets_ms/certify_only_p95", f_int)
    n.add("nLatTargetEte", ptr(P27_LAT, "/0/targets_ms/end_to_end_p95") / 1000, f_int, P27_LAT,
          "/0/targets_ms/end_to_end_p95 / 1000")
    # --- Phase 24 coverage (synthetic Bernoulli)
    for i, name in enumerate(("Ninety", "NinetyFour", "NinetyFourNine", "NinetySix", "NinetyNine")):
        n.p(f"nCovP{name}", P24_COV, f"/rows/{i}/true_p", f_text)
        n.p(f"nCovAcc{name}", P24_COV, f"/rows/{i}/accept_rate", f_pct(1))
    n.p("nCovReps", P24_COV, "/rows/0/reps", f_int)
    # --- Phase 25 replay, Phase 26 flip-flop
    n.p("nReplayN", P25, "/n", f_int)
    n.p("nReplayMatched", P25, "/matched", f_int)
    n.p("nReplaySeeds", P25, "/seeds_used", f_int)
    n.p("nFlipSeeds", P26, "/seeds", f_int)
    n.p("nFlipSteps", P26, "/steps", f_int)
    n.p("nFlipMigrations", P26, "/total_migrations", f_int)
    n.p("nFlipSeedsWithMig", P26, "/seeds_with_migration", f_int)
    n.p("nFlipReturns", P26, "/returns_to_left_shelter", f_int)
    n.p("nFlipMaxMig", P26, "/max_migrations_observed", f_int)
    # --- claim-support verifier (14D of record, 14C failed) and tiers
    n.p("nVerPairs", P14D, "/claim_pairs", f_int)
    n.p("nVerTwoPrecision", P14D, "/t2_metrics/t2_precision", f_fix(3))
    n.p("nVerTwoUnsafe", P14D, "/t2_metrics/t2_unsafe_acceptance", f_fix(3))
    n.p("nVerTwoRecall", P14D, "/t2_metrics/t2_recall", f_fix(3))
    n.p("nVerMacroFone", P14D, "/metrics/macro_f1", f_fix(3))
    n.p("nVerPartialRecall", P14D, "/metrics/per_class/PARTIALLY_SUPPORTED/recall", f_fix(3))
    n.p("nVerOldMacroFone", P14C, "/metrics/macro_f1", f_fix(3))
    n.p("nVerOldSpanFail", P14C, "/metrics/span_integrity_failure_rate", f_fix(3))
    n.p("nTierRuleOne", TIERS, "/records/0/rule_id", f_text)
    n.p("nTierOne", TIERS, "/records/0/tier", f_text)
    n.p("nTierRuleTwo", TIERS, "/records/1/rule_id", f_text)
    n.p("nTierTwo", TIERS, "/records/1/tier", f_text)
    return n


def f_int_round(x) -> str:
    return f_int(int(round(x)))


# ---------------------------------------------------------------- outputs

HEADER = "% Generated by scripts/paper_figures.py from frozen files. Do not edit by hand.\n"


def numbers_tex(n: Numbers) -> str:
    lines = [HEADER]
    for macro, written, source, how in n.rows:
        lines.append(f"\\newcommand{{\\{macro}}}{{\\ensuremath{{{written}}}}} % {source} {how}\n"
                     if "\\" in written or written[:1] in "-0123456789" else
                     f"\\newcommand{{\\{macro}}}{{{written}}} % {source} {how}\n")
    return "".join(lines)


def trace_md(n: Numbers) -> str:
    out = ["# Numbers trace for the Phase 37 paper draft\n\n",
           "Generated by `scripts/paper_figures.py`. Every macro used in `docs/paper/paper.tex` resolves to one row.\n\n",
           "| Macro | Written | File | Pointer or derivation |\n|---|---|---|---|\n"]
    for macro, written, source, how in n.rows:
        out.append(f"| `\\{macro}` | `{written}` | `{source}` | `{how}` |\n")
    return "".join(out)


def tab_bars() -> str:
    b = "/bars"
    rows = [
        ("1 (outcomes)", "E1 CI upper $<0$ and $R\\ge0.95$",
         "E1 $=\\nEOneDiff$ [\\nEOneLo, \\nEOneHi]; $R=\\nR$", ptr(P27, f"{b}/bar1/pass")),
        ("2 (coupling)", "joint has fewer errors than each marginal rule, McNemar $p<0.05$",
         "errors \\nFBJoint{} vs \\nFBProduct{} / \\nFBSeparate; $p=\\nMcNp$", ptr(P27, f"{b}/bar2/pass")),
        ("3 (keyed CRN)", "median $\\mathrm{Var}_{\\text{indep}}/\\mathrm{Var}_{\\text{CRN}}\\ge2$",
         "\\nVarRatio{} (\\nQthreeStates{} states)", ptr(P27, f"{b}/bar3/pass")),
        ("4 (safety)", "share of states with a false accept $\\le0.01$",
         "\\nQfourFA/\\nQfourStates{} (CP 95\\,\\% upper \\nQfourUpper)", ptr(P27, f"{b}/bar4/pass")),
    ]
    out = [HEADER, "\\begin{tabular}{@{}l p{0.30\\columnwidth} p{0.34\\columnwidth} c@{}}\n\\toprule\n",
           "Bar & Pre-registered test & Result & Pass\\\\\n\\midrule\n"]
    for bar, test, result, ok in rows:
        verdict = "yes" if ok else "\\textbf{no}"
        out.append(f"{bar} & {test} & {result} & {verdict}\\\\\n")
    out.append("\\bottomrule\n\\end{tabular}\n")
    return "".join(out)


def tab_systems() -> str:
    out = [HEADER, "\\begin{tabular}{@{}lrrr@{}}\n\\toprule\n",
           "System & Groups/ep. & Safe arr./ep. & Fail. rate\\\\\n\\midrule\n"]
    for s in SYSTEMS:
        m = SYS_MACRO[s]
        label = SYSTEM_LABEL[s]
        if s == "P":
            label = f"\\textbf{{{label}}}"
        fail = "--" if s == "HOLD" else f"\\nFail{m}"
        out.append(f"{label} & \\nGroups{m} & \\nSafe{m} & {fail}\\\\\n")
    out.append("\\bottomrule\n\\end{tabular}\n")
    return "".join(out)


def tab_regimes() -> str:
    """Appendix: every system x regime, straight from analysis.json (stress regime included)."""
    regs = PRIMARY + (STRESS,)
    short = {"v4-medium-dt2-v1": "medium", "v4-high-dt2-v1": "high", "v4-stress-dt2-v1": "stress"}
    out = [HEADER, "\\begin{tabular}{@{}llrrrr@{}}\n\\toprule\n",
           "System & Regime & Groups & Safe arr./ep. & Fail. rate & Migr.\\\\\n\\midrule\n"]
    for s in SYSTEMS:
        for r in regs:
            e = f"/episodes/systems/{s}/{r}"
            fail = ptr(P27, f"{e}/mean_group_failure_rate")
            fail_s = "--" if s == "HOLD" else f"{100 * fail:.1f}\\,\\%"
            out.append(f"{s} & {short[r]} & {f_int(ptr(P27, f'{e}/dispatched_groups'))} & "
                       f"{ptr(P27, f'{e}/mean_safe_arrivals'):.1f} & {fail_s} & "
                       f"{f_int(ptr(P27, f'{e}/migrations'))}\\\\\n")
        if s != SYSTEMS[-1]:
            out.append("\\addlinespace[2pt]\n")
    out.append("\\bottomrule\n\\end{tabular}\n")
    return "".join(out)


def fig_tradeoff() -> str:
    """Safe arrivals vs group failure rate per system (primary regimes): the D-27 trade-off."""
    pts = []
    for s in SYSTEMS:
        if s == "HOLD":
            continue
        x = primary_mean(s, "mean_safe_arrivals")
        y = 100 * primary_mean(s, "mean_group_failure_rate")
        pts.append((s, x, y))
    anchor = {"A": "north west", "A2": "north east", "B": "south west", "P": "south west",
              "P-noFC": "south west", "P-noHyst": "north west"}
    coords = "\n".join(f"      ({x:.3f},{y:.3f}) [{s}]" for s, x, y in pts if s != "P-noHyst")
    labels = "\n".join(f"    \\node[anchor={anchor[s]},font=\\scriptsize] at (axis cs:{x:.3f},{y:.3f}) {{{s}}};"
                       for s, x, y in pts if s != "P-noHyst")
    return (HEADER +
            "\\begin{tikzpicture}\n"
            "  \\begin{axis}[width=\\columnwidth, height=0.62\\columnwidth,\n"
            "    xlabel={People safely arrived per episode}, ylabel={Group failure rate (\\%)},\n"
            "    xmin=0, xmax=265, ymin=0, ymax=27, grid=major, grid style={gray!25},\n"
            "    tick label style={font=\\scriptsize}, label style={font=\\small}]\n"
            "    \\addplot[only marks, mark=*, mark size=1.8pt] coordinates {\n"
            f"{coords}\n    }};\n"
            f"{labels}\n"
            "  \\end{axis}\n"
            "\\end{tikzpicture}\n")


def fig_q2() -> str:
    q2 = "/bars/bar2/numbers"
    vals = [("joint", ptr(P27, f"{q2}/false_blocks/joint")),
            ("product", ptr(P27, f"{q2}/false_blocks/product_of_marginals")),
            ("separate", ptr(P27, f"{q2}/false_blocks/separate_checks"))]
    coords = " ".join(f"({name},{v})" for name, v in vals)
    return (HEADER +
            "\\begin{tikzpicture}\n"
            "  \\begin{axis}[ybar, width=0.95\\columnwidth, height=0.5\\columnwidth, bar width=16pt,\n"
            "    symbolic x coords={joint,product,separate}, xtick=data, ymin=0, ymax=280,\n"
            "    ylabel={False blocks (of \\nQtwoGraded{} graded)}, nodes near coords,\n"
            "    nodes near coords style={font=\\scriptsize}, tick label style={font=\\scriptsize},\n"
            "    label style={font=\\small}, enlarge x limits=0.25]\n"
            f"    \\addplot[fill=gray!45] coordinates {{{coords}}};\n"
            "  \\end{axis}\n"
            "\\end{tikzpicture}\n")


def render() -> dict[str, str]:
    n = collect()
    return {
        "numbers.tex": numbers_tex(n),
        "NUMBERS_TRACE.md": trace_md(n),
        "tab_bars.tex": tab_bars(),
        "tab_systems.tex": tab_systems(),
        "tab_regimes.tex": tab_regimes(),
        "fig_tradeoff.tex": fig_tradeoff(),
        "fig_q2.tex": fig_q2(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare with files on disk instead of writing")
    args = ap.parse_args(argv)
    files = render()
    if args.check:
        bad = [name for name, text in files.items()
               if not (OUT / name).exists() or (OUT / name).read_text(encoding="utf-8") != text]
        for name in bad:
            print(f"differs: docs/paper/generated/{name}")
        print("OK" if not bad else f"{len(bad)} file(s) differ")
        return 1 if bad else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote docs/paper/generated/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
