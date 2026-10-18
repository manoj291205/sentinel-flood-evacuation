import { useEffect } from 'react';
import type { MapGeometry } from '../types';
import { SimulationMap } from '../live/OperationsMap';
import type { Run, Trace } from './types';
import type { Speed } from './SpeedControl';
import SpeedControl from './SpeedControl';
import styles from './Sims.module.css';

export default function ReplayPlayer({ trace, run, geometry, index, setIndex, playing, setPlaying, speed, setSpeed }: {
  trace: Trace; run?: Run; geometry: MapGeometry; index: number; setIndex: (index: number) => void;
  playing: boolean; setPlaying: (playing: boolean) => void; speed: Speed; setSpeed: (speed: Speed) => void;
}) {
  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      if (index >= trace.steps.length - 1) setPlaying(false);
      else setIndex(index + 1);
    }, 1000 / speed);
    return () => window.clearTimeout(timer);
  }, [playing, index, speed, trace.steps.length, setIndex, setPlaying]);
  const step = trace.steps[index];
  return <section className={styles.player} aria-label="Recorded simulation replay">
    <div className={styles.playerHead}><div><strong>Certified gate P · {trace.regime} · seed {trace.seed}</strong><small>RECORDED SIMULATION · {trace.source_path}</small></div><span>t = {step.timestep} / {trace.steps.at(-1)?.timestep}</span></div>
    <SimulationMap geometry={geometry} step={step} label="Recorded gate decision" />
    <div className={styles.controls}><button type="button" onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</button><button type="button" onClick={() => setIndex(Math.max(0, index - 1))}>Step back</button><button type="button" onClick={() => setIndex(Math.min(trace.steps.length - 1, index + 1))}>Step forward</button><SpeedControl speed={speed} onChange={setSpeed} /></div>
    <input type="range" aria-label="Replay timestep" min={0} max={trace.steps.length - 1} value={index} onChange={event => setIndex(Number(event.target.value))} list="events" /><datalist id="events">{trace.steps.filter(row => row.chosen_key !== 'WAIT').map(row => <option key={row.timestep} value={trace.steps.indexOf(row)} />)}</datalist>
    <p className={styles.caption}>t={step.timestep} · {step.chosen_key === 'WAIT' ? 'Gate holds; no route chosen' : `Gate chooses ${step.chosen_key}`} · {step.futures_used} futures · {step.looks} looks</p>
    <div className={styles.metrics}><span>Safe <b>{run?.people_safely_arrived ?? '—'}</b><small>Final run summary only</small></span><span>Stranded <b>{run?.stranded_people ?? '—'}</b><small>Final run summary only</small></span><span>Unsafe <b>{run?.unsafe_people ?? '—'}</b><small>Final run summary only</small></span></div>
    <p className={styles.caveat}>Per-step arrivals and transit: —. {trace.note}</p>
  </section>;
}
