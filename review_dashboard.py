"""Standalone, offline review dashboard for frozen Sentinel-Agent V3 results.

Run with: streamlit run review_dashboard.py

This UI reads committed artifacts and local corpus chunks. It does not train models,
run policy/retrieval evaluations, call Gemini, or modify scientific outputs.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
TRAINING_PATH = ROOT / "data" / "eval_v3" / "training" / "training_summary.json"
LEARNING_CURVES_PATH = ROOT / "data" / "eval_v3" / "training" / "learning_curves.csv"
PERMUTATION_PATH = ROOT / "data" / "eval_v3" / "training" / "permutation_diagnostic.json"
POLICY_PATH = ROOT / "data" / "eval_v3" / "phase10" / "heldout_summary.json"
PAIRWISE_PATH = ROOT / "data" / "eval_v3" / "phase10" / "pairwise_bootstrap.json"
POLICY_LATENCY_PATH = ROOT / "data" / "eval_v3" / "phase10" / "latency_results.json"
RETRIEVAL_LATENCY_PATH = ROOT / "data" / "eval_v3" / "phase12_retrieval_sanity.json"
RETRIEVAL_PATH = ROOT / "data" / "eval_v3" / "phase13" / "phase13b_retrieval_results_v2.json"
RETRIEVAL_MANIFEST_PATH = ROOT / "data" / "eval_v3" / "phase13" / "ai_assisted_label_manifest_extended.json"
PER_QUESTION_PATH = ROOT / "data" / "eval_v3" / "phase13" / "phase13b_per_question_v2.csv"
RANKINGS_PATH = ROOT / "data" / "eval_v3" / "phase13" / "phase13b_rankings_v2.csv"
LABELS_PATH = ROOT / "data" / "eval_v3" / "phase13" / "ai_assisted_passage_labels_extended.csv"
DOCUMENTATION_PATH = ROOT / "DOCUMENTATION.md"

SYSTEM_LABELS = {
    "dense-minilm-v1": "Dense",
    "bm25-okapi-v1": "BM25",
    "hybrid-rrf-v1": "Hybrid",
}
POLICY_LABELS = {
    "random_valid": "Random",
    "nearest_safe": "Nearest-safe",
    "risk_greedy": "Risk-greedy",
    "lookahead_k2": "Lookahead-2",
    "lookahead_k3": "Lookahead-3",
    "sampled_mpc": "MPC",
    "ppo_family": "PPO",
}
SOURCE_TITLES = {
    "ndma-flood-guidelines-2008": "NDMA Management of Floods",
    "ndma-national-disaster-management-plan-2019": "National Disaster Management Plan 2019",
    "ndma-temporary-shelters-2019": "National Guidelines for Temporary Shelters",
}
GRADE_LABELS = {2: "DIRECT", 1: "PARTIAL", 0: "NOT RELEVANT"}
GRADE_COLORS = {2: "#0f9d76", 1: "#d98e04", 0: "#718096"}


st.set_page_config(
    page_title="Sentinel-Agent V3 · Project Review",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      :root { --navy:#10243e; --cyan:#17a6b6; --ice:#eef8fa; --gold:#e0a52b; }
      .stApp { background: linear-gradient(180deg,#f7fbfc 0,#ffffff 300px); }
      .block-container { max-width: 1280px; padding-top: 1.7rem; padding-bottom: 3rem; }
      .hero { padding:1.6rem 1.8rem; border-radius:20px; color:white;
              background:linear-gradient(125deg,#10243e 0%,#153f5d 62%,#148a99 100%);
              box-shadow:0 18px 42px rgba(16,36,62,.16); margin-bottom:1rem; }
      .eyebrow { text-transform:uppercase; letter-spacing:.14em; font-size:.72rem;
                 font-weight:700; color:#8fe2ea; }
      .hero h1 { font-size:2.45rem; line-height:1.05; margin:.35rem 0 .5rem; }
      .hero p { color:#d6edf1; max-width:850px; font-size:1.03rem; margin:0; }
      .result-good,.result-warn,.result-info { padding:1rem 1.15rem; border-radius:14px;
                 border:1px solid rgba(16,36,62,.10); height:100%; }
      .result-good { background:#eaf8f3; border-left:5px solid #0f9d76; }
      .result-warn { background:#fff7e6; border-left:5px solid #e0a52b; }
      .result-info { background:#edf7fb; border-left:5px solid #17a6b6; }
      .result-kicker { text-transform:uppercase; letter-spacing:.08em; font-size:.7rem;
                       font-weight:700; color:#526477; }
      .result-value { font-size:1.45rem; font-weight:800; color:#10243e; margin:.2rem 0; }
      .result-copy { color:#43576a; font-size:.88rem; line-height:1.45; }
      .flow { display:flex; gap:.45rem; align-items:center; flex-wrap:wrap; margin:.8rem 0 1.2rem; }
      .flow-step { background:#fff; border:1px solid #cfe3e8; color:#173853; border-radius:10px;
                   padding:.62rem .75rem; font-size:.78rem; font-weight:650;
                   box-shadow:0 4px 12px rgba(16,36,62,.05); }
      .flow-arrow { color:#17a6b6; font-weight:800; }
      .evidence { background:#fff; border:1px solid #dce9ed; border-radius:13px;
                  padding:.78rem .9rem; margin:.45rem 0; box-shadow:0 4px 13px rgba(16,36,62,.04); }
      .evidence-meta { font-size:.76rem; color:#607386; margin-bottom:.35rem; }
      .excerpt { font-size:.86rem; line-height:1.5; color:#273b4d; }
      .badge { color:white; padding:.14rem .48rem; border-radius:999px; font-size:.68rem;
               font-weight:750; letter-spacing:.04em; }
      div[data-testid="stMetric"] { background:white; border:1px solid #dce9ed;
               padding:.8rem 1rem; border-radius:13px; box-shadow:0 5px 14px rgba(16,36,62,.04); }
      div[data-testid="stTabs"] button { font-weight:650; }
      h2,h3 { color:#10243e; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text()), None
    except Exception as exc:  # surfaced visibly by each tab
        return None, f"Could not load {path.relative_to(ROOT)}: {exc}"


@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    try:
        return pd.read_csv(path), None
    except Exception as exc:
        return None, f"Could not load {path.relative_to(ROOT)}: {exc}"


@st.cache_data(show_spinner=False)
def load_test_count() -> int | None:
    try:
        matches = re.findall(r"passes all ([0-9,]+) collected tests", DOCUMENTATION_PATH.read_text())
        return int(matches[-1].replace(",", "")) if matches else None
    except Exception:
        return None


@st.cache_data(show_spinner="Reconstructing local evidence excerpts…")
def load_chunk_catalog() -> tuple[dict[str, dict[str, Any]] | None, str | None]:
    try:
        from src.rag.ingest import prepare_corpus

        prepared = prepare_corpus()
        catalog = {
            chunk_id: {
                "text": text,
                "source_id": str(metadata["source_id"]),
                "filename": str(metadata["source_document"]),
                "page": int(metadata["page"]),
            }
            for chunk_id, text, metadata in zip(
                prepared.ids, prepared.documents, prepared.metadatas
            )
        }
        return catalog, None
    except Exception as exc:
        return None, f"Local chunk reconstruction is unavailable: {exc}"


def show_error(error: str | None) -> bool:
    if error:
        st.warning(error, icon="⚠️")
        return True
    return False


def result_card(kicker: str, value: str, copy: str, kind: str = "info") -> None:
    st.markdown(
        f'<div class="result-{kind}"><div class="result-kicker">{html.escape(kicker)}</div>'
        f'<div class="result-value">{html.escape(value)}</div>'
        f'<div class="result-copy">{html.escape(copy)}</div></div>',
        unsafe_allow_html=True,
    )


training, training_error = load_json(TRAINING_PATH)
policy, policy_error = load_json(POLICY_PATH)
pairwise, pairwise_error = load_json(PAIRWISE_PATH)
retrieval, retrieval_error = load_json(RETRIEVAL_PATH)
retrieval_manifest, retrieval_manifest_error = load_json(RETRIEVAL_MANIFEST_PATH)
policy_latency, policy_latency_error = load_json(POLICY_LATENCY_PATH)
retrieval_latency, retrieval_latency_error = load_json(RETRIEVAL_LATENCY_PATH)

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">University project review · frozen research results</div>
      <h1>Sentinel-Agent V3</h1>
      <p>Evidence-Grounded Decision Support for Dynamic Flood Evacuation Under Uncertainty</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Offline review UI · reads committed artifacts · performs no training or experiment reruns")

overview_tab, policy_tab, training_tab, retrieval_tab, evidence_tab, tradeoffs_tab = st.tabs(
    [
        "Overview",
        "Policy & RL",
        "PPO Training",
        "RAG Evaluation",
        "Evidence Demo",
        "Research Trade-offs",
    ]
)


with overview_tab:
    st.subheader("Project at a glance")
    test_count = load_test_count()
    values = [
        ("Held-out scenarios", policy["suite"]["number_of_scenarios"] if policy else "—"),
        ("PPO seeds", len(training["primary_training_seeds"]) if training else "—"),
        ("Timesteps / seed", f"{training['timesteps_per_seed']:,}" if training else "—"),
        ("Total PPO timesteps", f"{training['total_primary_timesteps']/1_000_000:.2f}M" if training else "—"),
        (
            "NDMA documents",
            len(retrieval["source_distribution_top5"]["dense"]) if retrieval else "—",
        ),
        (
            "RAG chunks",
            f"{retrieval_manifest['canonical_chunks']:,}" if retrieval_manifest else "—",
        ),
        ("Benchmark questions", retrieval["question_count"] if retrieval else "—"),
        ("Automated tests", test_count or "—"),
    ]
    for start in (0, 4):
        columns = st.columns(4)
        for column, (label, value) in zip(columns, values[start : start + 4]):
            column.metric(label, value)
    for error in (training_error, policy_error, retrieval_error, retrieval_manifest_error):
        show_error(error)

    st.subheader("System architecture")
    flow = [
        "Dynamic flood / shelter / route state",
        "Stochastic simulator",
        "Deterministic safety layer",
        "Decision policy / planner",
        "Evacuation recommendation",
        "RAG evidence retrieval",
        "Source · page · citation",
    ]
    flow_html = '<div class="flow">' + '<span class="flow-arrow">→</span>'.join(
        f'<span class="flow-step">{html.escape(step)}</span>' for step in flow
    ) + "</div>"
    st.markdown(flow_html, unsafe_allow_html=True)
    left, middle, right = st.columns(3)
    with left:
        result_card("Decision research", "RL usefulness = NO", "PPO was tested across five seeds and 600 held-out stochastic scenarios, but was not selected as the final decision method.", "warn")
    with middle:
        result_card("Retrieval research", "HYBRID_SUPPORTED", "Hybrid met the frozen support rule against Dense; BM25 nevertheless had the highest DirectHit@5.", "good")
    with right:
        result_card("Scientific posture", "Negative results retained", "The project reports what the frozen experiments found and does not tune until a preferred story appears.", "info")


with policy_tab:
    st.subheader("Frozen Phase 10 held-out evaluation")
    if show_error(policy_error) or policy is None:
        st.info("Policy charts require the committed Phase 10 held-out summary.")
    else:
        policies = policy["policies"]
        policy_rows = [
            {
                "Policy": label,
                "NSU-practical": policies[key]["nsu_practical"],
                "Safe population fraction": policies[key]["mean_safe_population_fraction"],
            }
            for key, label in POLICY_LABELS.items()
        ]
        policy_frame = pd.DataFrame(policy_rows).set_index("Policy")
        chart_left, chart_right = st.columns(2)
        with chart_left:
            st.markdown("#### Normalized score (NSU-practical)")
            st.bar_chart(policy_frame[["NSU-practical"]], color="#17a6b6")
            st.caption("Frozen Phase 1 practical normalization; values are intentionally unclipped.")
        with chart_right:
            st.markdown("#### Mean safe-population fraction")
            st.bar_chart(policy_frame[["Safe population fraction"]], color="#e0a52b")
            st.caption("Synthetic held-out scenarios; this is not real emergency-response evidence.")

        result_left, comparison_col, safety_col = st.columns([1, 1.35, 1])
        with result_left:
            result_card("Frozen Phase 10 result", f"RL USEFULNESS: {policy['formal_result']}", "PPO was evaluated experimentally and was not selected as the final decision method.", "warn")
        if pairwise and not pairwise_error:
            effect = pairwise["combined"]["effects"]["nsu_difference"]
            with comparison_col:
                result_card("PPO vs Risk-greedy", f"{effect['estimate']:.4f} NSU", f"95% CI [{effect['lower']:.4f}, {effect['upper']:.4f}] · principal comparator: {policy['principal_comparator']}", "info")
        else:
            with comparison_col:
                show_error(pairwise_error)
        with safety_col:
            unsafe = int(policies["ppo_family"]["unsafe_dispatches"])
            result_card("Hard-safety outcome", f"{unsafe} unsafe dispatches", "Deterministic action masks remained the safety authority.", "good")
        st.info("The project intentionally retained the negative RL result rather than retraining until PPO appeared superior.", icon="ℹ️")


with training_tab:
    st.subheader("Frozen Phase 9 PPO training")
    if show_error(training_error) or training is None:
        st.info("Training charts require the committed Phase 9 training summary.")
    else:
        seed_rows = pd.DataFrame(training["seed_results"])
        seed_rows["seed"] = seed_rows["seed"].astype(str)
        top = st.columns(4)
        top[0].metric("Seeds", len(training["primary_training_seeds"]))
        top[1].metric("Timesteps / seed", f"{training['timesteps_per_seed']:,}")
        top[2].metric("Total timesteps", f"{training['total_primary_timesteps']/1_000_000:.2f}M")
        top[3].metric("Representative model", f"Seed {training['representative_seed']}")

        left, right = st.columns(2)
        with left:
            st.markdown("#### Best validation return by seed")
            st.bar_chart(seed_rows.set_index("seed")[["validation_return"]], color="#17a6b6")
            st.dataframe(
                seed_rows[["seed", "best_timestep", "validation_return"]].rename(
                    columns={"seed": "Seed", "best_timestep": "Best timestep", "validation_return": "Validation return"}
                ),
                hide_index=True,
                width="stretch",
                column_config={"Validation return": st.column_config.NumberColumn(format="%.6f")},
            )
        with right:
            curves, curves_error = load_csv(LEARNING_CURVES_PATH)
            if curves is not None:
                aggregate = curves.groupby("timestep", as_index=False)["mean_validation_return"].first()
                st.markdown("#### Recorded validation trajectory")
                st.line_chart(aggregate.set_index("timestep"), color="#e0a52b")
                st.caption("Committed mean validation return across seeds; no curve was regenerated for this dashboard.")
            else:
                show_error(curves_error)

        permutation, permutation_error = load_json(PERMUTATION_PATH)
        if permutation and not permutation_error:
            result_card("Scientific limitation", permutation["alarm_label"], "The flat MLP showed sensitivity to slot permutations, which was reported rather than hidden.", "warn")
        else:
            show_error(permutation_error)


with retrieval_tab:
    st.subheader("Frozen Phase 13 retrieval benchmark")
    if show_error(retrieval_error) or retrieval is None:
        st.info("Retrieval charts require the committed Phase 13B v2 result artifact.")
    else:
        overall = retrieval["overall"]
        hit_frame = pd.DataFrame(
            {
                "Retriever": ["Dense", "BM25", "Hybrid"],
                "DirectHit@1": [overall[key]["direct_hit_at_1"] for key in ("dense", "bm25", "hybrid")],
                "DirectHit@3": [overall[key]["direct_hit_at_3"] for key in ("dense", "bm25", "hybrid")],
                "DirectHit@5": [overall[key]["direct_hit_at_5"] for key in ("dense", "bm25", "hybrid")],
            }
        ).set_index("Retriever")
        left, right = st.columns([1.55, 1])
        with left:
            st.markdown("#### Direct-evidence hit rate")
            st.bar_chart(hit_frame, color=["#8ccbd3", "#17a6b6", "#10243e"])
        with right:
            st.markdown("#### Graded ranking quality · nDCG@5")
            ndcg = pd.DataFrame(
                {
                    "Retriever": ["Dense", "BM25", "Hybrid"],
                    "nDCG@5": [overall[key]["ndcg_at_5"] for key in ("dense", "bm25", "hybrid")],
                }
            ).set_index("Retriever")
            st.bar_chart(ndcg, color="#e0a52b")

        principal = retrieval["principal_comparison"]
        a, b, c = st.columns(3)
        with a:
            result_card("Frozen verdict vs Dense", principal["final_verdict"], "All three pre-registered support conditions passed.", "good")
        with b:
            result_card("Hybrid − Dense Hit@5", f"+{principal['hybrid_minus_dense_directhit5']:.4f}", f"+{principal['equivalent_question_difference']} questions · 95% CI [{principal['ci95']['lower']:.4f}, {principal['ci95']['upper']:.4f}]", "info")
        with c:
            counts = ", ".join(
                f"{name} {overall[key]['direct_hit_at_5_count']}/45"
                for key, name in (("dense", "Dense"), ("bm25", "BM25"), ("hybrid", "Hybrid"))
            )
            result_card("DirectHit@5 counts", "BM25 highest", counts, "warn")
        st.warning("Unexpected finding: BM25 achieved the highest DirectHit@5 even though Hybrid was strongly supported over the pre-registered Dense baseline. Hybrid did not beat BM25 on DirectHit@5.", icon="🔎")
        st.caption("Passage relevance labels are AI-assisted rather than independently human-annotated gold labels.")


with evidence_tab:
    st.subheader("Offline evidence explorer")
    question_data, question_error = load_csv(PER_QUESTION_PATH)
    rankings, rankings_error = load_csv(RANKINGS_PATH)
    labels, labels_error = load_csv(LABELS_PATH)
    errors = [error for error in (question_error, rankings_error, labels_error) if error]
    for error in errors:
        show_error(error)
    if question_data is None or rankings is None or labels is None:
        st.info("The evidence explorer requires the committed Phase 13 question, ranking, and extended-label artifacts.")
    else:
        preferred = ["Q003", "Q008", "Q016", "Q034", "Q006", "Q012", "Q020", "Q039"]
        available = set(question_data["question_id"])
        selected_ids = [question_id for question_id in preferred if question_id in available]
        if not selected_ids:
            selected_ids = list(question_data["question_id"].head(8))
        question_lookup = question_data.set_index("question_id")["effective_question"].to_dict()
        selected = st.selectbox(
            "Select a frozen benchmark question",
            selected_ids,
            format_func=lambda question_id: f"{question_id} · {question_lookup[question_id]}",
        )
        st.markdown(f"### {selected} · {question_lookup[selected]}")
        st.caption("Ranks come from the frozen evaluation; excerpts are reconstructed at runtime from the unchanged local corpus.")

        label_lookup = {
            (str(row.question_id), str(row.chunk_id)): int(row.ai_relevance_grade)
            for row in labels.itertuples()
        }
        catalog, catalog_error = load_chunk_catalog()
        if catalog_error:
            show_error(catalog_error)
        method_columns = st.columns(3)
        for column, (method_id, system_name) in zip(method_columns, SYSTEM_LABELS.items()):
            with column:
                st.markdown(f"#### {system_name} top-5")
                method_rows = rankings[
                    (rankings["question_id"] == selected)
                    & (rankings["method_id"] == method_id)
                ].sort_values("rank")
                if method_rows.empty:
                    st.warning(f"No frozen {system_name} ranks found.")
                    continue
                for row in method_rows.itertuples():
                    grade = label_lookup.get((selected, str(row.chunk_id)))
                    grade_text = GRADE_LABELS.get(grade, "UNLABELLED")
                    grade_color = GRADE_COLORS.get(grade, "#b42318")
                    chunk = catalog.get(str(row.chunk_id)) if catalog else None
                    source_id = str(row.source_id)
                    document = SOURCE_TITLES.get(source_id, source_id)
                    filename = chunk["filename"] if chunk else document
                    excerpt = ""
                    if chunk:
                        clean = " ".join(chunk["text"].split())
                        excerpt = clean[:280] + ("…" if len(clean) > 280 else "")
                    excerpt_html = f'<div class="excerpt">{html.escape(excerpt)}</div>' if excerpt else ""
                    st.markdown(
                        f'<div class="evidence"><span class="badge" style="background:{grade_color}">{grade_text}</span>'
                        f'<div class="evidence-meta"><b>Rank {int(row.rank)}</b> · {html.escape(document)} · '
                        f'{html.escape(filename)} · PDF page {int(row.page)}</div>'
                        f'<div class="evidence-meta"><code>{html.escape(str(row.chunk_id))}</code></div>'
                        f'{excerpt_html}</div>',
                        unsafe_allow_html=True,
                    )
        st.info("Relevant evidence retrieval is separate from claim entailment. Claim-support verification is planned as the next project phase.", icon="ℹ️")


with tradeoffs_tab:
    st.subheader("Research trade-offs: quality versus computation")
    st.caption("Both views combine already-frozen measurements; no evaluation or timing was rerun for this dashboard.")

    st.markdown("### Evacuation policy trade-off")
    if policy is None:
        show_error(policy_error)
    elif policy_latency is None:
        show_error(policy_latency_error)
        st.info("Phase 10 latency artifact unavailable; the policy latency/utility scatter cannot be displayed.")
    else:
        policy_tradeoff = pd.DataFrame(
            [
                {
                    "Method": label,
                    "Median latency (ms)": policy_latency["policies"][key]["median_ms"],
                    "NSU-practical": policy["policies"][key]["nsu_practical"],
                    "Safe fraction": policy["policies"][key]["mean_safe_population_fraction"],
                }
                for key, label in POLICY_LABELS.items()
            ]
        )
        policy_base = alt.Chart(policy_tradeoff).encode(
            x=alt.X(
                "Median latency (ms):Q",
                scale=alt.Scale(type="log"),
                axis=alt.Axis(title="Median decision latency (ms, logarithmic)", grid=True),
            ),
            y=alt.Y(
                "NSU-practical:Q",
                axis=alt.Axis(title="Normalized score / NSU-practical"),
                scale=alt.Scale(zero=False, padding=18),
            ),
            color=alt.Color(
                "Method:N",
                legend=None,
                scale=alt.Scale(
                    domain=list(POLICY_LABELS.values()),
                    range=["#8aa8b7", "#5d8799", "#0f9d76", "#27a8b7", "#123c5a", "#e0a52b", "#b64c63"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Method:N"),
                alt.Tooltip("NSU-practical:Q", format=".4f"),
                alt.Tooltip("Median latency (ms):Q", format=".4f"),
                alt.Tooltip("Safe fraction:Q", format=".4f"),
            ],
        )
        policy_plot = policy_base.mark_circle(size=175, opacity=0.92) + policy_base.mark_text(
            align="left", dx=9, dy=-9, fontSize=12, fontWeight=600
        ).encode(text="Method:N")
        st.altair_chart(policy_plot.properties(height=420), width="stretch")
        st.caption(
            f"Latency source: {POLICY_LATENCY_PATH.relative_to(ROOT)} · "
            f"utility/safety source: {POLICY_PATH.relative_to(ROOT)}"
        )
        st.info(
            "Planning quality increased substantially with lookahead depth, but latency also increased by orders of magnitude. PPO remained fast but did not achieve competitive held-out utility.",
            icon="↔️",
        )
        best, practical, rl = st.columns(3)
        with best:
            result_card("Best utility", "Lookahead-3", f"NSU {policy['policies']['lookahead_k3']['nsu_practical']:.4f}; not designated as a production method.", "good")
        with practical:
            result_card("Fast practical baseline", "Risk-Greedy", "Principal practical comparator under the frozen latency constraint.", "info")
        with rl:
            result_card("RL result", "Not useful", "PPO did not pass the frozen Phase 10 usefulness criteria.", "warn")

    st.markdown("### Retrieval quality versus latency")
    if retrieval is None:
        show_error(retrieval_error)
    elif retrieval_latency is None:
        show_error(retrieval_latency_error)
        fallback = pd.DataFrame(
            {
                "Method": ["Dense MiniLM", "BM25", "Hybrid RRF"],
                "DirectHit@5": [retrieval["overall"][key]["direct_hit_at_5"] for key in ("dense", "bm25", "hybrid")],
            }
        ).set_index("Method")
        st.info("Latency artifact unavailable; showing frozen retrieval quality only.")
        st.bar_chart(fallback, color="#17a6b6")
    else:
        retrieval_names = {"dense": "Dense MiniLM", "bm25": "BM25", "hybrid": "Hybrid RRF"}
        retrieval_tradeoff = pd.DataFrame(
            [
                {
                    "Method": label,
                    "Median latency (ms)": retrieval_latency["latency"][key]["median_ms"],
                    "DirectHit@5": retrieval["overall"][key]["direct_hit_at_5"],
                    "Hits": f"{retrieval['overall'][key]['direct_hit_at_5_count']}/45",
                    "nDCG@5": retrieval["overall"][key]["ndcg_at_5"],
                }
                for key, label in retrieval_names.items()
            ]
        )
        retrieval_base = alt.Chart(retrieval_tradeoff).encode(
            x=alt.X(
                "Median latency (ms):Q",
                scale=alt.Scale(type="log"),
                axis=alt.Axis(title="Warmed median retrieval latency (ms, logarithmic)", grid=True),
            ),
            y=alt.Y(
                "DirectHit@5:Q",
                axis=alt.Axis(title="DirectHit@5", format=".0%"),
                scale=alt.Scale(domain=[0.55, 0.92]),
            ),
            color=alt.Color(
                "Method:N",
                legend=None,
                scale=alt.Scale(
                    domain=list(retrieval_names.values()),
                    range=["#5d8799", "#e0a52b", "#17a6b6"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Method:N"),
                alt.Tooltip("DirectHit@5:Q", format=".4f"),
                alt.Tooltip("Hits:N"),
                alt.Tooltip("nDCG@5:Q", format=".4f"),
                alt.Tooltip("Median latency (ms):Q", format=".4f"),
            ],
        )
        retrieval_plot = retrieval_base.mark_circle(size=210, opacity=0.94) + retrieval_base.mark_text(
            align="left", dx=10, dy=-10, fontSize=13, fontWeight=600
        ).encode(text="Method:N")
        st.altair_chart(retrieval_plot.properties(height=380), width="stretch")
        st.caption(
            f"Latency source: {RETRIEVAL_LATENCY_PATH.relative_to(ROOT)} · "
            f"quality source: {RETRIEVAL_PATH.relative_to(ROOT)}"
        )
        retrieval_finding, hybrid_finding = st.columns(2)
        with retrieval_finding:
            result_card("BM25 highest DirectHit@5", "39/45 · 0.8667", "BM25 also had the lowest frozen warmed retrieval latency.", "good")
        with hybrid_finding:
            result_card("Hybrid supported vs Dense", "+0.2000 DirectHit@5", "Hybrid passed the pre-registered principal comparison against Dense; it did not beat BM25.", "info")
        st.success("BM25 produced the highest DirectHit@5 while also having the lowest measured warmed retrieval latency.", icon="🔎")

    st.markdown("### Why this matters")
    lesson_one, lesson_two, lesson_three = st.columns(3)
    with lesson_one:
        result_card("1 · Complexity", "Not automatically better", "Measured quality and computation—not model novelty—drive selection.", "info")
    with lesson_two:
        result_card("2 · Reinforcement learning", "Empirically rejected", "PPO was not retained despite 1.25 million training timesteps.", "warn")
    with lesson_three:
        result_card("3 · Neural retrieval", "Lexical baseline won", "BM25 outperformed the Dense baseline on direct-evidence retrieval.", "good")
    st.markdown(
        "**Sentinel-Agent therefore selects components based on measured performance rather than assuming that reinforcement learning or neural retrieval must be superior.**"
    )

    st.markdown("### Research progression")
    timeline = [
        "V1 · Static shelter recommendation",
        "V2 · Multi-resource deterministic planning",
        "V3 Simulator · Dynamic stochastic evacuation",
        "V3 Policy Study · PPO tested and rejected",
        "V3 Retrieval Study · Hybrid supported vs Dense",
    ]
    st.markdown(
        '<div class="flow">'
        + '<span class="flow-arrow">→</span>'.join(
            f'<span class="flow-step">{html.escape(step)}</span>' for step in timeline
        )
        + "</div>",
        unsafe_allow_html=True,
    )

st.divider()
st.caption("Sentinel-Agent V3 · Synthetic evacuation research prototype · Not validated for operational emergency response")
