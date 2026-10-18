import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import phases from '../content/phases.json';
import styles from './Journey.module.css';

const architecture = [
  ['Scenario', 'A simulated world on a real Fort Kochi road graph'],
  ['Simulator', 'Population, closures, travel and flood conditions evolve by step'],
  ['Safety', 'Hard route and capacity checks'],
  ['Planner', 'Planning and policy candidates'],
  ['Certifier', 'Checks a candidate against sampled futures'],
  ['Dispatch gate', 'Allows only a certified action or a hold'],
  ['Certificates', 'Sealed decision record with replay'],
  ['Console', 'Operator review and reasoned decisions'],
  ['HIL rig', 'Certificate-gated device demonstration'],
  ['NDMA corpus', 'Locally indexed authoritative guidance'],
  ['Tiered rules', 'Source-checked constraints'],
] as const;

export default function Journey() {
  const facts = useQuery({ queryKey: ['project-facts'], queryFn: api.projectFacts });
  const [selected, setSelected] = useState<(typeof architecture)[number]>(architecture[0]);
  return <div className={styles.page}><header><p className={styles.eyebrow}>ABOUT / PROJECT METHOD</p><h1>How it was built</h1><p>From a deterministic simulation baseline to a local operator console. The phase record includes planned, paused and superseded work.</p></header>
    <section><h2>By the numbers</h2><div className={styles.facts}>{Object.entries(facts.data?.facts ?? {}).map(([key, fact]) => <div key={key}><span>{key.replaceAll('_', ' ')}</span><strong>{fact.value ?? '—'}</strong><small>{fact.as_of && `as of ${fact.as_of} · `}{fact.source_path}</small>{fact.value == null && <small>{fact.reason}</small>}</div>)}{facts.isPending && <p role="status">Loading source-labelled facts…</p>}{facts.isError && <p role="alert">Project facts unavailable.</p>}</div></section>
    <section><h2>Architecture</h2><div className={styles.architecture} role="group" aria-label="Architecture components">{architecture.map((item, index) => <button type="button" key={item[0]} onClick={() => setSelected(item)} aria-pressed={selected[0] === item[0]}><span>{item[0]}</span>{index < architecture.length - 1 && <span aria-hidden="true">→</span>}</button>)}</div><div className={styles.detail} role="status"><strong>{selected[0]}</strong><p>{selected[1]}</p></div></section>
    <section><h2>Methods and decisions</h2><div className={styles.methods}><article><h3>Pre-registration</h3><p>Evaluation questions and pass bars were fixed before the Phase 27 runs.</p><small>specs/V4_EVALUATION_PREREG.md</small></article><article><h3>Frozen artifacts</h3><p>Read-only results preserve the observed evaluation. The console keeps missing values visible.</p><small>data/eval_results/phase27/analysis.json</small></article><article><h3>Claim-support history</h3><p>14B was superseded without a score. 14C failed its reliability bar. 14D is the evaluation of record and met its frozen verifier gate.</p><small>data/eval_results/phase14d/test/score.json</small></article><article><h3>D-27</h3><p>Bars 2 and 4 pass; Bars 1 and 3 fail. No outcome-effect claim. The gate has decision-level evidence, and evaluated throughput is low.</p><small>specs/V4_D27_DECISION.md</small></article></div></section>
    <section><h2>Phase timeline</h2><div className={styles.timeline}>{phases.map((row, index) => <article key={`${row.phase}-${index}`}><span className={styles.phase}>PHASE {row.phase}</span><h3>{row.title}</h3><p>{row.status}</p><small>Artifact: {row.artifact_path}</small><small>Timeline source: {row.source_path}</small></article>)}</div></section>
  </div>;
}
