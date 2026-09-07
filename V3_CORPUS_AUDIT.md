# Sentinel-Agent V3 — Authoritative Corpus Audit

## Scope and status

`v3-authoritative-corpus-v1` is a provenance-controlled collection of three genuinely
distinct, locally cached Government of India disaster-management publications. Every
retained item is a **REAL AUTHORITATIVE DOCUMENT**. No blog, news article, commercial
page, student paper, AI summary, mirror, or unreadable scan counts toward the total.

This expansion changes the evidence base only. It does not change the frozen Phase 10
decision-policy result (`NO`), any PPO checkpoint, reward, simulator, planner, or result
artifact.

## Selection method

Candidates were screened for identifiable institutional publisher, stable title,
obtainable local PDF, topic relevance confirmed from the text, provenance URL, SHA-256,
page count, and readable extraction. At least three relevant PDF pages were manually
inspected for every retained document. Exact hashes identified mirrors; title/version and
text inspection identified reformatted or near-duplicate copies. Unusable scans were
rejected because Phase 11 has no OCR fallback.

Eight URLs were examined. Six candidate files were downloaded during Phase 11. Two URLs
were exact duplicates, one was a near-duplicate/repackaged copy, and five URL candidates
appear in the exclusion log. Three canonical documents were retained.

## Corpus identity

- Version: `v3-authoritative-corpus-v1`
- Fingerprint: `a4877d0f837a07311e47bd1c3ca35cb4c368c533012b631ed67cbc8ff3aeb753`
- Canonical documents: 3
- Publishers: 1 (National Disaster Management Authority, Government of India)
- PDF pages: 652
- Pages with extracted text: 635
- Page-scoped chunks: 1,797
- Embedding model: `all-MiniLM-L6-v2` (unchanged)
- Embedding dimension: 384
- Chroma collection: `v3_authoritative_corpus_v1`

The fingerprint is SHA-256 over concatenated UTF-8 lines sorted lexicographically by
`source_id`, each formatted exactly as:

```text
<source_id>\t<source_sha256>\n
```

It is independent of manifest document ordering. Full fields and hashes are in
[`data/raw_docs/MANIFEST.json`](data/raw_docs/MANIFEST.json).

## Documents retained

### 1. National Disaster Management Guidelines: Management of Floods

- Source ID: `ndma-flood-guidelines-2008`
- Publisher: National Disaster Management Authority (NDMA), Government of India
- Publication date: 17 January 2008
- Pages: 168; readable text pages: 162; chunks: 480
- Topics: flood management, evacuation, shelter, logistics/transport
- Canonical URL: <https://ndma.gov.in/sites/default/files/PDF/Guidelines/flood.pdf>
- Why retained: the primary India-specific national flood-management guideline, covering
  mitigation, flood shelters, evacuation, relief infrastructure, communications, and
  medical movement.

Manual spot checks:

1. PDF page 56 — preparedness measures call for flood shelters and high-ground relief
   centres with communications that remain usable during floods.
2. PDF page 63 — response arrangements assign evacuation, rescue, and relief roles.
3. PDF page 66 — the Patient Evacuation Plan covers equipment, trained staff, triage, and
   vital monitoring.

### 2. National Disaster Management Plan 2019

- Source ID: `ndma-national-disaster-management-plan-2019`
- Publisher: National Disaster Management Authority (NDMA), Government of India
- Publication date: November 2019
- Pages: 384; readable text pages: 379; chunks: 1,099
- Topics: all five corpus topics
- Canonical URL: <https://ndma.gov.in/sites/default/files/PDF/ndmp-2019.pdf>
- Why retained: the national cross-hazard responsibility framework connects evacuation,
  relief camps, temporary shelter, inclusion, transport access, and logistics.

Manual spot checks:

1. PDF page 111 — requires social inclusion in early warning, evacuation, relief, and
   rehabilitation.
2. PDF page 115 — discusses evacuation difficulties for persons with disabilities,
   support networks, and local assistance lists.
3. PDF page 256 — specifies shelters, support facilities, and multiple reliable access
   and escape routes.
4. PDF page 306 — requires identification and display of evacuation routes and temporary
   refuge areas.
5. PDF page 313 — covers relief camps, supplier arrangements, and regional shelter
   logistics.

The source has a generally strong text layer. A Corel PDF encoding maps a common `ti`
ligature to NUL; ingestion repairs that extraction artifact before chunking so terms such
as “evacuation” remain searchable. Page boundaries and source text provenance remain
unchanged.

### 3. National Guidelines for Temporary Shelters

- Source ID: `ndma-temporary-shelters-2019`
- Publisher: National Disaster Management Authority (NDMA), Government of India
- Publication date: September 2019
- Pages: 100; readable text pages: 94; chunks: 218
- Topics: evacuation, shelter, vulnerability/accessibility, logistics/transport
- Canonical URL: <https://nidm.gov.in/PDF/pubs/NDMA/24.pdf>
- Why retained: adds operational detail on site selection, settlement planning, shelter
  services, inclusive provision, materials, and supply logistics.

Manual spot checks:

1. PDF page 37 — covers site selection, planning, design, gender, vulnerability, and
   disability considerations.
2. PDF page 40 — provides water and sanitation guidance for temporary shelter sites.
3. PDF page 49 — requires provisions and facilities for persons with disabilities.
4. PDF page 54 — calls for regional logistics facilities and coordinated shelter stocks.

## Topic coverage

| Topic | Supporting canonical sources | Coverage assessment |
| --- | --- | --- |
| Flood management | Flood Guidelines; NDMP 2019 | Strong national coverage |
| Evacuation | All three | Strong, across flood, national planning, and shelter operations |
| Shelter | All three | Strong, with a dedicated temporary-shelter guideline |
| Vulnerability/accessibility | NDMP 2019; Temporary Shelters | Moderate; dedicated DiDRR scan was not indexable |
| Logistics/transport | All three | Moderate-to-strong policy coverage; not a route-operations manual |

The most important gap is dedicated accessibility depth. It is not filled with a weaker
source merely to increase document count.

## Duplicate and exclusion handling

The NIDM flood-guideline URL remains recorded as a byte-identical mirror of the canonical
NDMA source. It counts as one URL duplicate and zero additional documents.

The official NDMA and NIDM copies of the 2019 Disability-Inclusive DRR guideline are
byte-identical 106-page scans. Only 8 pages/6,780 characters extract. A Gujarat government
copy is a reformatted near-duplicate with a malformed page tree. NDMA’s otherwise relevant
Guidelines on Minimum Standards of Relief is a six-page scan with no extractable text.
None was indexed. Exact URLs, relationships, and rejection reasons are preserved in
[`data/raw_docs/excluded_sources.json`](data/raw_docs/excluded_sources.json).

## Ingestion and offline capability

The existing page-scoped 1,000-character chunks with 150-character overlap are unchanged.
Only multi-document provenance fields were added: every chunk now carries `source_id`,
`source_document`, `source_sha256`, `corpus_version`, `page`, and `chunk_index`.

The index was rebuilt from committed PDFs using the already-cached MiniLM model with
network-disabled model loading. The 1,797 × 384 embeddings were written to local Chroma.
Normal ingestion, retrieval, citation checking, and dashboard use do not download PDFs or
models. The production constraint cache was not regenerated.

## Dense-retrieval smoke test

The unchanged dense retriever executed five non-benchmark queries: `evacuation`, `relief
shelter`, `flood-safe location`, `vulnerable groups`, and `transport access`. Across their
top-five results, all three canonical source IDs appeared. Every result retained source
ID, filename, PDF page, text, and cosine distance. This proves multi-source execution and
metadata compatibility only; it is not a retrieval-quality claim.

Existing citation verification remains compatible because `source_document`, `page`, and
verbatim chunk text are preserved. `source_id` is additive.

## Known limitations

- Three documents are a deliberately small corpus and all share one publisher.
- Dedicated disability guidance could not be retained without OCR.
- The flood guideline is from 2008; authority does not imply recency.
- PDF extraction quality varies, and six cover/furniture pages in two sources are blank.
- Source presence does not prove a retrieved result is relevant.
- Document authority does not prove a model-generated statement is entailed.
- Retrieval quality, hybrid retrieval, reranking, and claim entailment remain deferred to
  later phases.
