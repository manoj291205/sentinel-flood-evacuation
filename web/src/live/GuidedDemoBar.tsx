import type { DemoStep } from '../types';
import styles from './Live.module.css';

interface Props {
  step: DemoStep;
  count: number;
  playing: boolean;
  completed: boolean;
  onPrevious: () => void;
  onNext: () => void;
  onReset: () => void;
  onTogglePlay: () => void;
}

export function GuidedDemoBar({ step, count, playing, completed, onPrevious, onNext, onReset, onTogglePlay }: Props) {
  return <section className={styles.demoBar} aria-label="Guided demo">
    <div className={styles.demoTop}>
      <span className={styles.darkLabel}>GUIDED DEMO</span>
      <span className="mono">Step {step.step_index + 1} / {count} · t = {step.timestep} / 16</span>
      <div className={styles.demoControls}>
        <button type="button" className={styles.secondaryButton} aria-label="Previous step" onClick={onPrevious} disabled={step.step_index === 0}>◀ Back</button>
        <button type="button" className={styles.primaryButton} onClick={onTogglePlay}>{completed ? 'Replay demo' : playing ? 'Pause demo' : 'Run demo'}</button>
        <button type="button" className={styles.secondaryButton} aria-label="Next step" onClick={onNext} disabled={step.step_index === count - 1}>Next ▶</button>
        <button type="button" className={styles.linkButton} onClick={onReset}>Reset</button>
      </div>
    </div>
    <div className={styles.progress} aria-hidden="true">{Array.from({ length: count }, (_, index) => <i key={index} className={index <= step.step_index ? styles.progressDone : ''} />)}</div>
    <p className={styles.caption} role="status" aria-live="polite">{step.caption}</p>
  </section>;
}

const stages = ['SENSE', 'FORECAST 256+ FUTURES', 'SUGGEST', 'CERTIFY', 'OPERATOR DECIDES', 'COMMIT + CERTIFICATE'];

export function PipelineStrip({ current }: { current: number }) {
  return <ol className={styles.pipeline} aria-label="Decision pipeline">
    {stages.map((stage, index) => <li key={stage} className={index + 1 === current ? styles.stageCurrent : index + 1 < current ? styles.stageDone : styles.stageFuture}>
      <span className="mono">{index + 1}</span> {stage}
    </li>)}
  </ol>;
}

export function KpiTiles({ kpis }: { kpis: DemoStep['kpis'] }) {
  const tiles = [
    ['WAITING', kpis.waiting], ['ON THE ROAD', kpis.on_road], ['SAFE', kpis.safe], ['CERTIFICATES', kpis.certificates_issued],
  ] as const;
  return <div className={styles.kpis} aria-label="Simulated population and certificate counts">
    {tiles.map(([label, value]) => <div className={styles.kpi} key={label}>
      <span className={styles.kpiLabel}>{label}</span><strong className="mono">{value.toLocaleString('en-IN')}</strong>
    </div>)}
  </div>;
}
