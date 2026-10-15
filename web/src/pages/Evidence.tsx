import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import type { EvidenceItem } from '../types';
import styles from './Pages.module.css';

function EvidenceTable({ group, items }: { group: string; items: EvidenceItem[] }) {
  return <section className={styles.panel}><h2>{group}</h2><div className={styles.tableScroll} role="region" tabIndex={0} aria-label={`${group} evidence table`}><table className={styles.table}>
    <thead><tr><th scope="col">Measure</th><th scope="col">Value</th><th scope="col">Unit</th><th scope="col">Source</th></tr></thead>
    <tbody>{items.map(item => <tr key={item.id}><th scope="row">{item.label}</th><td><strong className="mono">{item.display}</strong>{item.note && <small className={styles.note}>{item.note}</small>}</td><td>{item.unit}</td><td><span className={styles.source}>{item.source_path}</span></td></tr>)}</tbody>
  </table></div></section>;
}

export default function Evidence() {
  const evidence = useQuery({ queryKey: ['evidence'], queryFn: api.evidence });
  const items = evidence.data?.items ?? [];
  const groups = [...new Set(items.map(item => item.group))];
  const analysis = items.find(item => item.id === 'p27-analysis');
  return <div className={styles.page}>
    <header className={styles.heading}><p className={styles.eyebrow}>EVIDENCE / RESULTS</p><h1>Evidence &amp; Results</h1><p>Frozen artifact values only. Missing runs remain visible as pending evidence.</p></header>
    {evidence.isPending && <p role="status">Loading evidence manifest…</p>}
    {evidence.isError && <p role="alert" className={styles.error}>Evidence unavailable. <button type="button" onClick={() => void evidence.refetch()}>Retry</button></p>}
    {groups.map(group => <EvidenceTable key={group} group={group} items={items.filter(item => item.group === group)} />)}
    <section className={styles.panel}><h2>Historical planner and retrieval results</h2>
      <p>Phase 10 planner table: - Not in the evidence manifest yet.</p>
      <p>Phase 13 retrieval table: - Not in the evidence manifest yet.</p>
    </section>
    <section className={styles.panel}><h2>Patent experiments (Phase 27 · pre-registered)</h2>
      {analysis?.value == null ? <p>- Not run yet. {analysis?.note ?? 'No analysis artifact is available.'}</p> : <p>{analysis.display}</p>}
    </section>
  </div>;
}
