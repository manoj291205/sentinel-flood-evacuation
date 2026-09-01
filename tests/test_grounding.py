"""The grounding check — the defence that catches a citation the model invented."""

from __future__ import annotations

from src.constraints.generate import check_grounding
from src.rag.retrieve import RetrievedChunk

CHUNK = RetrievedChunk(
    text=(
        "An important component of preparedness for floods is the construction of "
        "suitable shelters for the flood-affected people during the relief period."
    ),
    source_document="ndma_flood_guidelines.pdf",
    page=86,
    score=0.1,
)


def payload(excerpt: str) -> dict:
    return {"constraints": [{"action_id": "S1", "source_excerpt": excerpt}]}


def test_exact_quote_is_verified():
    p = payload("the construction of suitable shelters for the flood-affected people")
    assert check_grounding(p, [CHUNK]) == []
    assert p["constraints"][0]["citation_verified"] is True


def test_whitespace_and_case_differences_still_verify():
    """PDF extraction is noisy; a real quote must not fail on spacing alone."""
    p = payload("The  Construction   of\nsuitable SHELTERS for the flood-affected people")
    assert check_grounding(p, [CHUNK]) == []
    assert p["constraints"][0]["citation_verified"] is True


def test_a_paraphrase_is_caught():
    """Plausible, on-topic, and not in the source — the case that matters."""
    p = payload("Shelters must be built for people affected by flooding during relief.")
    assert check_grounding(p, [CHUNK]) == ["S1"]
    assert p["constraints"][0]["citation_verified"] is False


def test_an_empty_excerpt_is_not_verified():
    p = payload("")
    assert check_grounding(p, [CHUNK]) == ["S1"]


def test_with_no_retrieved_chunks_nothing_can_verify():
    """The RAG ablation: without retrieval a citation is unverifiable by construction."""
    p = payload("the construction of suitable shelters")
    assert check_grounding(p, []) == ["S1"]
    assert p["constraints"][0]["citation_verified"] is False


def test_every_constraint_gets_the_flag_set():
    p = {"constraints": [
        {"action_id": "S1", "source_excerpt": "suitable shelters"},
        {"action_id": "S2", "source_excerpt": "invented text not in the source"},
    ]}
    ungrounded = check_grounding(p, [CHUNK])
    assert ungrounded == ["S2"]
    assert all("citation_verified" in c for c in p["constraints"])
