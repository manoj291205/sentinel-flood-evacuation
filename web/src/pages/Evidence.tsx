import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import type { EvidenceItem } from '../types';
import styles from './Pages.module.css';

function EvidenceTable({ group, items }: { group: string; items: EvidenceItem[] }) {
  return <section className={styles.panel}><h2>{group}</h2>{group === 'Exploratory: network outage (not pre-registered)' && <p>Exploratory — not pre-registered</p>}<div className={styles.tableScroll} role="region" tabIndex={0} aria-label={`${group} evidence table`}><table className={styles.table}>
    <thead><tr><th scope="col">Measure</th><th scope="col">Value</th><th scope="col">Unit</th><th scope="col">Source</th></tr></thead>
    <tbody>{items.map(item => <tr key={item.id}><th scope="row">{item.label}</th><td><strong className="mono">{item.display}</strong>{item.note && <small className={styles.note}>{item.note}</small>}</td><td>{item.unit}</td><td><span className={styles.source}>{item.source_path}</span></td></tr>)}</tbody>
  </table></div></section>;
}

function ResultChart({ title, items, limit = 6 }: { title: string; items: EvidenceItem[]; limit?: number }) {
  const values = items.filter(item => typeof item.value === 'number').slice(0, limit);
  const maximum = Math.max(1, ...values.map(item => Number(item.value)));
  return <section className={styles.panel}><h2>{title}</h2>{values.length ? <div className={styles.chartScroll} role="region" tabIndex={0} aria-label={`${title} chart`}><svg viewBox={`0 0 900 ${Math.max(90, values.length * 38 + 10)}`} role="img" aria-label={`${title} artifact values as bars`}>{values.map((item, index) => <g key={item.id}><title>{item.label}: {item.display}</title><text x="0" y={index * 38 + 22} fill="currentColor" fontSize="12">{item.label.slice(0, 42)}</text><rect x="360" y={index * 38 + 5} width={Math.max(2, Number(item.value) / maximum * 330)} height="22" fill="var(--info)" aria-label={`${item.label}: ${item.display}`} /><text x="710" y={index * 38 + 22} fill="currentColor" fontSize="13" className="mono">{item.display}</text></g>)}</svg></div> : <p>— No numeric value available from the artifact manifest.</p>}<p className={styles.note}>Source files: {Array.from(new Set(items.map(item => item.source_path))).join('; ') || '—'}.</p><p className={styles.note}>What this does NOT show: operational performance or an outcome-effect claim.</p></section>;
}

export default function Evidence() {
  const evidence = useQuery({ queryKey: ['evidence'], queryFn: api.evidence });
  const tiers = useQuery({ queryKey: ['rule-tiers'], queryFn: api.ruleTiers });
  const items = evidence.data?.items ?? [];
  const groups = [...new Set(items.map(item => item.group))].filter(group => group !== 'Claim support');
  const analysis = items.find(item => item.id === 'p27-analysis');
  const r = items.find(item => item.id === 'p27-bar1-r');
  const claim = (prefix: string) => items.filter(item => item.id.startsWith(prefix));
  const history = (prefix: string) => items.filter(item => item.id.startsWith(prefix));
  return <div className={styles.page}>
    <header className={styles.heading}><div><p className={styles.eyebrow}>EVIDENCE / RESULTS</p><h1>Evidence &amp; Results</h1><p>Frozen artifact values only. Missing runs remain visible as pending evidence.</p></div><span className={styles.sourceBadge}>READ-ONLY RESEARCH RECORD</span></header>
    <nav className={styles.sectionNav} aria-label="Evidence sections"><a href="#claim-support">Claim support</a><a href="#historical-results">Planners &amp; retrieval</a><a href="#preregistered-results">Pre-registered evaluation</a><a href="#document-rules">Document rules</a></nav>
    {evidence.isPending && <p role="status">Loading evidence manifest…</p>}
    {evidence.isError && <p role="alert" className={styles.error}>Evidence unavailable. <button type="button" onClick={() => void evidence.refetch()}>Retry</button></p>}
    <section id="claim-support" className={styles.panel}><h2>Claim support</h2><p>14D: evaluation of record. 14C: failed on Macro-F1 and span integrity. 14B: superseded.</p></section>
    <EvidenceTable group="14D evaluation of record" items={claim('p14d-')} />
    <ResultChart title="14D verifier measures" items={claim('p14d-')} />
    <EvidenceTable group="14C failed" items={claim('p14c-')} />
    <ResultChart title="14C failed verifier measures" items={claim('p14c-')} />
    <EvidenceTable group="14B superseded" items={claim('p14b-').map(item => ({ ...item, value: null, display: '—', note: 'superseded by 14D' }))} />
    {groups.map(group => <EvidenceTable key={group} group={group} items={items.filter(item => item.group === group && item.id !== 'p27-bar1-r' && !item.id.startsWith('p10-') && !item.id.startsWith('p13-'))} />)}
    <section id="historical-results" className={styles.panel}><h2>Historical planner and retrieval results</h2>
      <EvidenceTable group="Phase 10 planners" items={history('p10-')} />
      <EvidenceTable group="Phase 13 retrieval" items={history('p13-')} />
      <ResultChart title="Phase 10 · planner comparison" items={history('p10-')} />
      <ResultChart title="Phase 13 · retrieval" items={history('p13-')} />
    </section>
    <section id="preregistered-results" className={styles.panel}><h2>Pre-registered evaluation (Phase 27)</h2>
      {analysis?.value == null ? <p>- Not run yet. {analysis?.note ?? 'No analysis artifact is available.'}</p> : <p>{analysis.display}</p>}
      <p>Bar 1 guard R: {r?.display ?? '—'}{r?.note && ` · ${r.note}`}</p>
      <p>{analysis?.value && typeof analysis.value === 'object' ? Object.entries(analysis.value as Record<string, { pass: boolean }>).map(([key, row]) => `${key.toUpperCase()} ${row.pass ? 'PASS' : 'FAIL'}`).join(' · ') : 'Bars: —, artifact unavailable'}. No outcome-effect claim. Source: {analysis?.source_path ?? 'data/eval_results/phase27/analysis.json'}; see the simulation library for the recorded ratio beside the group failure rates.</p>
    </section>
    <section id="document-rules" className={styles.panel}><h2>Document rules (Phase 15′ tiers)</h2>
      <p>Tier from the P15T2 tiering run; T2 needs a SUPPORTED answer from the 14D verifier.</p>
      <div className={styles.tableScroll} role="region" tabIndex={0} aria-label="Document rules table"><table className={styles.table} aria-label="Document rules (Phase 15 tiers)">
        <thead><tr><th scope="col">Rule</th><th scope="col">Predicate</th><th scope="col">Tier</th><th scope="col">14D answer</th><th scope="col">Integrity</th><th scope="col">Note</th></tr></thead>
        <tbody>{(tiers.data?.rules ?? []).map(row => <tr key={row.rule_id}><th scope="row">{row.rule_id}</th><td>{row.predicate ?? '—'}</td><td>{row.tier ?? '—'}</td><td>{row.semantic_outcome ?? '—'}</td><td>{row.source_integrity_pass == null ? '—' : row.source_integrity_pass ? 'pass' : 'fail'}</td><td>{row.note ?? '—'}</td></tr>)}</tbody>
      </table></div>
      {tiers.data?.status !== 'CURRENT' && <p>{tiers.data?.status_reason ?? 'Tier result unavailable'}</p>}
    </section>
  </div>;
}
