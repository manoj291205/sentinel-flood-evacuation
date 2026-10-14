"""The RAG-grounded constraint step: one structured Gemini call per scenario.

Takes the scenario state plus retrieved NDMA guideline chunks, and returns a validated
JSON object marking every candidate shelter `allowed` or `excluded`, each with a
one-sentence reason and the guideline clause it rests on.

Per DEVELOPMENT.md this is EXACTLY ONE structured LLM call per scenario -- not a
rule-extraction or conflict-arbitration pipeline. The output schema is fixed there and
every later step depends on its exact shape.

Free tier only: gemini-3.6-flash via the google-genai package, keyed by the GEMINI_API_KEY
environment variable. Retrieval and embedding stay local (Step 2); this is the only step
in the project that makes a network call at demo time, and even that is cached.

Run:  .venv/bin/python -m src.constraints.test_constraints
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from ..rag.retrieve import RetrievedChunk, retrieve

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_PATH = PROJECT_ROOT / "data" / "scenario.json"
MANIFEST_PATH = PROJECT_ROOT / "data" / "raw_docs" / "MANIFEST.json"
CACHE_PATH = PROJECT_ROOT / "data" / "constraints_output.json"

# DEVELOPMENT.md originally fixed gemini-2.5-flash / gemini-2.5-flash-lite. As of 2026-09-02
# BOTH return 404 on this key: "This model ... is no longer available to new users.
# Please update your code to use models/gemini-3.6-flash". Substituted with the user's
# explicit approval; see DOCUMENTATION.md Step 3. Still the free tier -- a Google AI Studio
# key with no billing attached cannot call anything outside it.
MODEL = "gemini-3.6-flash"
VALID_STATUSES = {"allowed", "excluded"}

# Retrieval queries covering the two in-scope data kinds (hazard severity, shelter
# status). Deliberately about shelter siting and relief-camp provision -- not traffic,
# sensors, or imagery, which are cut from scope entirely.
CONTEXT_QUERIES = [
    "shelter site selection flood-free elevated land",
    "relief camps basic amenities capacity for flood affected people",
    "evacuation of people from flood affected areas to safer places",
    "construction of flood shelters minimum standards",
]


class ConstraintError(RuntimeError):
    """Raised when the model cannot produce a schema-valid result even after a retry."""


# --------------------------------------------------------------------------------------
# scenario + context
# --------------------------------------------------------------------------------------


def load_scenario(path: Path = SCENARIO_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_fingerprint(scenario: dict) -> str:
    """Stable hash of the decision-relevant scenario facts, for cache invalidation."""
    relevant = {
        "scenario_id": scenario["scenario_id"],
        "source": scenario["source"],
        "shelters": scenario["shelters"],
        "cells": scenario["grid"]["cells"],
    }
    blob = json.dumps(relevant, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def known_documents() -> set[str]:
    """Filenames of the REAL documents actually in the corpus.

    Used to reject a citation naming a document we do not have, which is the most
    plausible-looking way a hallucinated source would slip through.
    """
    if not MANIFEST_PATH.exists():
        return set()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {d["filename"] for d in manifest.get("documents", [])}


def gather_context(per_query_k: int = 3) -> list[RetrievedChunk]:
    """Retrieve guideline chunks, deduplicated across queries, order preserved."""
    seen: set[tuple[str, int, str]] = set()
    chunks: list[RetrievedChunk] = []
    for query in CONTEXT_QUERIES:
        for chunk in retrieve(query, k=per_query_k):
            key = (chunk.source_document, chunk.page, chunk.text[:60])
            if key in seen:
                continue
            seen.add(key)
            chunks.append(chunk)
    return chunks


def shelter_facts(scenario: dict) -> list[dict]:
    """Flatten each shelter with its cell's hazard data and derived headroom."""
    cells = {c["cell_id"]: c for c in scenario["grid"]["cells"]}
    facts = []
    for shelter in scenario["shelters"]:
        cell = cells[shelter["cell_id"]]
        facts.append(
            {
                "shelter_id": shelter["shelter_id"],
                "cell_id": shelter["cell_id"],
                "flood_severity": cell["flood_severity"],
                "severity_band": cell["severity_band"],
                "capacity_total": shelter["capacity_total"],
                "current_occupancy": shelter["current_occupancy"],
                "capacity_headroom": shelter["capacity_total"] - shelter["current_occupancy"],
                "status": shelter["status"],
                "travel_cost_minutes": shelter["travel_cost_minutes"],
            }
        )
    return facts


# --------------------------------------------------------------------------------------
# prompt
# --------------------------------------------------------------------------------------


def build_prompt(scenario: dict, chunks: list[RetrievedChunk]) -> str:
    source = scenario["source"]
    source_cell = next(
        c for c in scenario["grid"]["cells"] if c["cell_id"] == source["cell_id"]
    )

    lines = [
        "You are supporting a flood evacuation decision. Judge each candidate shelter",
        "against the official guideline excerpts provided below.",
        "",
        "SCENARIO",
        f"  scenario_id: {scenario['scenario_id']}",
        f"  Flooded source cell {source['cell_id']} "
        f"(flood severity {source_cell['flood_severity']}, {source_cell['severity_band']})",
        f"  People needing evacuation: {source['population_to_evacuate']}",
        "",
        "  Flood severity is a 0.0-1.0 scale where 1.0 is fully inundated.",
        "  capacity_headroom = capacity_total - current_occupancy (spare places available).",
        "",
        "CANDIDATE SHELTERS",
    ]
    for fact in shelter_facts(scenario):
        lines.append(
            f"  {fact['shelter_id']}: in cell {fact['cell_id']} | "
            f"flood severity {fact['flood_severity']} ({fact['severity_band']}) | "
            f"capacity {fact['capacity_total']}, occupied {fact['current_occupancy']}, "
            f"headroom {fact['capacity_headroom']} | "
            f"status {fact['status']} | travel {fact['travel_cost_minutes']} min"
        )

    lines += [
        "",
        "OFFICIAL GUIDELINE EXCERPTS (the only sources you may cite)",
    ]
    for index, chunk in enumerate(chunks, start=1):
        lines += [
            "",
            f"  [{index}] source_document: {chunk.source_document} (page {chunk.page})",
            f"      {chunk.text}",
        ]

    lines += [
        "",
        "TASK",
        "  Return one entry for EVERY shelter listed above - no more, no fewer.",
        "  Mark each 'allowed' or 'excluded' for receiving these evacuees.",
        "",
        "RULES",
        "  1. Base each judgement on the flood severity at the shelter's cell, the",
        "     shelter's operational status, and whether its capacity headroom can take",
        f"     the {source['population_to_evacuate']} people needing evacuation.",
        "  2. 'reason' must be ONE sentence.",
        "  3. 'source_excerpt' MUST be copied VERBATIM from one of the numbered excerpts",
        "     above - copy an exact substring, character for character. Do not paraphrase,",
        "     summarise, or reword it.",
        "  4. 'source_document' MUST be EXACTLY the source_document filename shown for the",
        "     excerpt you quoted - the filename alone, with no page number appended.",
        "     Never name a document that does not appear above.",
        "  5. Pick the excerpt that MOST DIRECTLY supports your specific reason for THAT",
        "     shelter. If you exclude a shelter because its cell is badly flooded, quote a",
        "     clause about siting or elevation; if because it is full or closed, quote a",
        "     clause about shelter provision or capacity. Do NOT reuse one generic",
        "     sentence about evacuation for every shelter - a citation that does not",
        "     support the specific reason is useless.",
        "  6. Judge every shelter on its merits; do not assume a fixed number must be",
        "     excluded.",
    ]
    return "\n".join(lines)


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scenario_id": {"type": "string"},
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_id": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(VALID_STATUSES)},
                    "reason": {"type": "string"},
                    "source_document": {"type": "string"},
                    "source_excerpt": {"type": "string"},
                },
                "required": [
                    "action_id",
                    "status",
                    "reason",
                    "source_document",
                    "source_excerpt",
                ],
            },
        },
    },
    "required": ["scenario_id", "constraints"],
}


# --------------------------------------------------------------------------------------
# validation + grounding
# --------------------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Collapse whitespace and lowercase, so PDF spacing quirks don't fail a real quote."""
    return re.sub(r"\s+", " ", text).strip().lower()


def validate(payload: Any, scenario: dict) -> list[str]:
    """Return a list of schema violations. Empty list means valid."""
    errors: list[str] = []

    if not isinstance(payload, dict):
        return [f"top level must be a JSON object, got {type(payload).__name__}"]

    if payload.get("scenario_id") != scenario["scenario_id"]:
        errors.append(
            f"scenario_id must be {scenario['scenario_id']!r}, "
            f"got {payload.get('scenario_id')!r}"
        )

    constraints = payload.get("constraints")
    if not isinstance(constraints, list):
        return errors + ["'constraints' must be a list"]

    expected = {s["shelter_id"] for s in scenario["shelters"]}
    documents = known_documents()
    seen: set[str] = set()

    for index, item in enumerate(constraints):
        where = f"constraints[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue

        for field in ("action_id", "status", "reason", "source_document", "source_excerpt"):
            if field not in item:
                errors.append(f"{where} missing required field {field!r}")

        action_id = item.get("action_id")
        if action_id in seen:
            errors.append(f"{where} duplicate action_id {action_id!r}")
        seen.add(action_id)
        if action_id not in expected:
            errors.append(
                f"{where} action_id {action_id!r} is not one of the candidate shelters "
                f"{sorted(expected)}"
            )

        status = item.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{where} status must be 'allowed' or 'excluded', got {status!r}")

        if not str(item.get("reason", "")).strip():
            errors.append(f"{where} reason must be a non-empty sentence")
        if not str(item.get("source_excerpt", "")).strip():
            errors.append(f"{where} source_excerpt must be non-empty")

        # A citation naming a document we do not actually have is the most plausible-
        # looking way a fabricated source would slip past a reader.
        document = item.get("source_document")
        if documents and document not in documents:
            errors.append(
                f"{where} source_document {document!r} is not a document in the corpus "
                f"{sorted(documents)}"
            )

    for missing in sorted(expected - seen):
        errors.append(f"no constraint returned for shelter {missing!r}")

    return errors


def check_grounding(payload: dict, chunks: list[RetrievedChunk]) -> list[str]:
    """Mark each constraint's citation_verified; return the ids that failed.

    An excerpt counts as grounded only if it appears verbatim (whitespace-normalised,
    case-insensitive) inside a chunk we actually retrieved. This is what lets us say the
    system detects its own ungrounded citations instead of trusting the model.
    """
    corpus = [_normalise(c.text) for c in chunks]
    ungrounded: list[str] = []

    for item in payload.get("constraints", []):
        excerpt = _normalise(str(item.get("source_excerpt", "")))
        verified = bool(excerpt) and any(excerpt in text for text in corpus)
        item["citation_verified"] = verified
        if not verified:
            ungrounded.append(str(item.get("action_id")))

    return ungrounded


# --------------------------------------------------------------------------------------
# the single Gemini call
# --------------------------------------------------------------------------------------


def _call_gemini(prompt: str) -> str:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ConstraintError(
            "GEMINI_API_KEY is not set. Get a free key from Google AI Studio "
            "(no credit card needed) and export it before running this step."
        )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.0,
        ),
    )
    return response.text


def generate_constraints(
    scenario: dict | None = None,
    chunks: list[RetrievedChunk] | None = None,
    verbose: bool = True,
) -> dict:
    """One structured Gemini call per scenario, validated, with a single retry."""
    scenario = scenario if scenario is not None else load_scenario()
    chunks = chunks if chunks is not None else gather_context()

    prompt = build_prompt(scenario, chunks)
    attempts = 2  # the contract: one call, and exactly one retry if it doesn't hold up
    feedback = ""
    last_errors: list[str] = []

    for attempt in range(1, attempts + 1):
        if verbose:
            print(f"Calling {MODEL} (attempt {attempt} of {attempts})...")

        raw = _call_gemini(prompt + feedback)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_errors = [f"response was not valid JSON: {exc}"]
            if verbose:
                print(f"  parse failed: {exc}")
            feedback = (
                "\n\nYour previous response could not be parsed as JSON. "
                "Return ONLY a single valid JSON object matching the schema."
            )
            continue

        errors = validate(payload, scenario)
        if errors:
            last_errors = errors
            if verbose:
                print(f"  schema validation failed ({len(errors)} problem(s)):")
                for err in errors[:6]:
                    print(f"    - {err}")
            feedback = (
                "\n\nYour previous response failed validation with these problems:\n"
                + "\n".join(f"  - {e}" for e in errors)
                + "\nReturn a corrected JSON object fixing all of them."
            )
            continue

        ungrounded = check_grounding(payload, chunks)
        if ungrounded and attempt < attempts:
            if verbose:
                print(
                    f"  citations not verbatim for {ungrounded} -- retrying once "
                    f"to get exact quotes"
                )
            feedback = (
                "\n\nYour previous response was structurally valid, but the "
                f"source_excerpt for {', '.join(ungrounded)} was not an exact substring "
                "of any excerpt provided. Copy the quote character for character from "
                "the numbered excerpts."
            )
            continue

        if verbose and ungrounded:
            print(
                f"  WARNING: citations still not verbatim for {ungrounded}; "
                f"kept and flagged as UNVERIFIED"
            )
        payload["_meta"] = {
            "model": MODEL,
            "scenario_fingerprint": scenario_fingerprint(scenario),
            "retrieved_chunks": [
                {"source_document": c.source_document, "page": c.page} for c in chunks
            ],
            "attempts_used": attempt,
            "unverified_citations": ungrounded,
            "_note": (
                "Generated by a single structured Gemini call grounded in the retrieved "
                "NDMA excerpts. citation_verified=false means the excerpt was NOT found "
                "verbatim in the retrieved text and should not be trusted as a quote."
            ),
        }
        return payload

    raise ConstraintError(
        f"{MODEL} did not return a schema-valid result after {attempts} attempts. "
        f"Last problems: {last_errors}"
    )


# --------------------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------------------


def load_or_generate(refresh: bool = False, verbose: bool = True) -> dict:
    """Return cached constraints when they match the current scenario, else regenerate.

    Caching keeps the live demo working with no network and avoids burning free-tier
    quota on every rerun.
    """
    scenario = load_scenario()
    fingerprint = scenario_fingerprint(scenario)

    if not refresh and CACHE_PATH.exists():
        cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        if cached.get("_meta", {}).get("scenario_fingerprint") == fingerprint:
            if verbose:
                print(f"Using cached constraints from {CACHE_PATH.name} (no API call).")
            return cached
        if verbose:
            print("Cached constraints are stale (scenario changed); regenerating.")

    payload = generate_constraints(scenario, verbose=verbose)
    CACHE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if verbose:
        print(f"Wrote {CACHE_PATH}")
    return payload


def allowed_shelter_ids(payload: dict) -> list[str]:
    return [
        c["action_id"] for c in payload["constraints"] if c["status"] == "allowed"
    ]
