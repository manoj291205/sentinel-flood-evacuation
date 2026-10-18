import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import RunExplorer from './RunExplorer';
import ReplayPlayer from './ReplayPlayer';
import CompareView from './CompareView';
import type { Index, Run, Trace } from './types';
import type { Speed } from './SpeedControl';
import styles from './Sims.module.css';

const WORLDS = ['v4-medium-dt2-v1', 'v4-high-dt2-v1', 'v4-stress-dt2-v1'];
const get = async <T,>(path: string): Promise<T> => { const response = await fetch(path); if (!response.ok) throw new Error(`Artifact unavailable (${response.status})`); return response.json() as Promise<T>; };

export default function Simulations() {
  const index = useQuery({ queryKey: ['library-index'], queryFn: () => get<Index>('/api/library/index') });
  const geometry = useQuery({ queryKey: ['geometry'], queryFn: api.geometry });
  const [regime, setRegime] = useState(WORLDS[0]);
  const [seed, setSeed] = useState(1_050_000);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(5);
  const [baselineSystem, setBaselineSystem] = useState('A2');
  const [showcase, setShowcase] = useState(false);
  const trace = useQuery({ queryKey: ['library-trace', regime, seed], queryFn: () => get<Trace>(`/api/library/trace/${regime}/${seed}`) });
  const runs = index.data?.runs ?? [];
  const selected = runs.find(row => row.system === 'P' && row.regime === regime && row.seed === seed);
  const baseline = runs.find(row => row.system === baselineSystem && row.regime === regime && row.seed === seed);
  const openRun = (run: Run) => { setPlaying(false); setShowcase(false); setRegime(run.regime); setSeed(run.seed); setPosition(0); };
  useEffect(() => { if (trace.data && position >= trace.data.steps.length - 1 && showcase) { const next = WORLDS.indexOf(regime) + 1; if (next < WORLDS.length) { setRegime(WORLDS[next]); setPosition(0); setPlaying(true); } else { setShowcase(false); setPlaying(false); } } }, [position, trace.data, showcase, regime]);
  const bars = index.data?.analysis.bars;
  return <div className={styles.page}>
    <header><p className={styles.eyebrow}>OPERATE / RECORDED SIMULATIONS</p><h1>Simulation library</h1><p>Replay recorded certifier choices on Fort Kochi roads. Hazards, populations and decisions are simulated.</p></header>
    <div className={styles.hero}><div><strong>{runs.length || '—'}</strong><span>frozen run summaries</span></div><div><strong>{runs.filter(row => row.has_trace).length || '—'}</strong><span>per-step gate traces</span></div><div><strong>—</strong><span>per-step transit and arrival totals unavailable in trace</span></div></div>
    {index.isError && <p role="alert">Library index unavailable. {String(index.error)}</p>}
    <p className={styles.source}>RECORDED SIMULATION · data/eval_results/phase27/runs/*.jsonl · data/eval_results/phase27/states/*.jsonl.gz</p>
    <div className={styles.toolbar}><label>World <select value={regime} onChange={event => { setRegime(event.target.value); setPosition(0); setPlaying(false); }}>{WORLDS.map(item => <option key={item}>{item}</option>)}</select></label><label>Seed <select value={seed} onChange={event => { setSeed(Number(event.target.value)); setPosition(0); setPlaying(false); }}>{[...new Set(runs.filter(row => row.system === 'P' && row.regime === regime).map(row => row.seed))].map(item => <option key={item}>{item}</option>)}</select></label><button type="button" onClick={() => { setRegime(WORLDS[0]); setSeed(1_050_000); setPosition(0); setSpeed(5); setShowcase(true); setPlaying(true); }}>Run-all showcase · medium → high → stress</button></div>
    {showcase && <p role="status" className={styles.showcase}>SHOWCASE · {regime} · {trace.data?.steps[position]?.chosen_key === 'WAIT' ? 'gate holds at this step' : `route ${trace.data?.steps[position]?.chosen_key ?? 'loading'}`}</p>}
    {trace.isPending || geometry.isPending ? <p role="status">Loading recorded road trace…</p> : trace.isError || geometry.isError ? <p role="alert">Trace unavailable. {String(trace.error ?? geometry.error)}</p> : trace.data && geometry.data && <ReplayPlayer trace={trace.data} run={selected} geometry={geometry.data} index={position} setIndex={setPosition} playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} />}
    {trace.data && geometry.data && <><div className={styles.toolbar}><label>Compare with <select value={baselineSystem} onChange={event => setBaselineSystem(event.target.value)}>{['A', 'A2', 'B', 'HOLD', 'P-noFC', 'P-noHyst'].map(item => <option key={item}>{item}</option>)}</select></label></div><CompareView trace={trace.data} gate={selected} baseline={baseline} geometry={geometry.data} index={position} speed={speed} /></>}
    <section className={styles.decision}><h2>D-27 · pre-registered decision</h2><p>Bar 1 {bars ? (bars.bar1.pass ? 'PASS' : 'FAIL') : '—'} · Bar 2 {bars ? (bars.bar2.pass ? 'PASS' : 'FAIL') : '—'} · Bar 3 {bars ? (bars.bar3.pass ? 'PASS' : 'FAIL') : '—'} · Bar 4 {bars ? (bars.bar4.pass ? 'PASS' : 'FAIL') : '—'}.</p><p>No outcome-effect claim. Recorded group failure rates: A {index.data?.analysis.E1_P_vs_A ? `${(index.data.analysis.E1_P_vs_A.mean_rate_baseline * 100).toFixed(1)}%` : '—'}, P {index.data?.analysis.E1_P_vs_A ? `${((index.data.analysis.E1_P_vs_A.mean_rate_baseline + index.data.analysis.E1_P_vs_A.mean_diff) * 100).toFixed(1)}%` : '—'}, alongside throughput guard R = {index.data?.analysis.E2_ratio_P_over_A2?.toFixed(3) ?? '—'}; P delivers fewer people under the evaluated configuration.</p><small>{index.data?.analysis_source ?? 'data/eval_results/phase27/analysis.json'}</small></section>
    <RunExplorer runs={runs} onReplay={openRun} />
  </div>;
}
