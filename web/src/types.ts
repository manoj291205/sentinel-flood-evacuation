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
