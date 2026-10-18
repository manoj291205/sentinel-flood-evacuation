import { useEffect, useReducer, useState } from 'react';
import type { MapGeometry } from '../types';
import { SimulationMap, type SimulationMapStep } from './OperationsMap';
import DecisionModal, { type Context, type Decision, type Refusal, type Recheck } from './DecisionModal';
import SpeedControl, { type Speed } from '../sims/SpeedControl';
import styles from './Live.module.css';

type State = { people_stranded?: number; kpis: { waiting: number; in_transit: number; safe: number; stranded?: number; certificates_issued: number }; zones?: { zone_id: string; population_remaining: number; flood_severity_current: number }[]; shelters?: { shelter_id: string; capacity_total: number; occupancy_current: number; capacity_reserved: number; flood_severity_current: number }[]; route_rows?: { Source: string; Destination: string; Status: string }[]; transit_positions?: { group_id: string; source_zone_id: string; destination_shelter_id: string; progress: number }[] };
type Phase = 'IDLE' | 'STARTING' | 'AWAIT_DECISION' | 'SUBMITTING' | 'RESULT' | 'DONE';
export function livePhase(phase: Phase, event: 'START' | 'CONTEXT' | 'SUBMIT' | 'COMMIT' | 'NEXT' | 'END'): Phase {
  if (event === 'START') return 'STARTING';
  if (event === 'END') return 'DONE';
  if ((phase === 'STARTING' || phase === 'SUBMITTING') && event === 'CONTEXT') return 'AWAIT_DECISION';
  if (phase === 'AWAIT_DECISION' && event === 'SUBMIT') return 'SUBMITTING';
  if (phase === 'SUBMITTING' && event === 'COMMIT') return 'RESULT';
  if (phase === 'RESULT' && event === 'NEXT') return 'AWAIT_DECISION';
  return phase;
}
type EscrowStatus = {
  session_id: string; network: 'ONLINE' | 'OFFLINE'; label: string | null; mode: 'escrow' | 'last_known'; timestep: number;
  teams: { team: string; seats_left: number; seats_total: number; zones: string[] }[];
  blocked: { team: string; action_key: string; people: number; reason: string; suggested: string }[];
  last_reconciliation: { returned_to_pool: number; overbooked_seats: number; executed: { cert_id: string }[] } | null;
  certificates: string[]; note: string; honesty: string;
};
type EscrowComparison = { totals: { outages: number; overbooked_outages_escrow: number; overbooked_outages_last_known: number; overbooked_seats_escrow: number; overbooked_seats_last_known: number }; source_path: string; note: string };

const evidence = { source_id: 'ndma-flood-guidelines-2008', page: 64, chunk_id: 'ndma-flood-guidelines-2008-p64-c0' };

async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.flag === 'UNCERTIFIED_OVERRIDE_REFUSED' ? 'Refused: not certified' : data.detail ?? `Request failed (${response.status})`) as Error & { refusal?: Refusal; status?: number };
    error.status = response.status;
    if (data.flag === 'UNCERTIFIED_OVERRIDE_REFUSED') error.refusal = data as Refusal;
    throw error;
  }
  return data as T;
}

export default function LiveSession({ geometry }: { geometry?: MapGeometry }) {
  const [phase, transition] = useReducer(livePhase, 'IDLE');
  const [seed, setSeed] = useState(620003);
  const [world, setWorld] = useState('v4-medium-dt2-v1');
  const [session, setSession] = useState('');
  const [context, setContext] = useState<Context | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [state, setState] = useState<State | null>(null);
  const [rechecks, setRechecks] = useState<Recheck[]>([]);
  const [selected, setSelected] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [tab, setTab] = useState<'Suggestion' | 'In transit' | 'Shelters' | 'Audit log'>('Suggestion');
  const [networkDemo, setNetworkDemo] = useState(false);
  const [escrowMode, setEscrowMode] = useState<'escrow' | 'last_known'>('escrow');
  const [escrowStatus, setEscrowStatus] = useState<EscrowStatus | null>(null);
  const [escrowComparison, setEscrowComparison] = useState<EscrowComparison | null>(null);
  const [history, setHistory] = useState<State['kpis'][]>([]);
  const [feed, setFeed] = useState<{ type: string; text: string }[]>([]);
  const [autoRun, setAutoRun] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const [fastForwarded, setFastForwarded] = useState(0);
  const [safeDelta, setSafeDelta] = useState<number | null>(null);
  const [decisionLog, setDecisionLog] = useState<Decision[]>([]);
  const [refusalCount, setRefusalCount] = useState(0);

  useEffect(() => {
    if (!networkDemo || import.meta.env.MODE === 'test') return;
    void request<EscrowComparison>('/api/escrow/comparison').then(setEscrowComparison).catch(() => setEscrowComparison(null));
  }, [networkDemo]);

  useEffect(() => {
    if (!session || import.meta.env.MODE === 'test') return;
    const url = new URL(`/ws/sessions/${session}`, window.location.href);
    url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url);
    socket.onmessage = event => {
      try { const message = JSON.parse(event.data) as { type: string; payload: unknown }; setFeed(previous => [...previous, { type: message.type, text: JSON.stringify(message.payload).slice(0, 180) }]); }
      catch { /* malformed telemetry does not alter the decision */ }
    };
    return () => socket.close();
  }, [session]);

  useEffect(() => {
    if (!autoRun || !decision || !session) return;
    const timer = window.setTimeout(() => { void fetchContext(session).catch(cause => setError(String(cause))); }, 1500 / speed);
    return () => window.clearTimeout(timer);
  // fetchContext is local to this stateful controller.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun, decision, session, speed]);

  const fetchContext = async (id: string) => {
    let next: Context;
    try { next = await request<Context>(`/api/sessions/${id}/context`); }
    catch (cause) { if ((cause as Error & { status?: number }).status === 409) { transition('END'); setContext(null); setAutoRun(false); return; } throw cause; }
    setContext(next);
    const snapshot = await request<State>(`/api/sessions/${id}/state`);
    setState(snapshot); setHistory(previous => [...previous, { ...snapshot.kpis, stranded: snapshot.people_stranded ?? snapshot.kpis.stranded }]);
    setRechecks(previous => [...previous, ...next.certified.rechecks]);
    setSelected(next.certified.alternatives.find(item => item.certified)?.action_key ?? 'WAIT');
    setDecision(null);
    setReason('');
    transition(phase === 'RESULT' ? 'NEXT' : 'CONTEXT');
  };
  const start = async (mode = escrowMode) => {
    transition('START');
    setBusy(true); setError(''); setRefusal(null);
    try {
      if (networkDemo) {
        const created = await request<EscrowStatus>('/api/escrow/sessions', { seed, regime: world, mode });
        setEscrowStatus(created); setSession(''); setContext(null);
        return;
      }
      setEscrowStatus(null);
      const created = await request<{ session_id: string }>('/api/sessions', { seed, regime: world, certified: true, params_id: 'v4-cert-test-v1' });
      setSession(created.session_id); setRechecks([]); setHistory([]); setFeed([]); setFastForwarded(0); setDecisionLog([]); setRefusalCount(0); setSafeDelta(null);
      await fetchContext(created.session_id);
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  };
  const networkAction = async (action: 'step' | 'cut' | 'restore') => {
    if (!escrowStatus) return;
    setBusy(true); setError('');
    try {
      setEscrowStatus(await request<EscrowStatus>(`/api/escrow/sessions/${escrowStatus.session_id}/${action}`, {}));
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  };
  const submit = async (choice: 'ACCEPT' | 'OVERRIDE' | 'REJECT', alternative = selected, explanation = reason) => {
    if (!session) return;
    transition('SUBMIT');
    setBusy(true); setError(''); setRefusal(null);
    try {
      const result = await request<Decision>(`/api/sessions/${session}/decisions`, {
        decision: choice, selected_action: choice === 'OVERRIDE' ? alternative : undefined,
        reason: choice === 'ACCEPT' ? '' : explanation, evidence,
      });
      setDecision(result); setDecisionLog(previous => [...previous, result]); setRechecks(previous => [...previous, ...result.rechecks]);
      const snapshot = await request<State>(`/api/sessions/${session}/state`);
      setSafeDelta(state == null ? null : snapshot.kpis.safe - state.kpis.safe);
      setState(snapshot); setHistory(previous => [...previous, { ...snapshot.kpis, stranded: snapshot.people_stranded ?? snapshot.kpis.stranded }]);
      setFeed(previous => [...previous, { type: 'decision', text: `${choice} · ${result.certificates.map(cert => cert.cert_id).join(', ')}` }]);
      transition('COMMIT');
    } catch (cause) {
      setError(String(cause));
      const refused = (cause as Error & { refusal?: Refusal }).refusal ?? null;
      setRefusal(refused);
      if (refused) setRefusalCount(previous => previous + 1);
      transition('CONTEXT');
    }
    finally { setBusy(false); }
  };
  const fastForward = async (count: number) => {
    if (!session || !context) return;
    setAutoRun(false); setBusy(true); setError('');
    try {
      let current = context;
      for (let n = 0; n < count; n++) {
        const result = await request<Decision>(`/api/sessions/${session}/decisions`, { decision: 'ACCEPT', reason: '', evidence });
        setDecision(result); setDecisionLog(previous => [...previous, result]); setFastForwarded(previous => previous + 1);
        setFeed(previous => [...previous, { type: 'demo fast-forward', text: `ACCEPT · ${result.certificates.map(cert => cert.cert_id).join(', ')}` }]);
        const snapshot = await request<State>(`/api/sessions/${session}/state`);
        setState(snapshot); setHistory(previous => [...previous, { ...snapshot.kpis, stranded: snapshot.people_stranded ?? snapshot.kpis.stranded }]);
        try { current = await request<Context>(`/api/sessions/${session}/context`); }
        catch (cause) { if ((cause as Error & { status?: number }).status === 409) { transition('END'); setContext(null); return; } throw cause; }
        setContext(current); setRechecks(previous => [...previous, ...current.certified.rechecks]);
      }
      setDecision(null);
    } catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  };
  return <div className={styles.page}>
    <h1>Live Operations</h1>
    <p>Live session · simulated hazards · demo parameters v4-cert-test-v1 (not the evaluated configuration)</p>
    <p>REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED</p>
    {!escrowStatus ? <label><input type="checkbox" checked={networkDemo} onChange={event => { setNetworkDemo(event.target.checked); setEscrowStatus(null); setSession(''); setContext(null); }} />Two-team network demo</label>
      : <button type="button" onClick={() => { setNetworkDemo(false); setEscrowStatus(null); }}>End two-team demo</button>}
    {networkDemo && <fieldset role="radiogroup" aria-label="Escrow"><legend>Escrow</legend>
      <label><input type="radio" name="escrow-mode" checked={escrowMode === 'escrow'} onChange={() => { setEscrowMode('escrow'); if (escrowStatus) void start('escrow'); }} />With escrow</label>
      <label><input type="radio" name="escrow-mode" checked={escrowMode === 'last_known'} onChange={() => { setEscrowMode('last_known'); if (escrowStatus) void start('last_known'); }} />Without escrow</label>
    </fieldset>}
    {!networkDemo && <div className={styles.scenarioCards} role="group" aria-label="Scenario cards">{([['v4-low-dt2-v1', 'Low', 'Lower simulated hazard'], ['v4-medium-dt2-v1', 'Medium', 'Mixed simulated hazard'], ['v4-high-dt2-v1', 'High', 'Higher simulated hazard']] as const).map(([id, name, description]) => <button key={id} type="button" aria-pressed={world === id} onClick={() => setWorld(id)}><b>{name} world</b><small>{description}</small><span>Seed {seed}</span></button>)}</div>}
    <div className={styles.startControls}><label>Seed <input type="number" value={seed} onChange={event => setSeed(Number(event.target.value))} /></label>
      <label>World <select value={world} onChange={event => setWorld(event.target.value)}>
        {['v4-low-dt2-v1', 'v4-medium-dt2-v1', 'v4-high-dt2-v1'].map(item => <option key={item}>{item}</option>)}
      </select></label> <button type="button" onClick={() => void start()} disabled={busy}>Start</button></div>
    {busy && <p role="status">Certifying…</p>}
    {error && <p role="alert">{error}</p>}
    {networkDemo && escrowStatus && <section className={styles.networkPanel} aria-label="Network">
      <h2>Network · <span aria-hidden="true">{escrowStatus.network === 'ONLINE' ? '●' : '◆'}</span> {escrowStatus.network}</h2>
      {escrowStatus.label && <p className={styles.networkOutage}>{escrowStatus.label}</p>}
      <p>{escrowStatus.note}</p>
      <p>Step {escrowStatus.timestep} · {escrowStatus.mode === 'escrow' ? 'With escrow' : 'Without escrow'}</p>
      {escrowStatus.teams.map(team => <div className={styles.teamCard} key={team.team}><strong>{team.team}</strong><p>{team.team}: {team.seats_left} of {team.seats_total} seats left · {team.zones.join(', ')}</p><progress value={team.seats_left} max={team.seats_total} aria-label={`${team.team} seats left`} /></div>)}
      {escrowStatus.blocked.map((row, index) => <p key={`${row.team}-${row.action_key}-${index}`}>Held dispatch · {row.team} · {row.action_key} · {row.people} people · {row.reason} · {row.suggested}</p>)}
      {escrowStatus.last_reconciliation && <p>Rebalanced: {escrowStatus.last_reconciliation.returned_to_pool} seats back to the pool · overbooked seats: {escrowStatus.last_reconciliation.overbooked_seats}</p>}
      {escrowComparison && <div className={styles.outageCompare}><h3>Recorded before / after comparison</h3><p>With escrow: {escrowComparison.totals.overbooked_seats_escrow} overbooked seats in {escrowComparison.totals.overbooked_outages_escrow} of {escrowComparison.totals.outages} outages.</p><p>Last-known: {escrowComparison.totals.overbooked_seats_last_known} overbooked seats in {escrowComparison.totals.overbooked_outages_last_known} of {escrowComparison.totals.outages} outages.</p><small>{escrowComparison.note} · {escrowComparison.source_path}</small></div>}
      {escrowStatus.network === 'ONLINE' ? <button type="button" disabled={busy} onClick={() => void networkAction('cut')}>Cut network</button>
        : <button type="button" disabled={busy} onClick={() => void networkAction('restore')}>Restore network</button>}
      <button type="button" disabled={busy} onClick={() => void networkAction('step')}>Step on</button>
    </section>}
    {refusal && <p>Refusal row: step {refusal.timestep} · {refusal.action_key} · {refusal.verdict ?? 'unknown verdict'} · {refusal.reason}</p>}
    {session && context && <>
      <div className={styles.commandHead}><p>Step {context.certified.timestep} · {geometry ? `${Object.keys(geometry.zones).length} zones on the map` : 'Map unavailable'} · {phase}</p><div><label><input type="checkbox" checked={autoRun} onChange={event => setAutoRun(event.target.checked)} />Auto-run (pauses for each decision)</label><SpeedControl speed={speed} onChange={setSpeed} /><button type="button" disabled={busy} onClick={() => void fastForward(3)}>Demo fast-forward · 3 steps</button><small>With accepts (demo)</small></div></div>
      {fastForwarded > 0 && <p>Demo fast-forward: {fastForwarded} accepts recorded in this session</p>}
      {state && <div className={styles.kpis} aria-label="Simulated population and certificate counts">
        {([['WAITING', state.kpis.waiting], ['ON THE ROAD', state.kpis.in_transit], ['SAFE', state.kpis.safe], ['STRANDED', state.people_stranded ?? state.kpis.stranded], ['CERTIFICATES', state.kpis.certificates_issued], ['STEP', context.certified.timestep]] as const).map(([label, value]) =>
          <div className={styles.kpi} key={label}><span className={styles.kpiLabel}>{label}</span><strong className="mono">{value == null ? '—' : value.toLocaleString('en-IN')}</strong><svg viewBox="0 0 100 24" role="img" aria-label={`${label} history`}><polyline fill="none" stroke="var(--info)" strokeWidth="2" points={history.map((row, index) => `${history.length < 2 ? 0 : index * 100 / (history.length - 1)},${24 - 22 * ((Number(label === 'WAITING' ? row.waiting : label === 'ON THE ROAD' ? row.in_transit : label === 'SAFE' ? row.safe : label === 'STRANDED' ? row.stranded : row.certificates_issued) || 0) / Math.max(1, ...history.map(item => Number(label === 'WAITING' ? item.waiting : label === 'ON THE ROAD' ? item.in_transit : label === 'SAFE' ? item.safe : label === 'STRANDED' ? item.stranded : item.certificates_issued) || 0)))}`).join(' ')} /></svg></div>)}
      </div>}
      <div className={styles.operationsGrid}>
        <section className={styles.mapColumn} aria-label="Live map and state">
          {geometry && <SimulationMap geometry={geometry} step={{
            chosen_key: context.certified.recommendation.action_key,
            candidates: [context.certified.recommendation, ...context.certified.alternatives].filter(item => item.action_key !== 'WAIT').map(item => { const [from, to] = item.action_key.split('->'); const raw = geometry[`route_${from}_${to}`] as [string, number] | undefined; return { action_key: item.action_key, people: null, verdict: item.verdict, svg_path: raw?.[0] ?? '' }; }),
            zone_severity: Object.fromEntries((state?.zones ?? []).map(item => [item.zone_id, item.flood_severity_current])),
            zone_waiting: Object.fromEntries((state?.zones ?? []).map(item => [item.zone_id, item.population_remaining])),
            shelter_severity: Object.fromEntries((state?.shelters ?? []).map(item => [item.shelter_id, item.flood_severity_current])),
            edge_closed_path: (state?.route_rows ?? []).filter(item => item.Status !== 'OPEN').map(item => (geometry[`route_${item.Source}_${item.Destination}`] as [string, number] | undefined)?.[0] ?? '').join(''),
            shelters: (state?.shelters ?? []).map(item => ({ id: item.shelter_id, capacity: item.capacity_total, occupied: item.occupancy_current, reserved: item.capacity_reserved })),
          } satisfies SimulationMapStep} label="Live certified session" speed={speed} moving={(state?.transit_positions ?? []).map(item => ({ group_id: item.group_id, action_key: `${item.source_zone_id}->${item.destination_shelter_id}`, progress: item.progress }))} />}
          <p>Suggestion: {context.certified.recommendation.label}</p><p>{context.certified.note}</p>
          {rechecks.filter(row => row.action === 'MIGRATE' && row.cert_id).map(row => <p key={row.cert_id}>Re-routed automatically as {row.cert_id} (operator notified)</p>)}
          <div className={styles.events}><h2>Timeline and event feed</h2><input type="range" aria-label="Session timeline" min={0} max={Math.max(0, history.length - 1)} value={Math.max(0, history.length - 1)} readOnly /><ul>{feed.map((item, index) => <li key={index}><span>●</span><b>{item.type}</b><span>{item.text}</span></li>)}</ul></div>
        </section>
        <aside className={styles.sidePanel}><div role="tablist">{(['Suggestion', 'In transit', 'Shelters', 'Audit log'] as const).map(item => <button key={item} role="tab" aria-selected={tab === item} onClick={() => setTab(item)}>{item}</button>)}</div>
          {tab === 'Suggestion' && <div className={styles.card}><h2>Pending certified suggestion</h2><p>{context.certified.recommendation.label}</p><p>Lower bound {context.certified.recommendation.lower?.toFixed(3) ?? '—'} · threshold {context.certified.threshold?.toFixed(3) ?? '—'}</p><p>Open the decision pop-up to respond.</p></div>}
          {tab === 'In transit' && <div>{rechecks.map((row, index) => <p key={`${row.group_id}-${index}`}>{row.group_id} · {row.route} · {row.action === 'MIGRATE' ? 're-routed' : row.action === 'KEEP_ESCALATE' ? 'escalated' : 'KEEP'} · lower {row.lower?.toFixed(3) ?? '—'}</p>)}</div>}
          {tab === 'Shelters' && <div>{(state?.shelters ?? []).map(item => <p key={item.shelter_id}>{item.shelter_id} · {item.occupancy_current} occupied + {item.capacity_reserved} reserved / {item.capacity_total}<progress value={item.occupancy_current + item.capacity_reserved} max={item.capacity_total} /></p>)}</div>}
          {tab === 'Audit log' && <div className={styles.events}><ul>{feed.map((item, index) => <li key={index}><span>●</span><b>{item.type}</b><span>{item.text}</span></li>)}</ul></div>}
        </aside>
      </div>
      <DecisionModal context={context} result={decision} refusal={refusal} busy={busy} session={session} safeDelta={safeDelta} onSubmit={(choice, alternative, explanation) => void submit(choice, alternative, explanation)} onNext={() => { setBusy(true); void fetchContext(session).catch(cause => setError(String(cause))).finally(() => setBusy(false)); }} />
    </>}
    {session && phase === 'DONE' && <section className={styles.card}><h2>Episode complete</h2><p>Safe {state?.kpis.safe ?? '—'} · stranded {state?.people_stranded ?? state?.kpis.stranded ?? '—'} · certificates {state?.kpis.certificates_issued ?? '—'}</p><p>Overrides {decisionLog.filter(row => row.audit_record.decision === 'OVERRIDE').length} · declines {decisionLog.filter(row => row.audit_record.decision === 'REJECT').length} · gate refusals {refusalCount}</p><p>Certificates by kind: {Object.entries(decisionLog.flatMap(row => row.certificates).reduce<Record<string, number>>((counts, cert) => ({ ...counts, [cert.kind]: (counts[cert.kind] ?? 0) + 1 }), {})).map(([kind, count]) => `${kind} ${count}`).join(' · ') || '—'}</p><a href={`/api/sessions/${session}/audit.csv`} download>Download audit.csv</a> · <a href={`/api/sessions/${session}/audit.json`} download>Download audit.json</a></section>}
  </div>;
}
