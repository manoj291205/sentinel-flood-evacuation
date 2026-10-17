import { useState } from 'react';
import type { MapGeometry } from '../types';
import styles from './Live.module.css';

type Candidate = { action_key: string; label: string; verdict: string; lower: number | null; certified: boolean; comparison: string };
type Recheck = { group_id: string; route: string; action: string; lower: number | null; cert_id: string | null };
type Context = { certified: { timestep: number; recommendation: Candidate; why: string[]; alternatives: Candidate[]; rechecks: Recheck[]; note: string } };
type Certificate = { cert_id: string; kind: string };
type Decision = { audit_record: { decision: string }; certificates: Certificate[]; rechecks: Recheck[] };
type State = { kpis: { waiting: number; in_transit: number; safe: number; certificates_issued: number } };
type Refusal = { timestep: number; action_key: string; verdict: string | null; reason: string; flag: string };

const evidence = { source_id: 'ndma-flood-guidelines-2008', page: 64, chunk_id: 'ndma-flood-guidelines-2008-p64-c0' };

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.flag === 'UNCERTIFIED_OVERRIDE_REFUSED' ? 'Refused: not certified' : data.detail ?? `Request failed (${response.status})`) as Error & { refusal?: Refusal };
    if (data.flag === 'UNCERTIFIED_OVERRIDE_REFUSED') error.refusal = data as Refusal;
    throw error;
  }
  return data as T;
}

export default function LiveSession({ geometry }: { geometry?: MapGeometry }) {
  const [seed, setSeed] = useState(620003);
  const [world, setWorld] = useState('v4-medium-dt2-v1');
  const [session, setSession] = useState('');
  const [context, setContext] = useState<Context | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [rechecks, setRechecks] = useState<Recheck[]>([]);
  const [action, setAction] = useState<'ACCEPT' | 'OVERRIDE' | 'REJECT'>('ACCEPT');
  const [selected, setSelected] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [tab, setTab] = useState<'Suggestion' | 'In transit'>('Suggestion');

  const fetchContext = async (id: string) => {
    const next = await request<Context>(`/api/sessions/${id}/context`);
    setContext(next);
    setState(await request<State>(`/api/sessions/${id}/state`));
    setRechecks(previous => [...previous, ...next.certified.rechecks]);
    setSelected(next.certified.alternatives.find(item => item.certified)?.action_key ?? 'WAIT');
    setDecision(null);
    setAction('ACCEPT');
    setReason('');
  };
  const start = async () => {
    setBusy(true); setError(''); setRefusal(null);
    try {
      const created = await request<{ session_id: string }>('/api/sessions', { seed, regime: world, certified: true, params_id: 'v4-cert-test-v1' });
      setSession(created.session_id); setRechecks([]);
      await fetchContext(created.session_id);
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  };
  const submit = async (choice: 'ACCEPT' | 'OVERRIDE' | 'REJECT') => {
    if (!session) return;
    setBusy(true); setError(''); setRefusal(null);
    try {
      const result = await request<Decision>(`/api/sessions/${session}/decisions`, {
        decision: choice, selected_action: choice === 'OVERRIDE' ? selected : undefined,
        reason: choice === 'ACCEPT' ? '' : reason, evidence,
      });
      setDecision(result); setRechecks(previous => [...previous, ...result.rechecks]);
      setState(await request<State>(`/api/sessions/${session}/state`));
    } catch (cause) {
      setError(String(cause));
      setRefusal((cause as Error & { refusal?: Refusal }).refusal ?? null);
    }
    finally { setBusy(false); }
  };
  return <div>
    <h1>Live Operations</h1>
    <p>Live session · simulated hazards · demo parameters v4-cert-test-v1 (not the evaluated configuration)</p>
    <p>REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED</p>
    <div><label>Seed <input type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label>
      <label>World <select value={world} onChange={event => setWorld(event.target.value)}>
        {['v4-low-dt2-v1', 'v4-medium-dt2-v1', 'v4-high-dt2-v1'].map(item => <option key={item}>{item}</option>)}
      </select></label> <button type="button" onClick={() => void start()} disabled={busy}>Start</button></div>
    {busy && <p role="status">Certifying…</p>}
    {error && <p role="alert">{error}</p>}
    {refusal && <p>Refusal row: step {refusal.timestep} · {refusal.action_key} · {refusal.verdict ?? 'unknown verdict'} · {refusal.reason}</p>}
    {session && context && <>
      <p>Step {context.certified.timestep} · {geometry ? `${Object.keys(geometry.zones).length} zones on the map` : 'Map unavailable'}</p>
      {state && <div className={styles.kpis} aria-label="Simulated population and certificate counts">
        {([['WAITING', state.kpis.waiting], ['ON THE ROAD', state.kpis.in_transit], ['SAFE', state.kpis.safe], ['CERTIFICATES', state.kpis.certificates_issued]] as const).map(([label, value]) =>
          <div className={styles.kpi} key={label}><span className={styles.kpiLabel}>{label}</span><strong className="mono">{value.toLocaleString('en-IN')}</strong></div>)}
      </div>}
      <div className={styles.operationsGrid}>
        <section className={styles.mapColumn} aria-label="Live map and state">
          {geometry && <div className={styles.mapFrame}><div className={styles.mapCanvas}>
            <svg viewBox={`0 0 ${geometry.W} ${geometry.H}`} width={geometry.W} height={geometry.H} role="img" aria-label="Fort Kochi road topology for the live simulated session">
              <rect width={geometry.W} height={geometry.H} fill="var(--surface)" />
              <path d={geometry.minor} fill="none" stroke="var(--road)" strokeWidth="5" />
              <path d={geometry.major} fill="none" stroke="var(--road)" strokeWidth="10" />
              <path d={geometry.closed} fill="none" stroke="var(--ink)" strokeWidth="3" strokeDasharray="5 4" />
              {Object.entries(geometry.zones).map(([id, [x, y]]) => <g key={id}><circle cx={x} cy={y} r="10" fill="var(--w1)" stroke="var(--ink)" /><text x={x + 12} y={y} className={styles.mapLabel}>{id}</text></g>)}
              {Object.entries(geometry.shelters).map(([id, [x, y]]) => <g key={id}><rect x={x - 9} y={y - 9} width="18" height="18" fill="var(--ok)" stroke="var(--ink)" /><text x={x + 12} y={y} className={styles.mapLabel}>{id}</text></g>)}
            </svg>
          </div></div>}
          <h2>Suggestion: {context.certified.recommendation.label}</h2>
          <ol>{context.certified.why.map(item => <li key={item}>{item}</li>)}</ol>
          <p>{context.certified.note}</p>
          {decision?.certificates.map(cert => <p key={cert.cert_id}><a href={`/decisions?session=${session}&cert=${cert.cert_id}`}>{cert.cert_id}</a> · {cert.kind}</p>)}
          {decision && <p>Latest audit: {decision.audit_record.decision}</p>}
          {rechecks.filter(row => row.action === 'MIGRATE' && row.cert_id).map(row => <p key={row.cert_id}>Re-routed automatically as {row.cert_id} (operator notified)</p>)}
          {decision && <button type="button" disabled={busy} onClick={() => { setBusy(true); void fetchContext(session).catch(cause => setError(String(cause))).finally(() => setBusy(false)); }}>Step on</button>}
        </section>
        <aside className={styles.sidePanel}>
          <div role="tablist"><button role="tab" aria-selected={tab === 'Suggestion'} onClick={() => setTab('Suggestion')}>Suggestion</button><button role="tab" aria-selected={tab === 'In transit'} onClick={() => setTab('In transit')}>In transit</button></div>
          {tab === 'Suggestion' ? <>
            <h2>Alternatives</h2>
            <ul aria-label="Alternatives">{context.certified.alternatives.map(item => <li key={item.action_key}>
              <span>{item.label} · {item.verdict} · {item.lower === null ? '—' : item.lower.toFixed(3)}</span>
              <p>{item.comparison}</p>
              {!item.certified && <p>Not certified — the gate will not dispatch this</p>}
              <button type="button" aria-label={`Choose ${item.label}`} disabled={!item.certified || !!decision || busy} onClick={() => { setSelected(item.action_key); setAction('OVERRIDE'); }}>Choose</button>
            </li>)}</ul>
            {!decision && <><button type="button" disabled={busy} onClick={() => void submit('ACCEPT')}>Accept</button>
              <button type="button" disabled={busy} onClick={() => setAction('OVERRIDE')}>Override</button>
              <button type="button" disabled={busy} onClick={() => setAction('REJECT')}>Reject</button>
              {action !== 'ACCEPT' && <form onSubmit={event => { event.preventDefault(); void submit(action); }}>
                {action === 'OVERRIDE' && <label>Certified alternative <select value={selected} onChange={event => setSelected(event.target.value)}>{context.certified.alternatives.filter(item => item.certified).map(item => <option key={item.action_key} value={item.action_key}>{item.label}</option>)}<option value="WAIT">HOLD</option></select></label>}
                <label>REASON <input value={reason} required onChange={event => setReason(event.target.value)} /></label>
                <button type="submit" disabled={busy}>{action === 'OVERRIDE' ? 'Confirm override' : 'Confirm reject'}</button>
              </form>}</>}
          </> : <div>{rechecks.map((row, index) => <p key={`${row.group_id}-${index}`}>
            {row.group_id} · {row.route} · {row.action === 'MIGRATE' ? 're-routed' : row.action === 'KEEP_ESCALATE' ? 'escalated' : 'KEEP'} · lower {row.lower === null ? '—' : row.lower.toFixed(3)}
            {row.cert_id && <> · Re-routed automatically as {row.cert_id} (operator notified)</>}
          </p>)}</div>}
        </aside>
      </div>
    </>}
  </div>;
}
