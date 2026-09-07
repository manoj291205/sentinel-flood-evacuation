#!/usr/bin/env python3
"""Generate the Phase 13A MACHINE_PROPOSED question and passage review packet."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.benchmark import (  # noqa: E402
    BENCHMARK_SPEC_VERSION,
    CANDIDATE_BENCHMARK_VERSION,
    FUTURE_GOLD_VERSION,
    POOL_CAP,
    POOL_DEPTH,
    QUERY_STYLES,
    TARGET_ACCEPTED_QUESTIONS,
    TARGET_PER_STYLE,
    TARGET_PER_TOPIC,
    TOPICS,
    chunk_catalog,
    pool_question,
    validate_candidate_manifest,
)
from src.rag.ingest import prepare_corpus  # noqa: E402
from src.rag.retrieve import (  # noqa: E402
    BM25_METHOD_ID,
    DENSE_METHOD_ID,
    HYBRID_METHOD_ID,
    RETRIEVAL_CONFIG_VERSION,
    RetrievalMethod,
    clear_retriever_cache,
    frozen_corpus_identity,
    get_retriever,
    tokenize,
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "eval_v3" / "phase13"
MANIFEST_PATH = OUTPUT_DIR / "candidate_question_manifest.json"
QUESTION_REVIEW_PATH = OUTPUT_DIR / "question_review.csv"
PASSAGE_REVIEW_PATH = OUTPUT_DIR / "human_review.csv"
CONSISTENCY_PATH = OUTPUT_DIR / "review_consistency.csv"
PACKET_PATH = PROJECT_ROOT / "V3_RETRIEVAL_HUMAN_REVIEW.md"

FLOOD = "ndma-flood-guidelines-2008"
PLAN = "ndma-national-disaster-management-plan-2019"
SHELTER = "ndma-temporary-shelters-2019"

# These questions were drafted from direct inspection of the stated source pages. The
# retrievers are not consulted until after every question and source location is fixed.
# tuple: question, topic, style, source, PDF page, anchor terms, explanation,
# machine-proposed supporting source IDs (for later human verification).
CANDIDATE_DEFINITIONS = [
    # Flood risk / management: four lexical, four semantic, four operational.
    ("What is the purpose of flood plain zoning in reducing flood damage?", TOPICS[0], QUERY_STYLES[0], FLOOD, 78, ["flood", "plain", "zoning", "damage"], "The source explains the land-use purpose and limits of flood-plain zoning.", [FLOOD]),
    ("What information should flood forecasting and warning systems provide to exposed areas?", TOPICS[0], QUERY_STYLES[0], FLOOD, 96, ["forecasting", "warning", "water", "inundated"], "The implementation plan lists information expected from forecasting and warning systems.", [FLOOD, PLAN]),
    ("How should flood shelters and disaster relief centres be located?", TOPICS[0], QUERY_STYLES[0], FLOOD, 56, ["flood", "shelters", "high", "ground"], "The preparedness measures directly address shelter and relief-centre siting.", [FLOOD, SHELTER]),
    ("What mapping activities belong in flood management plans?", TOPICS[0], QUERY_STYLES[0], FLOOD, 96, ["flood", "vulnerability", "risk", "maps"], "The guideline enumerates hazard, risk, and vulnerability mapping activities.", [FLOOD]),
    ("Why can development in areas naturally used by rivers increase disaster losses?", TOPICS[0], QUERY_STYLES[1], FLOOD, 64, ["river", "flood", "plains", "damage"], "The source links unplanned flood-plain use to reported damage.", [FLOOD]),
    ("How can modelling future situations help authorities prepare for flooding?", TOPICS[0], QUERY_STYLES[1], FLOOD, 86, ["scenario", "simulation", "preparedness", "risk"], "The research section describes scenario analysis and simulation as preparedness tools.", [FLOOD]),
    ("What health problems can follow when flooding damages essential infrastructure?", TOPICS[0], QUERY_STYLES[1], FLOOD, 66, ["health", "water", "sanitation", "diseases"], "The medical-preparedness passage links flooding, damaged services, and health effects.", [FLOOD, PLAN]),
    ("Why should warnings use information that local communities can readily understand?", TOPICS[0], QUERY_STYLES[1], FLOOD, 96, ["warning", "information", "understood", "areas"], "The plan calls for public warning information presented in an understandable form.", [FLOOD, PLAN]),
    ("Which infrastructure connections should planners identify to keep relief moving during floods?", TOPICS[0], QUERY_STYLES[2], FLOOD, 56, ["road", "rail", "relief", "centres"], "The preparedness list identifies transport and communication links to relief centres.", [FLOOD, PLAN]),
    ("How should officials decide the scale and coordination level of a flood response?", TOPICS[0], QUERY_STYLES[2], FLOOD, 89, ["scale", "response", "magnitude", "severity"], "The response chapter ties mobilization level to event magnitude and severity.", [FLOOD, PLAN]),
    ("What should a local flood plan document before an emergency occurs?", TOPICS[0], QUERY_STYLES[2], FLOOD, 96, ["plan", "identification", "flood", "areas"], "The source lists advance planning activities for flood-management plans.", [FLOOD]),
    ("What resources should authorities arrange to sustain flood rescue and relief operations?", TOPICS[0], QUERY_STYLES[2], FLOOD, 92, ["relief", "supplies", "rescue", "transport"], "The response passage identifies infrastructure, equipment, supplies, and logistics support.", [FLOOD, PLAN]),

    # Evacuation / movement.
    ("What elements should an emergency evacuation plan establish and test?", TOPICS[1], QUERY_STYLES[0], FLOOD, 89, ["evacuation", "plans", "testing", "procedures"], "The evacuation section lists planning, validation, competence, and procedure testing.", [FLOOD, PLAN]),
    ("Which agencies support evacuation of people and animals during a major disaster?", TOPICS[1], QUERY_STYLES[0], PLAN, 310, ["evacuation", "people", "animals", "agencies"], "The national response matrix names lead and supporting bodies for evacuation.", [PLAN]),
    ("What should authorities identify and display when planning evacuation routes?", TOPICS[1], QUERY_STYLES[0], PLAN, 306, ["evacuation", "routes", "identify", "display"], "The preparedness matrix specifies route and refuge-area identification.", [PLAN, FLOOD]),
    ("What does a patient evacuation plan need for safe medical movement?", TOPICS[1], QUERY_STYLES[0], FLOOD, 66, ["patient", "evacuation", "medical", "equipment"], "The medical section describes personnel, equipment, triage, and movement needs.", [FLOOD, PLAN]),
    ("How should planners account for people who may need extra help leaving a hazardous area?", TOPICS[1], QUERY_STYLES[1], PLAN, 115, ["disabilities", "evacuation", "assistance", "local"], "The disability discussion addresses evacuation barriers and locally organized assistance.", [PLAN, SHELTER]),
    ("When might residents need to move after water has already entered their community?", TOPICS[1], QUERY_STYLES[1], FLOOD, 89, ["evacuation", "flooded", "safer", "area"], "The flood guideline distinguishes precautionary and post-inundation movement.", [FLOOD]),
    ("How should response plans handle visitors stranded in remote mountain areas?", TOPICS[1], QUERY_STYLES[1], PLAN, 310, ["visitors", "stranded", "remote", "evacuation"], "The national matrix gives remote stranded visitors as a special evacuation situation.", [PLAN]),
    ("Why are several reliable ways into and out of a shelter area important?", TOPICS[1], QUERY_STYLES[1], PLAN, 256, ["multiple", "routes", "access", "escape"], "The plan calls for multiple routes supporting access and escape.", [PLAN, SHELTER]),
    ("When should officials begin moving flood-threatened people to safer surroundings?", TOPICS[1], QUERY_STYLES[2], FLOOD, 89, ["precautionary", "warning", "evacuation", "impact"], "The passage explains precautionary evacuation based on warning indicators before impact.", [FLOOD, PLAN]),
    ("Who should be involved in coordinating a large community evacuation?", TOPICS[1], QUERY_STYLES[2], FLOOD, 89, ["stakeholders", "transportation", "health", "suppliers"], "The source lists warning, transport, health, supply, civil-society, and community actors.", [FLOOD, PLAN]),
    ("How should an evacuation route within a shelter site accommodate people with disabilities?", TOPICS[1], QUERY_STYLES[2], SHELTER, 40, ["disability", "route", "transportation", "facilities"], "The shelter standard describes an accessible route linking transport, facilities, and residences.", [SHELTER]),
    ("What national support may a state request for moving people and animals from threatened areas?", TOPICS[1], QUERY_STYLES[2], PLAN, 310, ["support", "state", "evacuation", "affected"], "The response matrix specifies central support on a state's request.", [PLAN]),

    # Temporary shelters / relief camps.
    ("What typologies are used to describe temporary shelter options?", TOPICS[2], QUERY_STYLES[0], SHELTER, 33, ["typologies", "assembly", "construction", "rental"], "The shelter guideline defines assembly, construction, and rental options.", [SHELTER]),
    ("How do emergency shelters differ from intermediate shelters in the recovery process?", TOPICS[2], QUERY_STYLES[0], SHELTER, 21, ["emergency", "intermediate", "short", "temporary"], "The guideline distinguishes immediate protection from mid-term shelter needs.", [SHELTER]),
    ("Which technical subjects are covered when planning temporary shelters?", TOPICS[2], QUERY_STYLES[0], SHELTER, 37, ["site", "planning", "design", "materials"], "The technical overview enumerates site, services, design, materials, and technology.", [SHELTER]),
    ("Which basic services must be arranged at temporary shelter sites?", TOPICS[2], QUERY_STYLES[0], SHELTER, 63, ["water", "sanitation", "electricity", "transport"], "The responsibility matrix lists essential site services and alternatives after disruption.", [SHELTER]),
    ("How should shelter support change as families progress toward permanent housing?", TOPICS[2], QUERY_STYLES[1], SHELTER, 25, ["evolve", "emergency", "intermediate", "permanent"], "The approach section describes continuously evolving shelter needs.", [SHELTER]),
    ("How can authorities avoid overlooking affected households absent from existing beneficiary lists?", TOPICS[2], QUERY_STYLES[1], SHELTER, 29, ["beneficiaries", "landless", "excluded", "families"], "The eligibility passage warns that existing lists can omit vulnerable households.", [SHELTER, PLAN]),
    ("Why should emergency accommodation not continue unchanged for an excessive period?", TOPICS[2], QUERY_STYLES[1], SHELTER, 25, ["relief", "camps", "continue", "needs"], "The source warns that prolonged relief camps fail to meet changing shelter needs.", [SHELTER]),
    ("Why should temporary housing assistance be treated as part of recovery rather than a passive handout?", TOPICS[2], QUERY_STYLES[1], SHELTER, 23, ["affected", "people", "passive", "housing"], "The guiding principles frame affected people as agents in a people-led recovery process.", [SHELTER]),
    ("What safety and privacy issues should be checked when laying out an intermediate shelter camp?", TOPICS[2], QUERY_STYLES[2], SHELTER, 39, ["safety", "privacy", "dark", "spaces"], "The site guidance addresses blind spots, dangerous spaces, privacy, and safety.", [SHELTER]),
    ("What should a shelter manager do when water or sanitation services are disrupted?", TOPICS[2], QUERY_STYLES[2], SHELTER, 63, ["disrupted", "alternate", "arrangements", "repair"], "The matrix requires alternate arrangements while damaged infrastructure is repaired.", [SHELTER, PLAN]),
    ("What factors should guide selection of a safe location for temporary accommodation?", TOPICS[2], QUERY_STYLES[2], SHELTER, 37, ["selection", "sites", "safe", "hazard"], "The technical guidance establishes source-based site selection and planning considerations.", [SHELTER]),
    ("What access features should planners require around shelters used during an emergency?", TOPICS[2], QUERY_STYLES[2], PLAN, 256, ["shelters", "facilities", "routes", "access"], "The national plan pairs shelter facilities with reliable access and escape routes.", [PLAN, SHELTER]),

    # Vulnerable groups / accessibility.
    ("Which groups receive explicit attention in inclusive disaster risk management?", TOPICS[3], QUERY_STYLES[0], PLAN, 108, ["gender", "elderly", "children", "disabilities"], "The social-inclusion chapter enumerates groups needing explicit attention.", [PLAN]),
    ("Why must disaster planning consider the specific requirements and strengths of older people?", TOPICS[3], QUERY_STYLES[0], PLAN, 113, ["older", "requirements", "vulnerability", "disasters"], "The elderly section explains why generic responses may overlook older people's needs.", [PLAN]),
    ("What local support measures can improve evacuation for persons with disabilities?", TOPICS[3], QUERY_STYLES[0], PLAN, 115, ["disabilities", "local", "support", "evacuation"], "The passage addresses local networks and advance identification of assistance needs.", [PLAN, SHELTER]),
    ("How should post-disaster housing programmes account for widows and single women?", TOPICS[3], QUERY_STYLES[0], PLAN, 110, ["widows", "single", "women", "shelters"], "The gender section warns against excluding women without land titles from shelter support.", [PLAN, SHELTER]),
    ("Why can treating all disaster survivors as one uniform group produce unfair outcomes?", TOPICS[3], QUERY_STYLES[1], PLAN, 107, ["homogenous", "disparities", "inequities", "vulnerable"], "The inclusion chapter links homogeneous treatment to overlooked structural inequalities.", [PLAN]),
    ("How can people facing several forms of exclusion disappear from emergency programmes?", TOPICS[3], QUERY_STYLES[1], PLAN, 108, ["multiple", "discrimination", "invisible", "emergency"], "The passage describes layered discrimination and invisibility in response programs.", [PLAN]),
    ("Why may sexual and gender minorities encounter greater barriers to disaster protection?", TOPICS[3], QUERY_STYLES[1], PLAN, 110, ["sexual", "gender", "minorities", "barriers"], "The source relates marginalization to barriers accessing protection.", [PLAN]),
    ("Which households are most likely to be missed when aid uses only pre-existing local lists?", TOPICS[3], QUERY_STYLES[1], SHELTER, 29, ["landless", "women", "tenant", "vulnerable"], "The eligibility section identifies several groups omitted from beneficiary lists.", [SHELTER, PLAN]),
    ("How should a camp layout protect women, older people, children, and people with disabilities?", TOPICS[3], QUERY_STYLES[2], SHELTER, 39, ["women", "elderly", "children", "disabilities"], "The layout guidance explicitly addresses safety and accessibility for these groups.", [SHELTER, PLAN]),
    ("What should connect a disability-friendly route through a temporary shelter site?", TOPICS[3], QUERY_STYLES[2], SHELTER, 40, ["disability", "route", "facilities", "residential"], "The standard specifies connections among transport, public facilities, and residential units.", [SHELTER]),
    ("Who is responsible for ensuring facilities for persons with disabilities in temporary shelters?", TOPICS[3], QUERY_STYLES[2], SHELTER, 49, ["provisions", "facilities", "persons", "disabilities"], "The stakeholder matrix makes disability provision an explicit shelter responsibility.", [SHELTER, PLAN]),
    ("How can local authorities identify residents who will need additional evacuation assistance?", TOPICS[3], QUERY_STYLES[2], PLAN, 115, ["detailed", "planning", "lists", "special"], "The disability section proposes local information and support arrangements before evacuation.", [PLAN, SHELTER]),

    # Logistics / transport / coordination.
    ("What temporary shelter materials should be stockpiled in regional stores?", TOPICS[4], QUERY_STYLES[0], SHELTER, 53, ["stockpile", "tents", "shelter", "materials"], "The stakeholder matrix lists materials for regional stocks and vendor arrangements.", [SHELTER]),
    ("What is the role of regional logistics facilities in temporary shelter response?", TOPICS[4], QUERY_STYLES[0], SHELTER, 54, ["regional", "logistics", "stocks", "shelters"], "The source links logistics facilities with response teams and non-food-item stocks.", [SHELTER, PLAN]),
    ("Which transportation services and routes require rapid restoration after a disaster?", TOPICS[4], QUERY_STYLES[0], PLAN, 321, ["transport", "restoration", "roads", "railway"], "The response matrix covers roads, public transport, rail, and equipment movement.", [PLAN]),
    ("What emergency support resources can be mobilized for moving relief supplies?", TOPICS[4], QUERY_STYLES[0], FLOOD, 92, ["equipment", "transport", "logistics", "supplies"], "The flood response passage names transport, logistics, pumps, equipment, and supplies.", [FLOOD, PLAN]),
    ("What practical burden should be considered when families must carry shelter materials from distribution points?", TOPICS[4], QUERY_STYLES[1], SHELTER, 45, ["transport", "vulnerable", "distribution", "sites"], "The tent guidance considers distance, economics, homeowners, and vulnerable individuals.", [SHELTER]),
    ("How should essential site services continue while damaged infrastructure is being fixed?", TOPICS[4], QUERY_STYLES[1], SHELTER, 63, ["alternate", "arrangements", "repair", "services"], "The matrix requires temporary alternatives alongside repair and restoration.", [SHELTER, PLAN]),
    ("Why do industrial emergency areas need more than one route for responders and evacuees?", TOPICS[4], QUERY_STYLES[1], PLAN, 256, ["wide", "roads", "multiple", "routes"], "The plan connects multiple routes with responder access and escape pathways.", [PLAN]),
    ("How should authorities use assistance offered by outside organizations during flood response?", TOPICS[4], QUERY_STYLES[1], FLOOD, 92, ["assistance", "receive", "utilise", "authorities"], "The source requires mechanisms to receive and optimally use assistance.", [FLOOD]),
    ("Which transport and communication links should a district verify before relief supplies are needed?", TOPICS[4], QUERY_STYLES[2], FLOOD, 56, ["transport", "communication", "supply", "areas"], "The preparedness list calls for identifying reliable supply-centre connections.", [FLOOD, PLAN]),
    ("How should transport agencies support movement of essential goods during recovery?", TOPICS[4], QUERY_STYLES[2], PLAN, 321, ["transportation", "essential", "goods", "recovery"], "The response matrix describes transport restoration for response and recovery needs.", [PLAN]),
    ("What airport actions help relief teams, equipment, supplies, and stranded passengers move again?", TOPICS[4], QUERY_STYLES[2], PLAN, 322, ["airport", "relief", "supplies", "passengers"], "The aviation response passage covers runway restoration and relief movement.", [PLAN]),
    ("How should local teams coordinate incoming temporary shelter supplies without duplicating work?", TOPICS[4], QUERY_STYLES[2], SHELTER, 54, ["supplies", "coordination", "avoid", "duplication"], "The stakeholder matrix addresses receipt, coordination, and avoidance of duplicate supply activity.", [SHELTER, PLAN]),
]


def resolve_seed(definition, catalog):
    question, topic, style, source_id, page, anchors, explanation, supporting_sources = definition
    choices = [
        chunk for chunk in catalog.values()
        if chunk.source_id == source_id and chunk.page == page
    ]
    if not choices:
        raise ValueError(f"no canonical chunks for {source_id} PDF page {page}")
    anchor_tokens = [token for anchor in anchors for token in tokenize(anchor)]

    def score(chunk):
        frequencies = Counter(tokenize(chunk.text))
        return (
            sum(frequencies[token] > 0 for token in set(anchor_tokens)),
            sum(frequencies[token] for token in anchor_tokens),
        )

    seed = sorted(choices, key=lambda chunk: (-score(chunk)[0], -score(chunk)[1], chunk.chunk_id))[0]
    matched = sum(token in set(tokenize(seed.text)) for token in anchor_tokens)
    if matched < min(2, len(set(anchor_tokens))):
        raise ValueError(f"weak anchor match for {question!r}: {seed.chunk_id}")
    lowered = seed.text.casefold()
    positions = [lowered.find(anchor.casefold()) for anchor in anchors]
    positions = [position for position in positions if position >= 0]
    possible_starts = {0, *(max(0, position - 180) for position in positions)}

    def window_score(window_start):
        window_tokens = tokenize(seed.text[window_start:window_start + 650])
        frequencies = Counter(window_tokens)
        return (
            sum(frequencies[token] > 0 for token in set(anchor_tokens)),
            sum(frequencies[token] for token in anchor_tokens),
            -window_start,
        )

    start = max(possible_starts, key=window_score)
    end = min(len(seed.text), start + 650)
    if start:
        next_space = seed.text.find(" ", start)
        start = next_space + 1 if next_space >= 0 else start
    if end < len(seed.text):
        previous_space = seed.text.rfind(" ", start, end)
        end = previous_space if previous_space > start else end
    excerpt = seed.text[start:end]
    return {
        "question": question,
        "primary_topic": topic,
        "query_style": style,
        "machine_proposed_answerable": True,
        "machine_proposed_source_id": seed.source_id,
        "machine_proposed_filename": seed.filename,
        "machine_proposed_page": seed.page,
        "page_convention": "one-based physical PDF page index",
        "machine_proposed_chunk_id": seed.chunk_id,
        "machine_proposed_supporting_excerpt": excerpt,
        "machine_explanation": explanation,
        "machine_proposed_supporting_source_ids": supporting_sources,
        "machine_proposed_multi_source": len(supporting_sources) > 1,
        "proposal_status": "MACHINE_PROPOSED",
    }


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(CANDIDATE_DEFINITIONS) != 60:
        raise ValueError(f"expected exactly 60 definitions, got {len(CANDIDATE_DEFINITIONS)}")
    version, fingerprint = frozen_corpus_identity()
    prepared = prepare_corpus()
    catalog = chunk_catalog(prepared)
    candidates = []
    for index, definition in enumerate(CANDIDATE_DEFINITIONS, start=1):
        candidate = resolve_seed(definition, catalog)
        candidate["candidate_question_id"] = f"Q{index:03d}"
        candidates.append(candidate)

    topic_counts = Counter(item["primary_topic"] for item in candidates)
    style_counts = Counter(item["query_style"] for item in candidates)
    source_counts = Counter(item["machine_proposed_source_id"] for item in candidates)
    manifest = {
        "benchmark_spec_version": BENCHMARK_SPEC_VERSION,
        "candidate_benchmark_version": CANDIDATE_BENCHMARK_VERSION,
        "future_human_gold_version_reserved": FUTURE_GOLD_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "corpus_version": version,
        "corpus_fingerprint": fingerprint,
        "retrieval_config": RETRIEVAL_CONFIG_VERSION,
        "retrieval_methods": [DENSE_METHOD_ID, BM25_METHOD_ID, HYBRID_METHOD_ID],
        "candidate_count": len(candidates),
        "target_human_accepted_count": TARGET_ACCEPTED_QUESTIONS,
        "target_final_topic_count_each": TARGET_PER_TOPIC,
        "target_final_query_style_count_each": TARGET_PER_STYLE,
        "candidate_topic_counts": dict(topic_counts),
        "candidate_query_style_counts": dict(style_counts),
        "machine_seed_source_counts": dict(source_counts),
        "machine_proposed_multi_source_candidate_count": sum(
            item["machine_proposed_multi_source"] for item in candidates
        ),
        "human_accepted_questions": 0,
        "human_passage_labels": 0,
        "human_review_status": "WAITING_FOR_HUMAN_REVIEW",
        "official_retrieval_metrics_calculated": False,
        "_warning": (
            "All questions, seed evidence, explanations, and suggested grades are "
            "MACHINE_PROPOSED and are not human-confirmed gold truth."
        ),
        "candidates": candidates,
    }
    validate_candidate_manifest(manifest, catalog)

    clear_retriever_cache()
    retrievers = {
        "dense": get_retriever(RetrievalMethod.DENSE),
        "bm25": get_retriever(RetrievalMethod.BM25),
        "hybrid": get_retriever(RetrievalMethod.HYBRID_RRF),
    }
    pools = {
        item["candidate_question_id"]: pool_question(item, catalog, retrievers)
        for item in candidates
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    question_fields = [
        "question_id", "question", "topic", "query_style",
        "machine_proposed_answerable", "machine_seed_source", "machine_seed_page",
        "human_question_status", "human_edited_question", "human_notes",
    ]
    question_rows = [
        {
            "question_id": item["candidate_question_id"],
            "question": item["question"],
            "topic": item["primary_topic"],
            "query_style": item["query_style"],
            "machine_proposed_answerable": "MACHINE_PROPOSED_TRUE",
            "machine_seed_source": item["machine_proposed_source_id"],
            "machine_seed_page": item["machine_proposed_page"],
            "human_question_status": "PENDING",
            "human_edited_question": "",
            "human_notes": "",
        }
        for item in candidates
    ]
    write_csv(QUESTION_REVIEW_PATH, question_fields, question_rows)

    passage_fields = [
        "question_id", "question", "topic", "query_style", "chunk_id", "source_id",
        "filename", "page", "excerpt", "dense_rank", "bm25_rank", "hybrid_rank",
        "machine_seed_evidence", "machine_suggested_grade", "human_grade",
        "human_review_status", "human_notes",
    ]
    passage_rows = []
    for item in candidates:
        for passage in pools[item["candidate_question_id"]]:
            passage_rows.append({
                "question_id": item["candidate_question_id"],
                "question": item["question"],
                "topic": item["primary_topic"],
                "query_style": item["query_style"],
                "chunk_id": passage["chunk_id"],
                "source_id": passage["source_id"],
                "filename": passage["filename"],
                "page": passage["page"],
                "excerpt": passage["excerpt"],
                "dense_rank": passage["dense_rank"] or "",
                "bm25_rank": passage["bm25_rank"] or "",
                "hybrid_rank": passage["hybrid_rank"] or "",
                "machine_seed_evidence": str(passage["machine_seed_evidence"]).upper(),
                "machine_suggested_grade": passage["machine_suggested_grade"],
                "human_grade": "",
                "human_review_status": "PENDING",
                "human_notes": "",
            })
    write_csv(PASSAGE_REVIEW_PATH, passage_fields, passage_rows)

    consistency_fields = [
        "question_id", "chunk_id", "first_pass_grade", "second_pass_grade",
        "second_pass_status", "consistency_notes",
    ]
    # Selection happens only after exactly 45 questions are human accepted/edited.
    write_csv(CONSISTENCY_PATH, consistency_fields, [])

    lines = [
        "# Sentinel-Agent V3 — Human Retrieval Review Packet",
        "",
        "> **STATUS: WAITING FOR HUMAN REVIEW.** Every question, seed, explanation, and",
        "> suggested grade below is `MACHINE_PROPOSED`. No human question has been",
        "> accepted and no human passage grade has been supplied.",
        "",
        "## Reviewer instructions",
        "",
        "For each question, enter `ACCEPT`, `EDIT`, or `REJECT` in `question_review.csv`.",
        "Use `human_edited_question` only for `EDIT`. For each passage of every retained",
        "question, enter a human grade and set status to `COMPLETE` in `human_review.csv`.",
        "",
        "- **2 — DIRECTLY RELEVANT:** directly answers or materially supports the exact question.",
        "- **1 — PARTIALLY RELEVANT:** useful context but insufficient by itself.",
        "- **0 — NOT RELEVANT:** does not materially help answer the exact question.",
        "",
        "Judge whether you would cite the passage for this question—not whether it is merely",
        "on the same broad topic. Seed evidence is not automatically relevant. `page` means",
        "the one-based physical PDF page index used by the corpus.",
        "",
        "> Relevance judgments are based on a pooled candidate set from the three evaluated",
        "> retrieval systems plus source-derived seed evidence. Relevant chunks outside the",
        "> pool may exist.",
        "",
        f"Pool: top {POOL_DEPTH} per method; retain cross-method passages, every method's top",
        f"five, and seed evidence; deterministic cap {POOL_CAP}.",
        "",
    ]
    for item in candidates:
        question_id = item["candidate_question_id"]
        lines += [
            f"## {question_id} — MACHINE_PROPOSED",
            "",
            f"**Question:** {item['question']}",
            "",
            f"**Topic:** `{item['primary_topic']}`",
            f"**Query style:** `{item['query_style']}`",
            "",
            "### Proposed seed evidence — not human-confirmed",
            "",
            f"- Document: `{item['machine_proposed_filename']}`",
            f"- Source ID: `{item['machine_proposed_source_id']}`",
            f"- PDF page: {item['machine_proposed_page']}",
            f"- Chunk: `{item['machine_proposed_chunk_id']}`",
            f"- Machine explanation: {item['machine_explanation']}",
            "",
            "> " + item["machine_proposed_supporting_excerpt"].replace("\n", " ").rstrip(),
            "",
            "**HUMAN QUESTION STATUS:** __________",
            "**HUMAN EDITED QUESTION (if needed):** __________",
            "",
            "### Candidate passages",
            "",
        ]
        for number, passage in enumerate(pools[question_id], start=1):
            ranks = ", ".join(
                f"{name} #{passage[f'{name}_rank']}"
                for name in ("dense", "bm25", "hybrid")
                if passage[f"{name}_rank"] is not None
            ) or "seed only"
            lines += [
                f"#### Passage {number}",
                "",
                f"- Chunk: `{passage['chunk_id']}`",
                f"- Document: `{passage['filename']}`",
                f"- Source ID: `{passage['source_id']}`",
                f"- PDF page: {passage['page']}",
                f"- Retrieved by: {ranks}",
                f"- Machine seed evidence: `{str(passage['machine_seed_evidence']).upper()}`",
                f"- Machine suggested grade: `{passage['machine_suggested_grade'] or 'NONE'}`",
                "",
                "> " + passage["excerpt"].replace("\n", " ").rstrip(),
                "",
                "**HUMAN GRADE:** ___",
                "**HUMAN REVIEW STATUS:** PENDING",
                "**HUMAN NOTES:** __________",
                "",
            ]
    PACKET_PATH.write_text("\n".join(lines).rstrip() + "\n")

    print(f"Wrote {len(candidates)} candidate questions")
    print(f"Topic counts: {dict(topic_counts)}")
    print(f"Style counts: {dict(style_counts)}")
    print(f"Seed source counts: {dict(source_counts)}")
    print(f"Machine-proposed multi-source candidates: {manifest['machine_proposed_multi_source_candidate_count']}")
    print(f"Passage review rows: {len(passage_rows)} (max {POOL_CAP} per question)")
    print("Human accepted questions: 0; human passage labels: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
