import type { SimulationMapStep } from '../live/OperationsMap';

export type Run = {
  system: string; regime: string; seed: number; has_trace: boolean; source_path: string;
  people_safely_arrived: number; stranded_people: number; unsafe_people: number;
  dispatched_groups: number; decisions: number; wall_seconds: number; status: string;
};
export type TraceStep = SimulationMapStep & { timestep: number; looks: number; futures_used: number };
export type Trace = { regime: string; seed: number; steps: TraceStep[]; source_path: string; note: string };
export type Index = { runs: Run[]; analysis: { bars: Record<string, { pass: boolean }>;
  E1_P_vs_A: { mean_rate_baseline: number; mean_diff: number }; E2_ratio_P_over_A2: number };
  analysis_source: string };
