"""Confirm the RAG index returns real guideline text before Step 3 depends on it.

The point of this script is to be read by a human: it prints the retrieved passages in
full, with their document and page, so you can see the text came out of a real NDMA/NIDM
PDF and is not noise or invention.

Run:  .venv/bin/python -m src.rag.test_retrieval
"""

from __future__ import annotations

import sys

from .retrieve import retrieve

# The query the kickoff prompt asks for, plus two probes shaped like the questions the
# Step 3 constraint step will actually need to answer about each candidate shelter.
QUERIES = [
    "evacuation",
    "relief shelter",
    "flood-safe location",
    "vulnerable groups",
    "transport access",
]

TOP_K = 5


def main() -> int:
    for query in QUERIES:
        print("=" * 78)
        print(f"QUERY: {query!r}   (top {TOP_K})")
        print("=" * 78)

        try:
            chunks = retrieve(query, k=TOP_K)
        except FileNotFoundError as exc:
            print(exc)
            return 1

        if not chunks:
            print("No results returned -- the collection may be empty.")
            return 1

        for rank, chunk in enumerate(chunks, start=1):
            print(
                f"\n--- #{rank}  [{chunk.source_id}; {chunk.citation()}]  "
                f"cosine distance {chunk.score:.4f}"
            )
            print(chunk.text)
        print()

    print("=" * 78)
    print("If the passages above read as real flood-guideline prose with plausible page")
    print("numbers, retrieval is grounded in the actual documents and Step 3 can proceed.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
