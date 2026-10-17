export type GateStatus = 'FEASIBLE' | 'UNDECIDED' | 'INFEASIBLE' | 'ALWAYS ALLOWED';

export interface GateCandidate {
  id: string;
  label: string;
  status: GateStatus;
  lower: number | null;
  upper: number | null;
  meta: string;
}

export interface DemoStep {
  step_index: number;
  timestep: number;
  pipeline_stage: number;
  highlight_zone: string | null;
  default_selection: string;
  kind: string;
  caption: string;
  suggestion: { title: string; meta: string; why: string[] };
  gate: { meta: string; candidates: GateCandidate[] };
  decision_required: boolean;
  override_alternatives: string[];
  certificate_id: string | null;
  hold_record: string | null;
  auto_note: string | null;
  events: { timestep: number; kind: string; text: string }[];
  kpis: { waiting: number; on_road: number; safe: number; certificates_issued: number };
  moving_group: { x: number; y: number; label: string } | null;
  g0009_label: string;
  groups: { group_id: string; route: string; meta: string; state: string; tone: string }[];
  shelters: {
    shelter_id: string;
    name: string;
    capacity_total: number;
    occupied: number;
    reserved: number;
    status: string;
  }[];
}

export interface DemoState {
  source: 'FIXTURE' | 'LIVE';
  step_index: number;
  step_count: number;
  step: DemoStep;
  simulated: boolean;
  honesty: string;
}

export interface MapGeometry {
  W: number;
  H: number;
  px_per_m: number;
  major: string;
  minor: string;
  closed: string;
  zones: Record<string, [number, number]>;
  shelters: Record<string, [number, number]>;
  [key: string]: unknown;
}

export interface DemoRoutes {
  [key: string]: { label: string; svg_path: string };
}

export interface CertificateCandidate {
  action_key: string;
  people: number;
  verdict: string;
  successes: number;
  n: number;
  lower: number | null;
  upper: number | null;
  outcome_counts: Record<string, number>;
}

export interface Certificate {
  cert_id: string;
  kind: string;
  timestep: number;
  futures_used: number;
  looks: number;
  params: { eps_dispatch: number; delta: number; a_max: number };
  chosen: { action_key: string; people: number; group_id: string | null };
  operator: { decision: string; actor: string; reason: string };
  commands: { target: string; command: string }[];
  candidates: CertificateCandidate[];
  prev_cert_hash: string | null;
  cert_hash: string;
}

export interface DecisionWhy {
  decision_id: string;
  title: string;
  reasons: string[];
  certified_lower: number;
  threshold: number;
  futures_used: number;
}

export interface EvidenceItem {
  id: string;
  group: string;
  label: string;
  value: unknown;
  display: string;
  unit: string;
  source_path: string;
  source_sha256: string | null;
  note: string | null;
}

export interface EvidenceResponse { source: 'ARTIFACT'; items: EvidenceItem[] }

export interface SystemStatus {
  source: 'FIXTURE' | 'SIMULATED' | 'LIVE';
  broker: { connected: boolean; host: string | null };
  devices: { device_id: string; kind: string; last_seen_utc: string | null; age_s: number | null; online: boolean; firmware: string | null }[];
  topics: string[];
  latency: { p50_ms: number | null; p95_ms: number | null; source_path: string | null };
}

export interface Ack {
  schema: 'ack-v1';
  device_id: string;
  cert_id: string;
  accepted: boolean;
  reason: string;
  ts_utc: string;
}
