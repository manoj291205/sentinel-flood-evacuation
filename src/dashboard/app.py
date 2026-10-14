"""Sentinel-Agent evacuation decision dashboard.

Single-page Streamlit app. Renders what the pipeline produced -- it does not
reimplement any decision logic:

  scenario (Step 1) -> retrieved NDMA text (Step 2) -> Gemini constraints (Step 3)
  -> MaskablePPO policy (Step 4) -> this page

Reads the CACHED constraint output, so it never calls the Gemini API and runs with no
network at all.

Colour follows the validated reference palette: flood severity is a SEQUENTIAL single-hue
blue ramp (magnitude), and verdicts use the fixed status palette. The validator reports
the good/critical pair at CVD delta-E 4.1 (deuteranopia) -- red-vs-green is invisible to a
deuteranope -- so every verdict carries an ICON AND A TEXT LABEL, with colour as
reinforcement only. Severity is likewise printed numerically in every cell, never
conveyed by shade alone.

Run:  .venv/bin/streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.constraints.generate import (  # noqa: E402
    CACHE_PATH,
    load_scenario,
    shelter_facts,
)
from src.env.shelter_env import ShelterChoiceEnv  # noqa: E402

MODEL_PATH = PROJECT_ROOT / "models" / "maskable_ppo_shelter.zip"

# --- palette (validated reference instance, light surface) ------------------------------
SEQ_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
            "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
SURFACE = "#fcfcfb"
GRIDLINE = "#e1e0d9"
BORDER = "rgba(11,11,11,0.10)"

st.set_page_config(
    page_title="Sentinel-Agent — Evacuation Decision Support",
    page_icon="🌊",
    layout="wide",
)


# --- data loading -----------------------------------------------------------------------


@st.cache_data
def get_scenario() -> dict:
    return load_scenario()


@st.cache_data
def get_constraints() -> dict | None:
    """Read the CACHED Step 3 output. Never calls the API from the dashboard."""
    if not CACHE_PATH.exists():
        return None
    import json

    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


@st.cache_resource
def get_model():
    if not MODEL_PATH.exists():
        return None
    from sb3_contrib import MaskablePPO

    return MaskablePPO.load(MODEL_PATH, device="cpu")


def severity_colour(value: float) -> str:
    index = int(np.clip(value, 0.0, 1.0) * (len(SEQ_BLUE) - 1))
    return SEQ_BLUE[index]


def readable_on(hex_colour: str) -> str:
    """Black or white ink, whichever is legible on the given fill."""
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return INK_PRIMARY if luminance > 0.55 else "#ffffff"


def decide(model, env) -> tuple[int, float, dict]:
    from sb3_contrib.common.maskable.utils import get_action_masks

    obs, _ = env.reset()
    masks = get_action_masks(env)
    action, _ = model.predict(obs, action_masks=masks, deterministic=True)
    _, reward, _, _, info = env.step(int(action))
    return int(action), float(reward), info


# --- page -------------------------------------------------------------------------------

st.markdown(
    f"""
    <style>
      .block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
      .prov {{
        background:{SURFACE}; border:1px solid {BORDER}; border-left:3px solid {INK_MUTED};
        border-radius:6px; padding:0.7rem 0.95rem; font-size:0.82rem;
        color:{INK_SECONDARY}; line-height:1.5; margin-bottom:1.4rem;
      }}
      .tile {{
        background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px;
        padding:1.0rem 1.15rem; height:100%;
      }}
      .tile-label {{ font-size:0.72rem; letter-spacing:0.06em; text-transform:uppercase;
                     color:{INK_MUTED}; margin-bottom:0.3rem; }}
      .tile-value {{ font-size:2.0rem; font-weight:650; color:{INK_PRIMARY}; line-height:1.1; }}
      .tile-sub {{ font-size:0.8rem; color:{INK_SECONDARY}; margin-top:0.25rem; }}
      .badge {{ display:inline-block; padding:0.12rem 0.5rem; border-radius:999px;
                font-size:0.73rem; font-weight:650; letter-spacing:0.02em; }}
      .cell {{ border-radius:8px; padding:0.6rem 0.55rem; min-height:104px;
               border:1px solid {BORDER}; }}
      .cell-id {{ font-size:0.68rem; letter-spacing:0.05em; opacity:0.85; }}
      .cell-sev {{ font-size:1.15rem; font-weight:650; font-variant-numeric:tabular-nums; }}
      .cell-tag {{ font-size:0.7rem; margin-top:0.15rem; line-height:1.35; }}
      .quote {{ border-left:3px solid {GRIDLINE}; padding:0.5rem 0.85rem; margin:0.45rem 0 0.2rem 0;
                color:{INK_SECONDARY}; font-size:0.87rem; line-height:1.55; }}
      table.shelters {{ width:100%; border-collapse:collapse; font-size:0.88rem; }}
      table.shelters th {{ text-align:left; font-size:0.7rem; letter-spacing:0.05em;
                           text-transform:uppercase; color:{INK_MUTED};
                           border-bottom:1px solid {GRIDLINE}; padding:0.42rem 0.55rem; }}
      table.shelters td {{ border-bottom:1px solid {GRIDLINE}; padding:0.46rem 0.55rem;
                           color:{INK_PRIMARY}; }}
      table.shelters td.num {{ font-variant-numeric:tabular-nums; text-align:right; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Sentinel-Agent — Flood Evacuation Decision Support")
st.markdown(
    '<div class="prov"><b>What is real and what is not.</b> The guideline document behind '
    "every citation on this page is genuine: <i>National Disaster Management Guidelines: "
    "Management of Floods</i> (NDMA, Government of India, 17 January 2008). "
    "<b>Everything else on this page is fictional</b> — the grid, the cells, all seven "
    "shelters, their capacities, statuses, flood-severity values and travel costs are "
    "invented for this prototype, inspired by the 2018 Kerala floods but using a "
    "simplified fictional grid for demo purposes. This is <b>not</b> real GPS or "
    "administrative data, and the verdicts below are a language model's judgements about "
    "fictional shelters — not determinations by any agency.</div>",
    unsafe_allow_html=True,
)

scenario = get_scenario()
constraints = get_constraints()
model = get_model()

if constraints is None:
    st.error(
        "No constraint output found. Generate it first:\n\n"
        "`.venv/bin/python -m src.constraints.test_constraints --refresh`"
    )
    st.stop()
if model is None:
    st.error(
        "No trained policy found. Train it first:\n\n"
        "`.venv/bin/python -m src.env.train`"
    )
    st.stop()

facts = {f["shelter_id"]: f for f in shelter_facts(scenario)}
verdicts = {c["action_id"]: c for c in constraints["constraints"]}
population = scenario["source"]["population_to_evacuate"]
cells = {c["cell_id"]: c for c in scenario["grid"]["cells"]}

# Decision WITH the real Gemini constraint mask.
env = ShelterChoiceEnv(randomise=False, constraint_payload=constraints)
action, reward, info = decide(model, env)
chosen = env.shelter_ids[action]

# Decision WITHOUT any constraints -- computed by actually re-running the policy on an
# all-allowed mask, never hardcoded.
env_open = ShelterChoiceEnv(randomise=False, constraint_payload=constraints)
env_open.fixed_mask = np.ones(env_open.n, dtype=bool)
action_open, reward_open, _ = decide(model, env_open)
chosen_open = env_open.shelter_ids[action_open]

# --- the recommendation -----------------------------------------------------------------

st.subheader("Recommendation")

chosen_fact = facts[chosen]
fits = chosen_fact["capacity_headroom"] >= population
cols = st.columns(4)
tiles = [
    ("Send evacuees to", chosen, f"cell {chosen_fact['cell_id']} · flood severity "
     f"{chosen_fact['flood_severity']}"),
    ("Travel time", f"{chosen_fact['travel_cost_minutes']:g} min", "from the flooded source cell"),
    ("Spare capacity", f"{chosen_fact['capacity_headroom']:,}",
     f"{'takes all ' + format(population, ',') if fits else 'CANNOT take all ' + format(population, ',')}"),
    ("Policy score", f"{reward:.3f}",
     "optimal among allowed" if info["regret"] < 1e-9
     else f"SUBOPTIMAL — {info['optimal_shelter_id']} scores "
          f"{info['optimal_reward']:.3f} (regret {info['regret']:.3f})"),
]
for col, (label, value, sub) in zip(cols, tiles):
    col.markdown(
        f'<div class="tile"><div class="tile-label">{label}</div>'
        f'<div class="tile-value">{value}</div>'
        f'<div class="tile-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")

# --- the constraint comparison ----------------------------------------------------------

show_unconstrained = st.toggle(
    "Show what this system would recommend **without** the RAG-grounded constraint step",
    value=False,
    help="Drops the Gemini action mask and re-runs the same trained policy.",
)

if show_unconstrained:
    open_fact = facts[chosen_open]
    open_cell = cells[open_fact["cell_id"]]
    left, right = st.columns(2)
    left.markdown(
        f'<div class="tile" style="border-left:3px solid {STATUS_GOOD};">'
        f'<div class="tile-label">✓ With constraints</div>'
        f'<div class="tile-value">{chosen}</div>'
        f'<div class="tile-sub">flood severity {chosen_fact["flood_severity"]} · '
        f'{chosen_fact["travel_cost_minutes"]:g} min · score {reward:.3f}</div></div>',
        unsafe_allow_html=True,
    )
    right.markdown(
        f'<div class="tile" style="border-left:3px solid {STATUS_CRITICAL};">'
        f'<div class="tile-label">✕ Without constraints</div>'
        f'<div class="tile-value">{chosen_open}</div>'
        f'<div class="tile-sub">flood severity {open_fact["flood_severity"]} '
        f'({open_cell["severity_band"]}) · {open_fact["travel_cost_minutes"]:g} min · '
        f'score {reward_open:.3f}</div></div>',
        unsafe_allow_html=True,
    )
    if chosen_open != chosen:
        st.markdown(
            f'<div class="prov" style="border-left-color:{STATUS_CRITICAL};">'
            f"<b>✕ Unsafe recommendation.</b> Unconstrained, the policy picks "
            f"<b>{chosen_open}</b> — it is the closest shelter at "
            f"{open_fact['travel_cost_minutes']:g} min and has room for all {population:,} "
            f"people, so it scores highest on capacity and travel alone. But it sits in a "
            f"<b>{open_cell['severity_band']}</b> flood cell (severity "
            f"{open_fact['flood_severity']}). The constraint step, grounded in the real NDMA "
            f"guidelines, is what removes it from consideration.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="prov">On this scenario the constraint mask does not change the '
            "choice — the reward function already disfavours the excluded shelters.</div>",
            unsafe_allow_html=True,
        )

st.divider()

# --- the grid ---------------------------------------------------------------------------

st.subheader("Hazard grid")
st.caption(
    f"Fictional 3×3 grid. Shade and the printed number both show flood severity "
    f"(0.0 dry → 1.0 fully inundated). Source cell "
    f"{scenario['source']['cell_id']} holds {population:,} people needing evacuation."
)

shelters_by_cell: dict[str, list[str]] = {}
for shelter_id, fact in facts.items():
    shelters_by_cell.setdefault(fact["cell_id"], []).append(shelter_id)

for row in range(scenario["grid"]["rows"]):
    row_cols = st.columns(scenario["grid"]["cols"])
    for col_index in range(scenario["grid"]["cols"]):
        cell = next(
            c for c in scenario["grid"]["cells"]
            if c["row"] == row and c["col"] == col_index
        )
        fill = severity_colour(cell["flood_severity"])
        ink = readable_on(fill)
        tags = []
        if cell["cell_id"] == scenario["source"]["cell_id"]:
            tags.append("◉ SOURCE — evacuate")
        for shelter_id in shelters_by_cell.get(cell["cell_id"], []):
            allowed = verdicts[shelter_id]["status"] == "allowed"
            icon = "✓" if allowed else "✕"
            word = "ALLOWED" if allowed else "EXCLUDED"
            star = " ★ CHOSEN" if shelter_id == chosen else ""
            tags.append(f"{icon} {shelter_id} {word}{star}")
        row_cols[col_index].markdown(
            f'<div class="cell" style="background:{fill}; color:{ink};">'
            f'<div class="cell-id">{cell["cell_id"]}</div>'
            f'<div class="cell-sev">{cell["flood_severity"]:.2f}</div>'
            f'<div class="cell-tag">{cell["severity_band"]}</div>'
            + "".join(f'<div class="cell-tag">{t}</div>' for t in tags)
            + "</div>",
            unsafe_allow_html=True,
        )

st.divider()

# --- shelter table ----------------------------------------------------------------------

st.subheader("All candidate shelters")

rows = []
for shelter_id in sorted(facts):
    fact = facts[shelter_id]
    verdict = verdicts[shelter_id]
    allowed = verdict["status"] == "allowed"
    colour = STATUS_GOOD if allowed else STATUS_CRITICAL
    icon = "✓" if allowed else "✕"
    word = "ALLOWED" if allowed else "EXCLUDED"
    index = env.shelter_ids.index(shelter_id)
    star = " ★" if shelter_id == chosen else ""
    rows.append(
        f"<tr><td><b>{shelter_id}</b>{star}</td><td>{fact['cell_id']}</td>"
        f"<td class='num'>{fact['flood_severity']:.2f}</td>"
        f"<td>{cells[fact['cell_id']]['severity_band']}</td>"
        f"<td class='num'>{fact['capacity_headroom']:,}</td>"
        f"<td class='num'>{fact['travel_cost_minutes']:g}</td>"
        f"<td>{fact['status'].replace('_', ' ')}</td>"
        f"<td class='num'>{env.rewards[index]:.3f}</td>"
        f"<td><span class='badge' style='background:{colour}1f; color:{colour};'>"
        f"{icon} {word}</span></td></tr>"
    )

st.markdown(
    "<table class='shelters'><thead><tr>"
    "<th>Shelter</th><th>Cell</th><th>Severity</th><th>Band</th><th>Spare</th>"
    "<th>Travel (min)</th><th>Status</th><th>Score</th><th>Verdict</th>"
    "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>",
    unsafe_allow_html=True,
)
st.caption(
    "★ marks the recommended shelter. Score is the reward the policy would receive; "
    "excluded shelters are structurally unselectable regardless of their score."
)

st.divider()

# --- exclusion evidence -----------------------------------------------------------------

st.subheader("Why each shelter was excluded")
st.caption(
    "Every exclusion below was produced by a single structured Gemini call grounded in "
    "retrieved text from the real NDMA guidelines. VERIFIED means the quote was found "
    "verbatim in the retrieved text; UNVERIFIED means it was not, and should not be "
    "trusted as a quote."
)

excluded = [sid for sid in sorted(verdicts) if verdicts[sid]["status"] == "excluded"]
pages = {
    (m["source_document"], m["page"])
    for m in constraints.get("_meta", {}).get("retrieved_chunks", [])
}

for shelter_id in excluded:
    verdict = verdicts[shelter_id]
    fact = facts[shelter_id]
    ok = verdict.get("citation_verified", False)
    badge_colour = STATUS_GOOD if ok else STATUS_CRITICAL
    badge_text = "✓ VERIFIED verbatim" if ok else "✕ UNVERIFIED — not found verbatim"

    with st.expander(
        f"✕  {shelter_id} — {verdict['reason'][:96]}"
        + ("…" if len(verdict["reason"]) > 96 else ""),
        expanded=(shelter_id == chosen_open),
    ):
        st.markdown(
            f"**Reason.** {verdict['reason']}\n\n"
            f"*Shelter facts:* cell {fact['cell_id']}, flood severity "
            f"{fact['flood_severity']} ({cells[fact['cell_id']]['severity_band']}), "
            f"spare capacity {fact['capacity_headroom']:,} of {population:,} needed, "
            f"status `{fact['status']}`, {fact['travel_cost_minutes']:g} min away."
        )
        st.markdown(
            f'<div class="quote">“{verdict["source_excerpt"]}”</div>', unsafe_allow_html=True
        )
        st.markdown(
            f"<span style='font-size:0.82rem;color:{INK_SECONDARY};'>"
            f"Source: <b>{verdict['source_document']}</b> — "
            f"NDMA, Government of India, 17 January 2008</span> &nbsp; "
            f"<span class='badge' style='background:{badge_colour}1f;color:{badge_colour};'>"
            f"{badge_text}</span>",
            unsafe_allow_html=True,
        )

allowed_ids = [sid for sid in sorted(verdicts) if verdicts[sid]["status"] == "allowed"]
st.markdown(
    f"<div class='prov'><b>✓ {len(allowed_ids)} shelter(s) allowed:</b> "
    f"{', '.join(allowed_ids)} &nbsp;·&nbsp; <b>✕ {len(excluded)} excluded:</b> "
    f"{', '.join(excluded)}<br>"
    f"Constraints generated by <code>{constraints['_meta']['model']}</code> in "
    f"{constraints['_meta']['attempts_used']} attempt(s), grounded in text retrieved "
    f"from {len(pages)} distinct page(s) of that document. Policy: MaskablePPO (sb3-contrib). "
    f"No API call is made when this page loads — the constraint output is read from "
    f"a cached file, so this demo runs with no network.</div>",
    unsafe_allow_html=True,
)
