import { useMemo, useState } from 'react';
import type { Run } from './types';
import styles from './Sims.module.css';

export default function RunExplorer({ runs, onReplay }: { runs: Run[]; onReplay: (run: Run) => void }) {
  const [system, setSystem] = useState('All');
  const [world, setWorld] = useState('All');
  const [sort, setSort] = useState<keyof Run>('seed');
  const filtered = useMemo(() => runs.filter(row => (system === 'All' || row.system === system) && (world === 'All' || row.regime === world)).sort((a, b) => String(a[sort]).localeCompare(String(b[sort]), undefined, { numeric: true })), [runs, system, world, sort]);
  const systems = [...new Set(runs.map(row => row.system))].sort();
  const worlds = [...new Set(runs.map(row => row.regime))].sort();
  return <section className={styles.explorer}><h2>Run explorer</h2><p>{filtered.length} recorded run summaries · data/eval_results/phase27/runs/*.jsonl</p><div className={styles.filters}><label>System <select value={system} onChange={event => setSystem(event.target.value)}><option>All</option>{systems.map(item => <option key={item}>{item}</option>)}</select></label><label>World <select value={world} onChange={event => setWorld(event.target.value)}><option>All</option>{worlds.map(item => <option key={item}>{item}</option>)}</select></label><label>Sort <select value={sort} onChange={event => setSort(event.target.value as keyof Run)}>{(['seed', 'people_safely_arrived', 'stranded_people', 'unsafe_people', 'wall_seconds'] as const).map(item => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}</select></label></div>
    <div className={styles.plot} role="region" tabIndex={0} aria-label="Distribution of safe, stranded and unsafe people"><svg viewBox="0 0 700 165" role="img" aria-label="Final people safe by system, each dot is a recorded run">{systems.map((item, row) => <g key={item}><text x="0" y={20 + row * 21} fill="currentColor" fontSize="11">{item}</text>{filtered.filter(run => run.system === item).map(run => <circle key={`${run.regime}-${run.seed}`} cx={75 + Math.min(600, run.people_safely_arrived * 1.5)} cy={16 + row * 21} r="2.5" fill="var(--info)" opacity=".45"><title>{item} · {run.regime} · seed {run.seed}: {run.people_safely_arrived} safe; {run.stranded_people} stranded; {run.unsafe_people} unsafe</title></circle>)}</g>)}</svg></div>
    <div className={styles.tableScroll} role="region" tabIndex={0} aria-label="Recorded run table"><table><thead><tr><th>System</th><th>World</th><th>Seed</th><th>Safe</th><th>Stranded</th><th>Unsafe</th><th>Trace</th></tr></thead><tbody>{filtered.map(run => <tr key={`${run.system}-${run.regime}-${run.seed}`}><td>{run.system}</td><td>{run.regime}</td><td>{run.seed}</td><td>{run.people_safely_arrived}</td><td>{run.stranded_people}</td><td>{run.unsafe_people}</td><td>{run.has_trace ? <button type="button" onClick={() => onReplay(run)}>Replay</button> : '— final summary only'}</td></tr>)}</tbody></table></div>
  </section>;
}
