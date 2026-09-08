# Sentinel-Agent V3 — Phase 13B Retrieval Evaluation

## 1. Executive result

Formal verdict: `HYBRID_SUPPORTED`. Hybrid retrieval was supported over the frozen Dense baseline under the pre-registered Phase 13 criteria on this AI-assisted benchmark.

## 2. Research question

Does frozen Hybrid RRF improve DirectHit@5 over the frozen Dense MiniLM baseline under the pre-registered rule? BM25 comparisons are secondary and descriptive.

## 3. Benchmark provenance

Question selection was project-owner adopted with disclosed AI assistance. Passage relevance judgments were generated using a blind AI-assisted labeling protocol. Nineteen additional question/chunk pairs were blindly labeled before retrieval metrics were calculated after the pre-registered label-coverage gate identified missing annotations caused by edited final queries. The benchmark must not be represented as independently human-annotated gold data.

## 4. Why coverage extension was required

Final edits to Q003, Q008, Q016, and Q034 changed top-five membership. The pre-metric gate froze all 19 missing pairs before any quality metric; every pair was then blindly labeled without retriever identity or rank.

## 5. Frozen 504-label benchmark

The authoritative benchmark is `v3-retrieval-benchmark-ai-assisted-v2`: 504 unique labels for 45 questions, fingerprint `393512866c33a32d9aa2944289791eb74554eeb585e21cc82956be203c28b1b7`, with unchanged 485-label parent `bf46ffb139cbd314e1707409635b76346faea81739e5a95710317be07dd73b92`.

## 6. Retrieval systems

Dense `dense-minilm-v1`, BM25 `bm25-okapi-v1` (`k1=1.5`, `b=0.75`, `epsilon=0.25`), and Hybrid `hybrid-rrf-v1` (`RRF_K=60`, candidate depth `max(20,k)`) were rerun unchanged at k=5. No reranker was added.

## 7. Coverage gate

Fresh coverage was 434/434; unlabeled pairs: 0; status: `PASS`.

## 8. Metrics

DirectHit and MRR count only grade 2. nDCG uses gains `2^rel-1` and an ideal ranking from all 504 pooled labels for each question. PooledRecall@5 divides distinct retrieved grade-2 chunks by all grade-2 chunks in that question's annotated pool; it is not exhaustive corpus recall.

## 9. Overall results

| Retriever | DirectHit@1 | DirectHit@3 | DirectHit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.5111 | 0.5778 | 0.6222 | 0.5519 | 0.5208 | 0.4129 |
| BM25 | 0.5333 | 0.7778 | 0.8667 | 0.6619 | 0.5906 | 0.5901 |
| Hybrid | 0.5111 | 0.7556 | 0.8222 | 0.6256 | 0.5950 | 0.5892 |

Raw DirectHit@5 counts: Dense 28/45, BM25 39/45, Hybrid 37/45.

## 10. Hybrid-vs-Dense paired bootstrap

Observed DirectHit@5 difference: 0.2000 (+9 net questions). The 10,000-resample, seed-131313 paired question-level percentile bootstrap 95% CI is [0.0889, 0.3111].

## 11. Frozen decision rule

All three conditions are required: difference >=0.05 (True), CI lower bound >0 (True), and Hybrid nDCG@5 >= Dense nDCG@5 - 0.02 (True). With n=45, one question is 0.02222, two are 0.04444, and three are 0.06667, so the effect condition requires at least a three-question net advantage.

## 12. Formal verdict

`HYBRID_SUPPORTED` — Hybrid retrieval was supported over the frozen Dense baseline under the pre-registered Phase 13 criteria on this AI-assisted benchmark.

The secondary comparisons below are descriptive deltas; positive values favor the first-named system.

| Comparison | DirectHit@1 | DirectHit@3 | DirectHit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 - Dense | 0.0222 | 0.2000 | 0.2444 | 0.1100 | 0.0698 | 0.1772 |
| Hybrid - BM25 | -0.0222 | -0.0222 | -0.0444 | -0.0363 | 0.0044 | -0.0009 |

## 13. Topic analysis

Each topic has n=9. All results are descriptive; no subgroup significance is claimed.

| Topic | Retriever | Hit@1 | Hit@3 | Hit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| evacuation | Dense | 0.4444 | 0.4444 | 0.5556 | 0.4722 | 0.4559 | 0.3180 |
| evacuation | BM25 | 0.5556 | 0.7778 | 0.8889 | 0.6704 | 0.5615 | 0.6132 |
| evacuation | Hybrid | 0.3333 | 0.7778 | 0.8889 | 0.5463 | 0.5626 | 0.7032 |
| flood | Dense | 0.3333 | 0.4444 | 0.4444 | 0.3889 | 0.4753 | 0.3611 |
| flood | BM25 | 0.3333 | 0.6667 | 0.7778 | 0.5278 | 0.4951 | 0.5278 |
| flood | Hybrid | 0.4444 | 0.7778 | 0.7778 | 0.5741 | 0.6123 | 0.6389 |
| logistics_transport | Dense | 0.4444 | 0.4444 | 0.5556 | 0.4722 | 0.4664 | 0.3981 |
| logistics_transport | BM25 | 0.5556 | 0.6667 | 0.7778 | 0.6204 | 0.6165 | 0.6389 |
| logistics_transport | Hybrid | 0.5556 | 0.6667 | 0.7778 | 0.6333 | 0.6117 | 0.5556 |
| temporary_shelters | Dense | 0.7778 | 1.0000 | 1.0000 | 0.8704 | 0.7629 | 0.6630 |
| temporary_shelters | BM25 | 0.5556 | 1.0000 | 1.0000 | 0.7593 | 0.5906 | 0.4944 |
| temporary_shelters | Hybrid | 0.6667 | 1.0000 | 1.0000 | 0.7963 | 0.6711 | 0.6037 |
| vulnerable_accessibility | Dense | 0.5556 | 0.5556 | 0.5556 | 0.5556 | 0.4437 | 0.3241 |
| vulnerable_accessibility | BM25 | 0.6667 | 0.7778 | 0.8889 | 0.7315 | 0.6894 | 0.6759 |
| vulnerable_accessibility | Hybrid | 0.5556 | 0.5556 | 0.6667 | 0.5778 | 0.5174 | 0.4444 |

## 14. Query-style analysis

Each style has n=15. All six metrics are descriptive.

| Query style | Retriever | Hit@1 | Hit@3 | Hit@5 | MRR@5 | nDCG@5 | PooledRecall@5 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| LEXICAL | Dense | 0.5333 | 0.6000 | 0.6000 | 0.5667 | 0.5486 | 0.3852 |
| LEXICAL | BM25 | 0.4667 | 0.8000 | 0.8667 | 0.6389 | 0.6496 | 0.6402 |
| LEXICAL | Hybrid | 0.4667 | 0.7333 | 0.8667 | 0.5933 | 0.6228 | 0.5830 |
| OPERATIONAL_TASK | Dense | 0.5333 | 0.6000 | 0.6667 | 0.5722 | 0.5374 | 0.4333 |
| OPERATIONAL_TASK | BM25 | 0.7333 | 0.8667 | 1.0000 | 0.8300 | 0.7023 | 0.6833 |
| OPERATIONAL_TASK | Hybrid | 0.5333 | 0.7333 | 0.8000 | 0.6167 | 0.5858 | 0.5611 |
| SEMANTIC_PARAPHRASE | Dense | 0.4667 | 0.5333 | 0.6000 | 0.5167 | 0.4765 | 0.4200 |
| SEMANTIC_PARAPHRASE | BM25 | 0.4000 | 0.6667 | 0.7333 | 0.5167 | 0.4199 | 0.4467 |
| SEMANTIC_PARAPHRASE | Hybrid | 0.5333 | 0.8000 | 0.8000 | 0.6667 | 0.5765 | 0.6233 |

## 15. Head-to-head analysis

DirectHit@5: both hit 28, Hybrid only 9, Dense only 0, neither 8 (sum 45).

## 16. Rank analysis

Among questions where both hit, Hybrid's first direct-evidence rank was better on 2, the same on 24, and worse on 2.

## 17. Failure analysis

Hybrid-only successes: Q003, Q006, Q012, Q015, Q018, Q023, Q037, Q049, Q054. Dense-only successes: none. BM25-only successes: Q008, Q046, Q048, Q057. All-system failures: Q002, Q020, Q039, Q056.

For each case below, the evidence field is a deterministic representative from the available grade-2 label pool. Ranked IDs are shown in order.

| Case | Question | Topic/style | Grade-2 evidence | Dense top 5 | BM25 top 5 | Hybrid top 5 |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid only successes | Q003: Where should flood shelters and disaster relief centres be located so that they remain functional during floods? | flood_management / LEXICAL | `ndma-flood-guidelines-2008-p56-c0` | `ndma-flood-guidelines-2008-p86-c3`<br>`ndma-flood-guidelines-2008-p86-c4`<br>`ndma-national-disaster-management-plan-2019-p152-c2`<br>`ndma-flood-guidelines-2008-p79-c1`<br>`ndma-national-disaster-management-plan-2019-p149-c0` | `ndma-flood-guidelines-2008-p56-c0`<br>`ndma-flood-guidelines-2008-p79-c1`<br>`ndma-flood-guidelines-2008-p86-c3`<br>`ndma-flood-guidelines-2008-p62-c1`<br>`ndma-national-disaster-management-plan-2019-p115-c2` | `ndma-flood-guidelines-2008-p86-c3`<br>`ndma-flood-guidelines-2008-p79-c1`<br>`ndma-flood-guidelines-2008-p56-c0`<br>`ndma-temporary-shelters-2019-p48-c2`<br>`ndma-flood-guidelines-2008-p86-c4` |
| hybrid only successes | Q006: How can modelling future situations help authorities prepare for flooding? | flood_management / SEMANTIC_PARAPHRASE | `ndma-flood-guidelines-2008-p86-c0` | `ndma-flood-guidelines-2008-p97-c1`<br>`ndma-flood-guidelines-2008-p113-c2`<br>`ndma-flood-guidelines-2008-p22-c3`<br>`ndma-flood-guidelines-2008-p43-c2`<br>`ndma-flood-guidelines-2008-p108-c2` | `ndma-temporary-shelters-2019-p37-c1`<br>`ndma-national-disaster-management-plan-2019-p114-c1`<br>`ndma-national-disaster-management-plan-2019-p88-c1`<br>`ndma-national-disaster-management-plan-2019-p108-c3`<br>`ndma-temporary-shelters-2019-p40-c2` | `ndma-flood-guidelines-2008-p86-c0`<br>`ndma-flood-guidelines-2008-p97-c1`<br>`ndma-temporary-shelters-2019-p37-c1`<br>`ndma-flood-guidelines-2008-p113-c2`<br>`ndma-national-disaster-management-plan-2019-p114-c1` |
| hybrid only successes | Q012: What resources should authorities arrange to sustain flood rescue and relief operations? | flood_management / OPERATIONAL_TASK | `ndma-flood-guidelines-2008-p92-c0` | `ndma-flood-guidelines-2008-p30-c0`<br>`ndma-flood-guidelines-2008-p22-c3`<br>`ndma-flood-guidelines-2008-p11-c0`<br>`ndma-flood-guidelines-2008-p31-c3`<br>`ndma-flood-guidelines-2008-p55-c2` | `ndma-national-disaster-management-plan-2019-p320-c1`<br>`ndma-national-disaster-management-plan-2019-p322-c1`<br>`ndma-national-disaster-management-plan-2019-p303-c0`<br>`ndma-flood-guidelines-2008-p31-c3`<br>`ndma-national-disaster-management-plan-2019-p341-c0` | `ndma-flood-guidelines-2008-p31-c3`<br>`ndma-flood-guidelines-2008-p30-c0`<br>`ndma-national-disaster-management-plan-2019-p320-c1`<br>`ndma-flood-guidelines-2008-p22-c3`<br>`ndma-national-disaster-management-plan-2019-p322-c1` |
| hybrid only successes | Q015: What should authorities identify and display when planning evacuation routes? | evacuation_movement / LEXICAL | `ndma-national-disaster-management-plan-2019-p256-c2` | `ndma-flood-guidelines-2008-p89-c2`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p303-c3`<br>`ndma-flood-guidelines-2008-p89-c3`<br>`ndma-national-disaster-management-plan-2019-p74-c1` | `ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p306-c1`<br>`ndma-national-disaster-management-plan-2019-p256-c2`<br>`ndma-national-disaster-management-plan-2019-p310-c1`<br>`ndma-temporary-shelters-2019-p40-c1` | `ndma-flood-guidelines-2008-p89-c1`<br>`ndma-flood-guidelines-2008-p89-c2`<br>`ndma-national-disaster-management-plan-2019-p306-c1`<br>`ndma-national-disaster-management-plan-2019-p310-c1`<br>`ndma-national-disaster-management-plan-2019-p303-c3` |
| hybrid only successes | Q018: When might residents need to move after water has already entered their community? | evacuation_movement / SEMANTIC_PARAPHRASE | `ndma-flood-guidelines-2008-p89-c1` | `ndma-temporary-shelters-2019-p39-c1`<br>`ndma-temporary-shelters-2019-p41-c2`<br>`ndma-national-disaster-management-plan-2019-p210-c0`<br>`ndma-temporary-shelters-2019-p38-c2`<br>`ndma-flood-guidelines-2008-p110-c2` | `ndma-temporary-shelters-2019-p60-c0`<br>`ndma-temporary-shelters-2019-p28-c0`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-temporary-shelters-2019-p25-c1`<br>`ndma-temporary-shelters-2019-p22-c2` | `ndma-temporary-shelters-2019-p39-c1`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-temporary-shelters-2019-p41-c2`<br>`ndma-temporary-shelters-2019-p39-c3`<br>`ndma-temporary-shelters-2019-p60-c0` |
| hybrid only successes | Q023: How should an evacuation route within a shelter site accommodate people with disabilities? | evacuation_movement / OPERATIONAL_TASK | `ndma-temporary-shelters-2019-p40-c0` | `ndma-temporary-shelters-2019-p39-c0`<br>`ndma-temporary-shelters-2019-p23-c2`<br>`ndma-temporary-shelters-2019-p38-c0`<br>`ndma-temporary-shelters-2019-p22-c1`<br>`ndma-temporary-shelters-2019-p37-c1` | `ndma-temporary-shelters-2019-p40-c0`<br>`ndma-temporary-shelters-2019-p39-c0`<br>`ndma-temporary-shelters-2019-p44-c2`<br>`ndma-temporary-shelters-2019-p45-c1`<br>`ndma-temporary-shelters-2019-p38-c0` | `ndma-temporary-shelters-2019-p39-c0`<br>`ndma-temporary-shelters-2019-p38-c0`<br>`ndma-temporary-shelters-2019-p28-c0`<br>`ndma-temporary-shelters-2019-p40-c0`<br>`ndma-temporary-shelters-2019-p23-c2` |
| hybrid only successes | Q037: Which groups receive explicit attention in inclusive disaster risk management? | vulnerable_groups_accessibility / LEXICAL | `ndma-national-disaster-management-plan-2019-p108-c0` | `ndma-national-disaster-management-plan-2019-p107-c0`<br>`ndma-national-disaster-management-plan-2019-p12-c2`<br>`ndma-national-disaster-management-plan-2019-p16-c0`<br>`ndma-national-disaster-management-plan-2019-p125-c0`<br>`ndma-national-disaster-management-plan-2019-p126-c1` | `ndma-national-disaster-management-plan-2019-p107-c0`<br>`ndma-flood-guidelines-2008-p84-c2`<br>`ndma-national-disaster-management-plan-2019-p108-c0`<br>`ndma-national-disaster-management-plan-2019-p204-c0`<br>`ndma-national-disaster-management-plan-2019-p252-c0` | `ndma-national-disaster-management-plan-2019-p107-c0`<br>`ndma-national-disaster-management-plan-2019-p44-c1`<br>`ndma-flood-guidelines-2008-p84-c2`<br>`ndma-national-disaster-management-plan-2019-p12-c2`<br>`ndma-national-disaster-management-plan-2019-p108-c0` |
| hybrid only successes | Q049: What temporary shelter materials should be stockpiled in regional stores? | logistics_transport_coordination / LEXICAL | `ndma-national-disaster-management-plan-2019-p313-c2` | `ndma-temporary-shelters-2019-p35-c1`<br>`ndma-temporary-shelters-2019-p77-c0`<br>`ndma-temporary-shelters-2019-p70-c0`<br>`ndma-temporary-shelters-2019-p30-c2`<br>`ndma-temporary-shelters-2019-p87-c0` | `ndma-temporary-shelters-2019-p53-c0`<br>`ndma-temporary-shelters-2019-p44-c1`<br>`ndma-national-disaster-management-plan-2019-p313-c2`<br>`ndma-temporary-shelters-2019-p54-c0`<br>`ndma-temporary-shelters-2019-p47-c1` | `ndma-temporary-shelters-2019-p47-c1`<br>`ndma-temporary-shelters-2019-p82-c0`<br>`ndma-temporary-shelters-2019-p46-c1`<br>`ndma-temporary-shelters-2019-p35-c1`<br>`ndma-temporary-shelters-2019-p53-c0` |
| hybrid only successes | Q054: How should essential site services continue while damaged infrastructure is being fixed? | logistics_transport_coordination / SEMANTIC_PARAPHRASE | `ndma-temporary-shelters-2019-p40-c0` | `ndma-national-disaster-management-plan-2019-p330-c2`<br>`ndma-national-disaster-management-plan-2019-p302-c0`<br>`ndma-temporary-shelters-2019-p39-c1`<br>`ndma-national-disaster-management-plan-2019-p33-c1`<br>`ndma-national-disaster-management-plan-2019-p135-c1` | `ndma-temporary-shelters-2019-p39-c1`<br>`ndma-temporary-shelters-2019-p39-c0`<br>`ndma-temporary-shelters-2019-p40-c0`<br>`ndma-temporary-shelters-2019-p45-c1`<br>`ndma-national-disaster-management-plan-2019-p380-c1` | `ndma-temporary-shelters-2019-p39-c1`<br>`ndma-temporary-shelters-2019-p40-c0`<br>`ndma-national-disaster-management-plan-2019-p380-c1`<br>`ndma-national-disaster-management-plan-2019-p330-c2`<br>`ndma-national-disaster-management-plan-2019-p302-c0` |
| bm25 only successes | Q008: How should flood warning information be presented to affected communities? | flood_management / SEMANTIC_PARAPHRASE | `ndma-flood-guidelines-2008-p96-c1` | `ndma-flood-guidelines-2008-p101-c0`<br>`ndma-flood-guidelines-2008-p151-c0`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-flood-guidelines-2008-p64-c3`<br>`ndma-flood-guidelines-2008-p22-c3` | `ndma-national-disaster-management-plan-2019-p85-c1`<br>`ndma-national-disaster-management-plan-2019-p237-c1`<br>`ndma-temporary-shelters-2019-p45-c1`<br>`ndma-temporary-shelters-2019-p44-c2`<br>`ndma-flood-guidelines-2008-p89-c1` | `ndma-flood-guidelines-2008-p89-c1`<br>`ndma-flood-guidelines-2008-p64-c3`<br>`ndma-flood-guidelines-2008-p101-c0`<br>`ndma-national-disaster-management-plan-2019-p85-c1`<br>`ndma-flood-guidelines-2008-p151-c0` |
| bm25 only successes | Q046: What should connect a disability-friendly route through a temporary shelter site? | vulnerable_groups_accessibility / OPERATIONAL_TASK | `ndma-temporary-shelters-2019-p40-c0` | `ndma-temporary-shelters-2019-p39-c0`<br>`ndma-temporary-shelters-2019-p38-c0`<br>`ndma-temporary-shelters-2019-p29-c2`<br>`ndma-temporary-shelters-2019-p20-c0`<br>`ndma-temporary-shelters-2019-p29-c4` | `ndma-temporary-shelters-2019-p40-c0`<br>`ndma-temporary-shelters-2019-p82-c0`<br>`ndma-temporary-shelters-2019-p37-c3`<br>`ndma-temporary-shelters-2019-p37-c2`<br>`ndma-temporary-shelters-2019-p87-c1` | `ndma-temporary-shelters-2019-p39-c0`<br>`ndma-temporary-shelters-2019-p29-c2`<br>`ndma-temporary-shelters-2019-p38-c0`<br>`ndma-temporary-shelters-2019-p37-c3`<br>`ndma-temporary-shelters-2019-p37-c2` |
| bm25 only successes | Q048: How can local authorities identify residents who will need additional evacuation assistance? | vulnerable_groups_accessibility / OPERATIONAL_TASK | `ndma-flood-guidelines-2008-p91-c0` | `ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p381-c3`<br>`ndma-temporary-shelters-2019-p49-c0`<br>`ndma-temporary-shelters-2019-p58-c1`<br>`ndma-temporary-shelters-2019-p50-c1` | `ndma-national-disaster-management-plan-2019-p115-c1`<br>`ndma-temporary-shelters-2019-p44-c2`<br>`ndma-flood-guidelines-2008-p89-c2`<br>`ndma-flood-guidelines-2008-p91-c0`<br>`ndma-flood-guidelines-2008-p66-c3` | `ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p298-c1`<br>`ndma-temporary-shelters-2019-p50-c0`<br>`ndma-flood-guidelines-2008-p89-c2`<br>`ndma-flood-guidelines-2008-p66-c2` |
| bm25 only successes | Q057: Which transport and communication links should a district verify before relief supplies are needed? | logistics_transport_coordination / OPERATIONAL_TASK | `ndma-flood-guidelines-2008-p56-c0` | `ndma-national-disaster-management-plan-2019-p320-c0`<br>`ndma-national-disaster-management-plan-2019-p321-c1`<br>`ndma-national-disaster-management-plan-2019-p320-c1`<br>`ndma-national-disaster-management-plan-2019-p319-c2`<br>`ndma-national-disaster-management-plan-2019-p313-c0` | `ndma-flood-guidelines-2008-p93-c3`<br>`ndma-flood-guidelines-2008-p92-c0`<br>`ndma-national-disaster-management-plan-2019-p320-c1`<br>`ndma-national-disaster-management-plan-2019-p321-c1`<br>`ndma-temporary-shelters-2019-p63-c0` | `ndma-national-disaster-management-plan-2019-p321-c1`<br>`ndma-national-disaster-management-plan-2019-p320-c1`<br>`ndma-national-disaster-management-plan-2019-p320-c0`<br>`ndma-national-disaster-management-plan-2019-p319-c2`<br>`ndma-national-disaster-management-plan-2019-p305-c2` |
| all system failures | Q002: What information should flood forecasting and warning systems provide to exposed areas? | flood_management / LEXICAL | `ndma-flood-guidelines-2008-p96-c1` | `ndma-flood-guidelines-2008-p64-c3`<br>`ndma-flood-guidelines-2008-p101-c0`<br>`ndma-flood-guidelines-2008-p68-c0`<br>`ndma-national-disaster-management-plan-2019-p163-c0`<br>`ndma-flood-guidelines-2008-p69-c3` | `ndma-national-disaster-management-plan-2019-p381-c2`<br>`ndma-national-disaster-management-plan-2019-p132-c3`<br>`ndma-flood-guidelines-2008-p64-c3`<br>`ndma-national-disaster-management-plan-2019-p164-c0`<br>`ndma-flood-guidelines-2008-p68-c0` | `ndma-flood-guidelines-2008-p64-c3`<br>`ndma-flood-guidelines-2008-p68-c0`<br>`ndma-national-disaster-management-plan-2019-p148-c0`<br>`ndma-flood-guidelines-2008-p102-c1`<br>`ndma-national-disaster-management-plan-2019-p164-c0` |
| all system failures | Q020: Why are several reliable ways into and out of a shelter area important? | evacuation_movement / SEMANTIC_PARAPHRASE | `ndma-national-disaster-management-plan-2019-p256-c2` | `ndma-temporary-shelters-2019-p23-c4`<br>`ndma-temporary-shelters-2019-p22-c1`<br>`ndma-temporary-shelters-2019-p23-c3`<br>`ndma-temporary-shelters-2019-p71-c1`<br>`ndma-temporary-shelters-2019-p35-c1` | `ndma-temporary-shelters-2019-p20-c0`<br>`ndma-temporary-shelters-2019-p35-c1`<br>`ndma-flood-guidelines-2008-p22-c3`<br>`ndma-flood-guidelines-2008-p71-c1`<br>`ndma-flood-guidelines-2008-p41-c2` | `ndma-temporary-shelters-2019-p35-c1`<br>`ndma-temporary-shelters-2019-p25-c0`<br>`ndma-temporary-shelters-2019-p20-c0`<br>`ndma-temporary-shelters-2019-p23-c4`<br>`ndma-temporary-shelters-2019-p22-c1` |
| all system failures | Q039: What local support measures can improve evacuation for persons with disabilities? | vulnerable_groups_accessibility / LEXICAL | `ndma-national-disaster-management-plan-2019-p115-c1` | `ndma-national-disaster-management-plan-2019-p115-c0`<br>`ndma-national-disaster-management-plan-2019-p114-c1`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p322-c0`<br>`ndma-temporary-shelters-2019-p49-c0` | `ndma-national-disaster-management-plan-2019-p121-c1`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p115-c0`<br>`ndma-national-disaster-management-plan-2019-p114-c2`<br>`ndma-national-disaster-management-plan-2019-p114-c1` | `ndma-national-disaster-management-plan-2019-p115-c0`<br>`ndma-flood-guidelines-2008-p89-c1`<br>`ndma-national-disaster-management-plan-2019-p114-c1`<br>`ndma-national-disaster-management-plan-2019-p121-c1`<br>`ndma-temporary-shelters-2019-p49-c0` |
| all system failures | Q056: How should authorities use assistance offered by outside organizations during flood response? | logistics_transport_coordination / SEMANTIC_PARAPHRASE | `ndma-flood-guidelines-2008-p92-c0` | `ndma-flood-guidelines-2008-p91-c3`<br>`ndma-flood-guidelines-2008-p90-c0`<br>`ndma-flood-guidelines-2008-p90-c3`<br>`ndma-flood-guidelines-2008-p89-c0`<br>`ndma-flood-guidelines-2008-p43-c2` | `ndma-national-disaster-management-plan-2019-p238-c0`<br>`ndma-national-disaster-management-plan-2019-p341-c2`<br>`ndma-national-disaster-management-plan-2019-p297-c1`<br>`ndma-temporary-shelters-2019-p48-c2`<br>`ndma-flood-guidelines-2008-p140-c1` | `ndma-flood-guidelines-2008-p91-c3`<br>`ndma-national-disaster-management-plan-2019-p238-c0`<br>`ndma-flood-guidelines-2008-p90-c0`<br>`ndma-national-disaster-management-plan-2019-p341-c2`<br>`ndma-flood-guidelines-2008-p90-c3` |

The main observed failure pattern was broad same-topic material displacing the directly answering chunk below rank five. Semantic paraphrases were especially visible in Q020 and Q056, while Q039 exposed a chunk-boundary/adjacency problem: systems retrieved the contextual `p115-c0` chunk but missed the directly useful neighboring `p115-c1`. Q002 likewise retrieved forecasting context without the more specific requested information. Hybrid-only successes generally arose when lexical evidence promoted an otherwise missed direct chunk into the fused top five. These are post-metric diagnostics; retrieval was not altered.

## 18. Source distribution

Top-five source counts are descriptive; no source-diversity constraint was imposed and concentration alone is not a quality failure.

| Retriever | Floods | National Plan | Temporary Shelters |
| --- | ---: | ---: | ---: |
| Dense | 66 | 65 | 94 |
| BM25 | 44 | 83 | 98 |
| Hybrid | 58 | 71 | 96 |

## 19. Latency context

Frozen Phase 12 warmed medians were Dense 8.6110 ms, BM25 0.3927 ms, and Hybrid 10.0295 ms. Startup/model load/index construction were excluded. Phase 13 did not remeasure latency or use it to change the verdict.

## 20. Reproducibility

The full benchmark ran twice from fresh retriever objects. Rankings, coverage, per-question and overall metrics, bootstrap interval, and verdict were identical. Retrieval received only effective query text and k; labels, seed evidence, topic, and query style never entered ranking. Ranking and result artifacts contain no full passage text.

## 21. Limitations

This is a small, three-document, single-publisher, AI-assisted pooled benchmark—not independently human-gold data or exhaustive corpus recall. Relevance does not establish claim entailment and retrieval quality does not establish safer decisions or improved real-world outcomes.

## 22. Implications for Phase 14

Phase 14 may separately evaluate claim support and entailment; it has not been started. Phase 13 has no authority to revise the frozen Phase 10 RL usefulness result, which remains `NO`.
