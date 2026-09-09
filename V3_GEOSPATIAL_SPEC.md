# Sentinel-Agent V3 Geospatial Integration

## Status and scientific boundary

This document records the offline Phase 16 **Geospatial Road Network** and Phase 17
**Integrate Stochastic Hazards With Graph Routing** demonstration milestone. It also
supplies the road-network view used by Phase 19 Dashboard V3.

> **Road topology may be derived from real geographic data, while flood hazards,
> population demand, shelter conditions and evacuation decisions remain simulated.**

This is not operational flood routing or evidence of real-world response performance.
It does not use live flood, traffic, shelter, weather, or emergency data.

## Frozen local topology

The compact graph covers a bounded Fort Kochi, Kerala, India demonstration area:

- graph version: `fort-kochi-osm-drive-v1`
- graph artifact: `data/geospatial_v3/fort_kochi_osm_drive_v1.json`
- manifest: `data/geospatial_v3/fort_kochi_osm_drive_v1_manifest.json`
- coordinate semantics: WGS84 latitude/longitude (`EPSG:4326`)
- source: OpenStreetMap contributors, obtained once through the Overpass API
- license/attribution: Open Database License (ODbL), © OpenStreetMap contributors
- topology: 622 nodes and 1,358 directed edges
- fingerprint: `dff7f2065ab5be8685ffd1195cdab1eaf8ce0b28716f5553f146c7565906a6e3`

The download bounds and exact Overpass query are frozen in the manifest. Runtime code
never downloads topology. The original Overpass response is not needed by the demo and
is not tracked.

Each graph node has a deterministic OSM-derived ID and coordinate. Each directed edge
has an ID, endpoints, OSM way ID, highway classification, optional road name, length,
assumed speed, and base travel time. Length is derived from consecutive OSM node
coordinates. Speeds are synthetic class-based demonstration assumptions—not observed
traffic—and are recorded on every edge.

Four synthetic evacuation zones and five synthetic candidate shelters are snapped to
deterministic graph nodes. These points do not represent verified settlements,
population counts, or certified shelters.

## Canonical fingerprint

The static graph fingerprint is SHA-256 over sorted-key, compact JSON containing:

- graph version;
- coordinate reference semantics;
- the canonically ordered node records;
- the canonically ordered directed edge records;
- zone-to-node mappings; and
- shelter-to-node mappings.

Dynamic hazard, travel, and closure fields are excluded. The loader recomputes the hash
and refuses a mismatch. The manifest records the same fingerprint and counts.

## Routing and dynamic road state

`networkx` computes the shortest directed path weighted by current edge travel time.
Closed edges are omitted from the routing graph. If no graph path remains, the pair is
explicitly `UNREACHABLE`; no straight-line or Euclidean fallback is fabricated.

At each prepared simulator timestep, edge hazard is interpolated from the existing
current simulated zone and shelter hazard state, with a small deterministic local
variation from the existing keyed random-stream mechanism. Current travel time applies
the selected LOW/MEDIUM/HIGH configuration's existing hazard travel factor. Closure
probability uses the existing configuration's closure multipliers plus the documented
geospatial base edge probability (`0.005`). Edge closure draws use
`EpisodeRandomStreams` and the existing `ROUTE_CLOSURE` namespace with timestep and edge
ID keys. Closures are absorbing for the episode.

The same scenario seed, uncertainty configuration, and action sequence therefore
reproduce the same edge hazards, closures, and paths. There is no module-global random
number generator.

## Simulator, safety, and planner adapter

`GeospatialRouteOverlay` uses the simulator's existing intervention hook. It derives
the road state, recomputes graph paths, and projects current graph distance, travel time,
hazard exposure, closure probability, and reachability into the existing route-level
`EpisodeState`. The scenario remains compatible with the existing planner contract and
uses `NetworkMode.GRAPH`.

The existing deterministic safety layer stays authoritative. It receives the adapted
state and mechanically excludes a zone/shelter dispatch when the graph has no valid open
path. Risk-Greedy is unchanged and consumes the normal route-level observation. Graph
routing does not add an action outside the canonical mask.

Dispatches already in transit retain the original simulator semantics: their committed
source, destination, population, travel lag, and arrival remain in the dispatch ledger.
A later edge closure affects future route computation but does not delete or silently
reroute an existing dispatch.

## Human decision and dashboard

The Human Override & Audit tab renders a tile-free Altair road graph, so the view remains
useful without internet or basemap access. It distinguishes open roads, closed roads,
the recommended path, simulated zones, and simulated shelters with labels and symbols.
The recommendation reports path distance, estimated travel time, edge count, status,
and compact path ID. Override choices still come only from the existing allowed mask,
which now incorporates graph reachability, and a compact preview is shown.

Decision audits add graph version, fingerprint, local source artifact, path ID/hash,
distance, estimated travel time, and edge count. Full path arrays and authoritative PDF
passage text are not copied into the audit table.

The dashboard banner says **REAL ROAD TOPOLOGY + SIMULATED DISASTER CONDITIONS**. Phase
14B remains visibly paused at 21/135 official dispositions, and no partial metric is
shown.

## Performance and limitations

A local, non-scientific diagnostic on the default fixed-seed episode measured individual
current-path queries at approximately 1.15 ms mean and 1.32 ms maximum on the development
machine. This is a system responsiveness observation, not a policy benchmark.

Limitations include OSM completeness and tagging quality, straight segments between OSM
nodes rather than full way geometry, class-based assumed speeds, fictional entity
placements, synthetic edge hazards and closures, no live traffic, no verified shelter
facilities, and no in-transit rerouting. The geospatial demo creates no new policy or
retrieval performance claim.
