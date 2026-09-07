# Raw authoritative source documents

This directory contains only real, locally cached public guidance from authoritative
institutions. The three canonical PDFs form `v3-authoritative-corpus-v1`; they are not
generated, summarized substitutes, or simulated evidence.

`MANIFEST.json` is the canonical machine-readable registry. It records publisher,
provenance URL, expected SHA-256, byte/page counts, topics, authority class, and manual
page spot checks. Its fingerprint is SHA-256 over UTF-8 lines sorted by source ID:

```text
<source_id>\t<source_sha256>\n
```

`excluded_sources.json` records duplicate mirrors, near-duplicate copies, unusable scans,
and other rejected candidates. A mirror never counts as an independent source.

## Canonical documents

- `ndma_flood_guidelines.pdf` — NDMA Management of Floods guidelines (2008)
- `ndma_national_disaster_management_plan_2019.pdf` — revised NDMP 2019
- `ndma_temporary_shelters_2019.pdf` — NDMA Temporary Shelters guidelines (2019)

The PDFs are committed so ingestion, retrieval, citation checks, and the demonstration
can run without web access. `python -m src.rag.fetch_docs` is only the intentional online
re-fetch path. It verifies every response as a PDF and refuses any unexpected hash.

To adopt a revised upstream document deliberately, inspect it as a new candidate, update
the expected hash and version/provenance record, rerun the spot checks, recompute the
corpus fingerprint, rebuild the index, and commit all resulting audit changes together.

Document authority does not prove that a retrieved passage is relevant or that a
model-generated claim is entailed. Those are separate later evaluation phases. Scenario
and shelter data elsewhere in this repository remain simulated.
