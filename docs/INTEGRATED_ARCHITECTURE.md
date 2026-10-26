# Integrated demonstration and trust boundaries

The React console and FastAPI single-process server own a live in-memory session.
Recorded traces, fixtures and scientific artifacts remain separately source-labelled.
No provider requests, model training or official evaluation run in a live session.

```text
Versioned synthetic scenario + cached OSM graph
 -> stochastic observation and transit/arrival events
 -> mechanical / modeled hazard checks
 -> graph paths and certification (V4), Risk-Greedy (V3)
 -> authenticated runtime T2 rules, when actually approved
 -> state-bound API context + authoritative ordered route geometry
 -> React display of recommendation, permission and rule status
 -> request ID + expected version + displayed recommendation identity
 -> session lock: duplicate/stale validation, canonical evidence reference
 -> one validated action (V3 REJECT records only; V4 REJECT commits HOLD)
 -> truthful state/events, pinned route and audit
 -> JSON export including inputs/configuration; certificate replay
```

Current approved rule records contain no T2 rules. T1 records remain advisory and
are visible as such. The registered numeric hazard threshold is a modeled policy;
it is not attributed to NDMA as a directly authorized number. A test-only authorized
fixture demonstrates the rule-sensitive integration without promoting production rules.

The live evidence reference authenticates source/page/chunk membership. It is not a
fresh claim-entailment verdict. Operational citation eligibility separately requires
SUPPORTED plus canonical source/text integrity and valid verbatim spans. The older
verdict-only helper remains a frozen classification metric, not citation permission.

Prospective planner versions enforce authoritative root masks and modeled future
fleet/safety constraints. Historical Phase 10 outputs retain their original algorithm
identity. MPC remains an approximation; it does not share the complete generative
process or information boundary of PPO. PPO horizon truncation used timeout
bootstrapping; no training or historical reward/configuration has been changed.

The API retains idempotency responses for the life of a session and refuses new
requests when its bounded history is full. It never silently evicts a session to
admit another. Explicit close and server restart end in-memory persistence. Export
before closing; use one server process. Multi-process durable storage/authenticated
operator accounts are future deployment requirements, not claims of this prototype.

Exports include source commit and source-tree hash because an uncommitted working
tree can differ from HEAD. They include scenario/configuration, graph identity,
human records, evidence provenance, active rule digest and certificate inputs.
CSV sanitizes spreadsheet formulas at serialization; canonical JSON preserves reasons.
Replay verifies recorded computational inputs, not whether synthetic model assumptions
would hold in a real emergency. Model checkpoints and scientific artifacts are protected.
