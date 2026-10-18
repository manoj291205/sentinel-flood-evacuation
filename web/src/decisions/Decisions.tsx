import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Certificate, CertificateCandidate } from '../types';
import styles from './Decisions.module.css';
import { useSessionStore } from '../live/sessionStore';

const kinds = ['All', 'Dispatch', 'Migration', 'Hold', 'Override'] as const;

export function actionLabel(action: string): string {
  return action.includes('->') ? action.replace('->', ' → ') : action;
}

export function orderedCertificates(certificates: Certificate[]): Certificate[] {
  return [...certificates].sort((left, right) => right.timestep - left.timestep ||
    (left.kind === 'HOLD' ? -1 : right.kind === 'HOLD' ? 1 : right.cert_id.localeCompare(left.cert_id)));
}

function HashCell({ hash }: { hash: string | null }) {
  if (!hash) return <span className={styles.muted}>— first record</span>;
  return <span className={styles.hash} title={hash}>{hash.slice(0, 12)}<button type="button" aria-label={`Copy hash ${hash.slice(0, 12)}`} onClick={() => void navigator.clipboard?.writeText(hash)}>Copy</button></span>;
}

function Verdict({ verdict }: { verdict: string }) {
  const shape = verdict === 'FEASIBLE' ? '●' : verdict === 'INFEASIBLE' ? '▲' : verdict === 'UNDECIDED' ? '◆' : '□';
  return <span className={styles.verdict} data-verdict={verdict}>{shape} {verdict}</span>;
}

function CandidateTable({ cert }: { cert: Certificate }) {
  const threshold = 1 - cert.params.eps_dispatch;
  const scale = (value: number) => Math.max(0, Math.min(100, (value - 0.8) * 500));
  return <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="Scrollable gate candidates"><table className={styles.table}>
    <caption>Gate candidates and outcomes across sampled futures</caption>
    <thead><tr><th scope="col">Option</th><th scope="col">Verdict</th><th scope="col">Futures OK</th><th scope="col">Certified interval</th><th scope="col">OK / Stranded / Unsafe / Overflow / Policy</th></tr></thead>
    <tbody>{cert.candidates.map((candidate: CertificateCandidate) => <tr key={candidate.action_key}>
      <td>{actionLabel(candidate.action_key)}{candidate.people ? ` · ${candidate.people} people` : ''}</td>
      <td><Verdict verdict={candidate.verdict} /></td>
      <td className="mono">{candidate.n ? `${candidate.successes} / ${candidate.n}` : '—'}</td>
      <td>{candidate.lower === null || candidate.upper === null ? <span>— HOLD is always available</span> : <>
        <span className="mono">[{candidate.lower.toFixed(3)}, {candidate.upper.toFixed(3)}]</span>
        <div className={styles.interval} role="img" aria-label={`Interval ${candidate.lower} to ${candidate.upper}; threshold ${threshold.toFixed(2)}`}>
          <span className={styles.range} style={{ left: `${scale(candidate.lower)}%`, width: `${Math.max(0, scale(candidate.upper) - scale(candidate.lower))}%` }} />
          <span className={styles.threshold} style={{ left: `${scale(threshold)}%` }} />
        </div>
      </>}</td>
      <td className="mono">{['OK', 'STRANDED', 'UNSAFE', 'OVERFLOW', ...('POLICY' in candidate.outcome_counts ? ['POLICY'] : [])].map(key => candidate.outcome_counts[key] ?? 0).join(' / ')}</td>
    </tr>)}</tbody>
  </table></div>;
}

export default function Decisions() {
  const live = useSessionStore();
  const [search, setSearch] = useSearchParams();
  const sessionId = search.get('session');
  const [kind, setKind] = useState<(typeof kinds)[number]>('All');
  const [tamper, setTamper] = useState(false);
  const [replay, setReplay] = useState<{ result: string; mismatched_fields: string[] } | null>(null);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [replaying, setReplaying] = useState(false);
  const list = useQuery({ queryKey: ['certificates', sessionId], queryFn: sessionId ?
    () => api.sessionCertificates(sessionId) : api.certificates });
  const liveCertificates = sessionId && sessionId === live.sessionId ? live.certificates as unknown as Certificate[] : [];
  const ordered = orderedCertificates(liveCertificates.length ? liveCertificates : list.data?.certificates ?? []);
  const selectedId = search.get('cert') ?? ordered[0]?.cert_id ?? '';
  const detail = useQuery({ queryKey: ['certificate', sessionId, selectedId, live.certificates.length], queryFn: sessionId ?
    async () => (await api.sessionCertificates(sessionId)).certificates.find(item => item.cert_id === selectedId) as Certificate :
    () => api.certificate(selectedId), enabled: !!selectedId });
  const why = useQuery({ queryKey: ['why', selectedId], queryFn: () => api.why(selectedId), enabled: !!selectedId && !sessionId, retry: false });
  const visible = ordered.filter(cert => kind === 'All' || cert.kind.toLowerCase() === kind.toLowerCase());

  const select = (id: string) => {
    setSearch(sessionId ? { session: sessionId, cert: id } : { cert: id });
    setTamper(false);
    setReplay(null);
    setReplayError(null);
  };
  const runReplay = async () => {
    setReplaying(true);
    setReplayError(null);
    try { setReplay(await (sessionId ? api.sessionReplay(sessionId, selectedId, tamper) : api.replay(selectedId, tamper))); }
    catch (error) { setReplayError(error instanceof Error ? error.message : 'Replay failed'); }
    finally { setReplaying(false); }
  };

  return <div className={styles.page}>
    <header className={styles.heading}><p className={styles.eyebrow}>VERIFY / DECISIONS</p><h1>Decisions &amp; Certificates</h1>
      <p>Every recorded suggestion, gate verdict, operator action, and replayable certificate in this simulated incident.</p></header>
    {live.sessionId && <label className={styles.filters}><input type="checkbox" checked={sessionId === live.sessionId} onChange={event => setSearch(event.target.checked ? { session: live.sessionId } : {})} />Show this live session</label>}
    {list.isPending && <p role="status">Loading certificates…</p>}
    {list.isError && <div role="alert" className={styles.error}>Certificates unavailable. <button type="button" onClick={() => void list.refetch()}>Retry</button></div>}
    {!list.isPending && !list.isError && <div className={styles.layout}>
      <section className={styles.list} aria-label="Decision list">
        <div className={styles.sectionHead}><h2>This session</h2><span className="mono">{ordered.length} records</span></div>
        <fieldset className={styles.filters}><legend>Kind</legend><div role="radiogroup" aria-label="Kind">{kinds.map(item => <label key={item}><input type="radio" name="kind" checked={kind === item} onChange={() => setKind(item)} />{item}</label>)}</div></fieldset>
        {visible.length === 0 && <p className={styles.empty}>No certificates yet</p>}
        {visible.map(cert => <button type="button" className={styles.row} key={cert.cert_id} aria-pressed={selectedId === cert.cert_id} data-new={liveCertificates.some(item => item.cert_id === cert.cert_id)} onClick={() => select(cert.cert_id)}>
          <span className={styles.rowTop}><strong className="mono">{cert.cert_id}</strong><Verdict verdict={cert.kind} /></span>
          <span>{cert.kind} · {actionLabel(cert.chosen.action_key)} · {cert.chosen.people}</span>
          <small className="mono">t {cert.timestep} · {cert.operator.actor}</small>
        </button>)}
      </section>
      <section className={styles.detail} aria-label="Decision detail">
        {detail.isPending && <p role="status">Loading decision…</p>}
        {detail.isError && <div role="alert" className={styles.error}>Decision unavailable. <button type="button" onClick={() => void detail.refetch()}>Retry</button></div>}
        {detail.data && <>
          <div className={styles.summary}><span className={styles.eyebrow}>{detail.data.kind} · {detail.data.operator.decision}</span>
            <h2>{actionLabel(detail.data.chosen.action_key)} · {detail.data.chosen.people} people</h2>
            <p className="mono">{detail.data.cert_id} · t {detail.data.timestep}</p>
            <p>{detail.data.operator.actor}{detail.data.operator.reason ? ` · ${detail.data.operator.reason}` : ''}</p>
          </div>
          <section className={styles.panel}><h3>Options the gate checked</h3><CandidateTable cert={detail.data} /></section>
          <section className={styles.panel}><h3>Why this suggestion</h3>
            {why.isPending && <p>Loading explanation…</p>}
            {why.isError && <p>No explanation recorded.</p>}
            {why.data && <><ol>{why.data.reasons.map(reason => <li key={reason}>{reason}</li>)}</ol>
              <p className="mono">Certified lower {why.data.certified_lower === null ? '— (HOLD)' : why.data.certified_lower.toFixed(3)} · threshold {why.data.threshold.toFixed(2)} · {why.data.futures_used} futures</p></>}
          </section>
          <section className={styles.panel}><h3>Certificate &amp; bit-exact replay</h3>
            <dl className={styles.meta}><div><dt>Futures used</dt><dd>{detail.data.futures_used}</dd></div><div><dt>Looks</dt><dd>{detail.data.looks}</dd></div><div><dt>Dispatch threshold</dt><dd>{(1 - detail.data.params.eps_dispatch).toFixed(2)}</dd></div></dl>
            <div className={styles.chain}><span>Previous</span><HashCell hash={detail.data.prev_cert_hash} /><span aria-hidden="true">→</span><span>Current</span><HashCell hash={detail.data.cert_hash} /></div>
            <p className={styles.muted}>Replay checks stored inputs and verdicts. The tamper control changes the forecast hash only in this demo request.</p>
            <div className={styles.replayControls}><label><input type="checkbox" checked={tamper} onChange={event => { setTamper(event.target.checked); setReplay(null); }} />Tamper with forecast (demo)</label>
              <button type="button" onClick={() => void runReplay()} disabled={replaying}>Replay certificate</button></div>
            {replay && <p role="status" className={replay.result === 'MATCH' ? styles.match : styles.mismatch}>{replay.result === 'MATCH' ? 'MATCH — regenerated bit-for-bit' : `MISMATCH — ${replay.mismatched_fields.join(', ')}`}</p>}
            {replayError && <p role="alert" className={styles.error}>{replayError}</p>}
          </section>
          <section className={styles.panel}><h3>Audit trail</h3><ol>
            <li>Gate evaluated {detail.data.candidates.length} options across {detail.data.futures_used} sampled futures.</li>
            <li>{detail.data.operator.actor}: {detail.data.operator.decision}{detail.data.operator.reason ? ` · ${detail.data.operator.reason}` : ''}</li>
            <li>Record {detail.data.cert_id} links to its previous certificate hash.</li>
            <li>{detail.data.commands.length ? detail.data.commands.map(item => `${item.target}: ${item.command}`).join('; ') : 'No commands issued.'}</li>
          </ol></section>
        </>}
      </section>
    </div>}
  </div>;
}
