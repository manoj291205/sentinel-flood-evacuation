import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { LiveContext, Decision, Refusal, RouteGeometry, Recheck } from './DecisionModal';
import { prepareDecision, type PreparedDecision } from './decisionRequest';

export type Subject = {
  action_key: string; kind: 'DISPATCH' | 'HOLD'; people: number | null;
  zone_id: string | null; zone_name?: string | null; zone_waiting?: number | null;
  zone_flood_severity?: number | null; shelter_id: string | null;
  shelter_name?: string | null; shelter_seats_free_before?: number | null;
  shelter_seats_free_after?: number | null; route_label?: string | null;
  route_length_km?: number | null; eta_minutes?: number | null;
  closed_edges_on_route?: string[] | null;
};
export type Kpis = { waiting: number; in_transit: number; safe: number; certificates_issued: number; stranded?: number };
export type LiveState = {
  current_timestep?: number; graph_fingerprint?: string; state_version?: number; closed_edge_svg_path?: string; terminal?: boolean; people_stranded?: number | null; people_unsafe_arrival?: number | null; people_overflow?: number | null; kpis: Kpis;
  summary?: { terminal_reason?: string | null };
  zones?: { zone_id: string; population_remaining: number; flood_severity_current: number }[];
  shelters?: { shelter_id: string; capacity_total: number; occupancy_current: number; capacity_reserved: number; capacity_available?: number; flood_severity_current: number }[];
  route_rows?: { Source: string; Destination: string; Status: string }[];
  transit_positions?: { group_id: string; source_zone_id: string; destination_shelter_id: string; progress: number; svg_path?: string }[];
};
export type OperatorEntry = {
  id: string; step: number; utc: string;
  decision: 'ACCEPT' | 'OVERRIDE' | 'DECLINE' | 'REFUSED' | 'AUTO_REROUTE' | 'FAST_FORWARD_ACCEPT';
  subject: Subject; alternative?: Subject; reason_code?: string; reason?: string;
  cert_ids: string[]; kpi_delta: { safe: number | null; waiting: number | null; in_transit: number | null };
  source: 'LIVE' | 'PRACTICE';
  route?: RouteGeometry;
};
export type FeedItem = { id: string; text: string; tone: 'ok' | 'warn' | 'danger' | 'info'; href?: string };
export type Toast = { id: number; text: string; tone: FeedItem['tone'] };
type Message = { seq?: number; type: 'decision' | 'certificate' | 'recheck' | 'event' | 'refusal' | 'state'; payload: Record<string, unknown> };

export function committedDecisionCount(entries: OperatorEntry[], source: OperatorEntry['source'] = 'LIVE'): number {
  return entries.filter(entry => entry.source === source && ['ACCEPT', 'OVERRIDE', 'DECLINE', 'FAST_FORWARD_ACCEPT'].includes(entry.decision)).length;
}

export function episodeOutcomeLabel(reason?: string | null): string {
  if (reason === 'ALL_FAILED') return 'Episode ended — all outcomes failed';
  if (reason === 'MIXED_OUTCOME') return 'Episode ended — mixed safe and failed outcomes';
  if (reason === 'HORIZON_REACHED') return 'Episode ended — horizon reached';
  if (reason === 'ALL_EVACUATED') return 'Episode complete — all evacuees arrived safely';
  return 'Episode ended — review the outcome totals';
}

function migrationEntry(cert: Record<string, unknown> | undefined, row: Recheck, step: number,
                        routes?: Record<string, RouteGeometry>): OperatorEntry {
  const route = row.cert_id ? routes?.[row.cert_id] : undefined;
  const base = restoredEntry(cert ?? { cert_id: row.cert_id ?? row.group_id, timestep: step,
    chosen: { action_key: route?.action_key ?? 'UNAVAILABLE' }, kind: 'MIGRATION' });
  return { ...base, id: `migration-${row.cert_id ?? `${row.group_id}-${step}`}`, decision: 'AUTO_REROUTE',
    route, reason: `Group ${row.group_id} re-routed automatically` };
}

export function subjectOf(candidate: { action_key: string; subject?: Subject }): Subject {
  return candidate.subject ?? { action_key: candidate.action_key, kind: candidate.action_key === 'WAIT' ? 'HOLD' : 'DISPATCH', people: null, zone_id: null, shelter_id: null };
}
export function subjectSentence(subject: Subject): string {
  if (subject.kind === 'HOLD') return 'HOLD: no dispatch this step';
  const people = subject.people == null ? '— people' : `${subject.people} people`;
  const zone = subject.zone_name ?? subject.zone_id ?? '—';
  const shelter = subject.shelter_name ?? subject.shelter_id ?? '—';
  return `Dispatch ${people} · ${zone} → ${shelter} · via ${subject.route_label ?? '—'} · road travel estimate ${subject.eta_minutes == null ? '—' : `${Number(subject.eta_minutes.toFixed(2))} min`}`;
}
function restoredEntry(cert: Record<string, unknown>): OperatorEntry {
  const chosen = cert.chosen as { action_key?: string; people?: number } | undefined;
  const operator = cert.operator as { decision?: string; reason?: string } | undefined;
  const key = chosen?.action_key ?? 'WAIT';
  const [zone, shelter] = key.split('->');
  const decision = cert.kind === 'MIGRATION' ? 'AUTO_REROUTE' : operator?.decision === 'REJECT' ? 'DECLINE' : operator?.decision === 'OVERRIDE' ? 'OVERRIDE' : 'ACCEPT';
  return { id: `${cert.kind === 'MIGRATION' ? 'migration' : 'restored'}-${String(cert.cert_id)}`, step: Number(cert.timestep ?? 0), utc: String(cert.utc ?? ''), decision,
    subject: { action_key: key, kind: key === 'WAIT' ? 'HOLD' : 'DISPATCH', people: chosen?.people ?? null,
      zone_id: key === 'WAIT' ? null : zone, shelter_id: key === 'WAIT' ? null : shelter },
    cert_ids: [String(cert.cert_id)], kpi_delta: { safe: null, waiting: null, in_transit: null }, source: 'LIVE', reason: operator?.reason };
}
export function toFeedItem(message: Message, sessionId = ''): FeedItem {
  const payload = message.payload;
  const id = String(message.seq ?? `${message.type}-${payload.timestep ?? payload.cert_id ?? payload.action_key ?? ''}`);
  const cert = String(payload.cert_id ?? '');
  const link = cert && sessionId ? `/decisions?session=${encodeURIComponent(sessionId)}&cert=${encodeURIComponent(cert)}` : undefined;
  switch (message.type) {
    case 'decision': return { id, text: `Step ${payload.timestep ?? '—'}: ${payload.decision ?? 'Decision'} recorded`, tone: 'ok' };
    case 'certificate': return { id, text: `${cert || 'Certificate'} issued · ${payload.kind ?? 'decision'}`, tone: 'ok', href: link };
    case 'recheck': return { id, text: payload.action === 'MIGRATE' ? `Re-routed automatically as ${cert || 'certificate pending'} · ${payload.group_id ?? 'group'}` : `${payload.group_id ?? 'Group'}: ${payload.action === 'KEEP_ESCALATE' ? 'escalated' : 'route re-checked'}`, tone: payload.action === 'KEEP_ESCALATE' ? 'warn' : 'info', href: link };
    case 'event': return { id, text: `${payload.event_type ?? payload.type ?? payload.kind ?? 'Simulation event'}${payload.group_id ? ` · ${payload.group_id}` : ''}`, tone: 'info' };
    case 'refusal': return { id, text: `Gate refused ${payload.action_key ?? 'route'} · ${payload.verdict ?? 'not certified'}`, tone: 'danger' };
    case 'state': return { id, text: `State updated · step ${payload.current_timestep ?? payload.timestep ?? '—'}`, tone: 'info' };
  }
}

const evidence = { source_id: 'ndma-flood-guidelines-2008', page: 64, chunk_id: 'ndma-flood-guidelines-2008-p64-c0' };
async function request<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : data.detail?.message;
    const error = new Error(detail ?? `Request failed (${response.status})`) as Error & { status: number; refusal?: Refusal };
    error.status = response.status;
    if (data.flag === 'UNCERTIFIED_OVERRIDE_REFUSED') error.refusal = data;
    throw error;
  }
  return data as T;
}
function initialSession(): { sessionId: string; world: string; seed: number; horizonSteps: number | null } {
  try { return JSON.parse(sessionStorage.getItem('sentinel-live-session') ?? 'null') ?? { sessionId: '', world: 'v4-medium-dt2-v1', seed: 620003, horizonSteps: null }; }
  catch { return { sessionId: '', world: 'v4-medium-dt2-v1', seed: 620003, horizonSteps: null }; }
}
type SessionStore = {
  operationsMode: 'session' | 'guided'; setOperationsMode: (mode: 'session' | 'guided') => void;
  sessionId: string; world: string; seed: number; horizonSteps: number | null; phase: 'IDLE' | 'STARTING' | 'AWAIT_DECISION' | 'SUBMITTING' | 'RESULT' | 'DONE' | 'ENDED';
  context: LiveContext | null; state: LiveState | null; kpiHistory: Kpis[]; log: OperatorEntry[];
  feed: FeedItem[]; certificates: Record<string, unknown>[]; refusals: Refusal[]; toast: Toast | null;
  result: Decision | null; error: string; busy: boolean; autoRunning: boolean;
  start: (world: string, seed: number) => Promise<void>;
  submit: (choice: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', alt?: string, code?: string, text?: string) => Promise<boolean>;
  stepOn: () => Promise<void>; autoRun: (speed: number | null) => void;
  fastForward: (n: number) => Promise<void>; end: () => Promise<void>;
  practice: (decision: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', subject: Subject, step: number, certId?: string, reason?: string) => void;
  clearToast: () => void;
};
const emptySession: SessionStore = {
  operationsMode: 'session', setOperationsMode: () => {},
  sessionId: '', world: 'v4-medium-dt2-v1', seed: 620003, horizonSteps: null, phase: 'IDLE', context: null, state: null,
  kpiHistory: [], log: [], feed: [], certificates: [], refusals: [], toast: null, result: null,
  error: '', busy: false, autoRunning: false,
  start: async () => {}, submit: async () => false, stepOn: async () => {}, autoRun: () => {},
  fastForward: async () => {}, end: async () => {}, practice: () => {}, clearToast: () => {},
};
const ContextStore = createContext<SessionStore>(emptySession);
export function useSessionStore(): SessionStore {
  return useContext(ContextStore);
}
export function SessionProvider({ children }: { children: ReactNode }) {
  const [operationsMode, setOperationsMode] = useState<'session' | 'guided'>('session');
  const initial = useRef(initialSession());
  const [sessionId, setSessionId] = useState(initial.current.sessionId);
  const [world, setWorld] = useState(initial.current.world);
  const [seed, setSeed] = useState(initial.current.seed);
  const [horizonSteps, setHorizonSteps] = useState<number | null>(initial.current.horizonSteps ?? null);
  const [phase, setPhase] = useState<SessionStore['phase']>('IDLE');
  const [context, setContext] = useState<LiveContext | null>(null);
  const [state, setState] = useState<LiveState | null>(null);
  const stateRef = useRef<LiveState | null>(null);
  const contextRef = useRef<LiveContext | null>(null);
  const pendingRequest = useRef<{ intent: string; body: PreparedDecision } | null>(null);
  const submitting = useRef(false);
  const [kpiHistory, setKpiHistory] = useState<Kpis[]>([]);
  const [log, setLog] = useState<OperatorEntry[]>([]);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [certificates, setCertificates] = useState<Record<string, unknown>[]>([]);
  const [refusals, setRefusals] = useState<Refusal[]>([]);
  const [toast, setToast] = useState<Toast | null>(null);
  const [result, setResult] = useState<Decision | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [speed, setSpeed] = useState<number | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);
  const seqSeen = useRef(new Set<number>());
  const fastForwarding = useRef(false);
  const setSnapshot = useCallback((next: LiveState) => { stateRef.current = next; setState(next); setKpiHistory(rows => [...rows, next.kpis]); }, []);
  const notify = useCallback((text: string, tone: Toast['tone']) => {
    window.clearTimeout(toastTimer.current);
    setToast({ id: Date.now(), text, tone });
    toastTimer.current = window.setTimeout(() => setToast(null), 4000);
  }, []);
  const addCertificates = useCallback((items: Record<string, unknown>[]) => {
    setCertificates(previous => {
      const byId = new Map(previous.map(item => [String(item.cert_id), item]));
      for (const item of items) byId.set(String(item.cert_id), item);
      return [...byId.values()];
    });
  }, []);
  const fetchContext = useCallback(async (id: string) => {
    try {
      const next = await request<LiveContext>(`/api/sessions/${id}/context?include_subject=true`);
      contextRef.current = next; setContext(next); setPhase('AWAIT_DECISION'); setResult(null);
      const [snapshot, issued] = await Promise.all([
        request<LiveState>(`/api/sessions/${id}/state`),
        request<{ certificates: Record<string, unknown>[]; executed_routes?: Record<string, RouteGeometry> }>(`/api/sessions/${id}/certificates`),
      ]);
      setSnapshot(snapshot); addCertificates(issued.certificates);
      for (const row of next.certified.rechecks.filter(item => item.action === 'MIGRATE')) {
        const cert = issued.certificates.find(item => item.cert_id === row.cert_id);
        const reroute = migrationEntry(cert, row, next.certified.timestep, issued.executed_routes);
        setLog(previous => previous.some(item => item.id === reroute.id) ? previous : [reroute, ...previous]);
        setFeed(previous => [toFeedItem({ type: 'recheck', payload: row as unknown as Record<string, unknown> }, id), ...previous]);
        notify(`Group ${row.group_id} re-routed · ${row.cert_id ?? 'certificate pending'}`, 'warn');
      }
    } catch (cause) {
      if ((cause as Error & { status?: number }).status === 409) { contextRef.current = null; setContext(null); setPhase('DONE'); }
      else throw cause;
    }
  }, [setSnapshot, addCertificates, notify]);
  useEffect(() => {
    if (!sessionId) return;
    try { sessionStorage.setItem('sentinel-live-session', JSON.stringify({ sessionId, world, seed, horizonSteps })); } catch { /* storage unavailable */ }
  }, [sessionId, world, seed, horizonSteps]);
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    void Promise.all([
      request<LiveState>(`/api/sessions/${sessionId}/state`),
      request<{ timeline: Record<string, unknown>[] }>(`/api/sessions/${sessionId}/timeline`),
      request<{ certificates: Record<string, unknown>[]; executed_routes?: Record<string, RouteGeometry> }>(`/api/sessions/${sessionId}/certificates`),
      request<{ audit?: Record<string, unknown>[]; refusals?: Refusal[] }>(`/api/sessions/${sessionId}/audit`),
    ]).then(async ([snapshot, timeline, certs, audit]) => {
      if (cancelled) return;
      setSnapshot(snapshot); setCertificates(certs.certificates); setRefusals(audit.refusals ?? []);
      setLog(previous => previous.length ? previous : [
        ...certs.certificates.map(cert => ({ ...restoredEntry(cert), route: certs.executed_routes?.[String(cert.cert_id)] })),
        ...(audit.refusals ?? []).map((refusal, index): OperatorEntry => ({
          id: `restored-refusal-${index}`, step: refusal.timestep, utc: '', decision: 'REFUSED',
          subject: subjectOf({ action_key: refusal.action_key }), cert_ids: [],
          kpi_delta: { safe: 0, waiting: 0, in_transit: 0 }, source: 'LIVE', reason: refusal.reason,
        })),
      ].sort((a, b) => b.step - a.step));
      setFeed(timeline.timeline.map((event, index) => toFeedItem({ seq: index, type: 'event', payload: event }, sessionId)));
      await fetchContext(sessionId);
    }).catch(cause => {
      if (cancelled) return;
      if ((cause as Error & { status?: number }).status === 404) { setPhase('ENDED'); setError('Session ended — start a new one'); }
      else setError(String(cause));
    });
    return () => { cancelled = true; };
  }, [sessionId, setSnapshot, fetchContext]);
  useEffect(() => {
    if (!sessionId || import.meta.env.MODE === 'test' || import.meta.env.VITE_API_MOCK === '1') return;
    const url = new URL(`/ws/sessions/${sessionId}`, window.location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(url);
    socket.onmessage = event => {
      try {
        const message = JSON.parse(event.data) as Message;
        if (message.seq != null && seqSeen.current.has(message.seq)) return;
        if (message.seq != null) seqSeen.current.add(message.seq);
        setFeed(rows => [toFeedItem(message, sessionId), ...rows]);
        if (message.type === 'state') setSnapshot(message.payload as LiveState);
        if (message.type === 'certificate') addCertificates([message.payload]);
        if (message.type === 'refusal') setRefusals(rows => [...rows, message.payload as Refusal]);
      } catch { /* malformed telemetry is ignored */ }
    };
    return () => socket.close();
  }, [sessionId, setSnapshot, addCertificates]);
  const start = useCallback(async (nextWorld: string, nextSeed: number) => {
    setBusy(true); setError(''); setPhase('STARTING'); setSpeed(null);
    try {
      const created = await request<{ session_id: string; horizon_steps?: number }>('/api/sessions', { seed: nextSeed, regime: nextWorld, certified: true, params_id: 'v4-cert-test-v1' });
      setWorld(nextWorld); setSeed(nextSeed); setHorizonSteps(created.horizon_steps ?? null); setLog([]); setFeed([]); setCertificates([]); setRefusals([]); setKpiHistory([]);
      seqSeen.current.clear(); setSessionId(created.session_id); notify('Live session started', 'info');
    } catch (cause) { setPhase('IDLE'); setError(String(cause)); }
    finally { setBusy(false); }
  }, [notify]);
  const submit = useCallback(async (choice: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', alt = '', code = '', text = '') => {
    const pending = contextRef.current?.certified;
    if (!sessionId || !pending || busy || submitting.current) return false;
    const identity = contextRef.current?.decision_identity;
    if (!identity || identity.session_id !== sessionId) { setError('Refresh the current server suggestion before deciding.'); return false; }
    const intent = { decision: choice === 'DECLINE' ? 'REJECT' as const : choice,
      selected_action: choice === 'OVERRIDE' ? alt : undefined,
      reason: choice === 'ACCEPT' ? '' : `${code}: ${text}`, evidence };
    const intentKey = JSON.stringify(intent);
    if (pendingRequest.current && pendingRequest.current.intent !== intentKey) {
      setError('Previous outcome is unknown. Retry the same decision before choosing another action.'); return false;
    }
    if (!pendingRequest.current) {
      try { pendingRequest.current = { intent: intentKey, body: prepareDecision(identity, intent) }; }
      catch (cause) { setError(String(cause)); return false; }
    }
    submitting.current = true;
    setBusy(true); setError(''); setPhase('SUBMITTING');
    const candidate = choice === 'OVERRIDE' ? pending.alternatives.find(item => item.action_key === alt) : pending.recommendation;
    const subject = subjectOf(candidate ?? pending.recommendation);
    const before = stateRef.current?.kpis;
    try {
      const response = await request<Decision & { state: LiveState }>(`/api/sessions/${sessionId}/decisions`, pendingRequest.current.body);
      pendingRequest.current = null;
      const next = response.state ?? await request<LiveState>(`/api/sessions/${sessionId}/state`);
      const delta = { safe: next.kpis.safe - (before?.safe ?? next.kpis.safe), waiting: next.kpis.waiting - (before?.waiting ?? next.kpis.waiting), in_transit: next.kpis.in_transit - (before?.in_transit ?? next.kpis.in_transit) };
      const certIds = (response.certificates ?? []).map(item => item.cert_id);
      const loggedDecision = choice === 'ACCEPT' && fastForwarding.current ? 'FAST_FORWARD_ACCEPT' : choice;
      const entry: OperatorEntry = { id: `${sessionId}-${pending.timestep}-${Date.now()}`, step: pending.timestep, utc: new Date().toISOString(), decision: loggedDecision,
        subject, alternative: choice === 'OVERRIDE' ? subjectOf(pending.recommendation) : undefined,
        reason_code: code || undefined, reason: text || undefined, cert_ids: certIds, kpi_delta: delta, source: 'LIVE',
        route: Object.values(response.executed_routes ?? {}).find(route => route.action_key === subject.action_key) };
      setLog(rows => [entry, ...rows]); setSnapshot(next); addCertificates(response.certificates ?? []); setResult(response); setPhase('RESULT');
      setFeed(rows => [{ id: entry.id, text: `${loggedDecision} recorded · ${subjectSentence(subject)}${certIds.length ? ` · ${certIds.join(', ')}` : ''}`, tone: 'ok', href: certIds[0] ? `/decisions?session=${sessionId}&cert=${certIds[0]}` : undefined }, ...rows]);
      for (const row of response.rechecks ?? []) if (row.action === 'MIGRATE') {
        const cert = response.certificates.find(item => item.cert_id === row.cert_id);
        const reroute = migrationEntry(cert, row, pending.timestep, response.executed_routes);
        setLog(rows => rows.some(item => item.id === reroute.id) ? rows : [reroute, ...rows]);
      }
      notify(`${choice === 'DECLINE' ? 'Decline' : choice === 'OVERRIDE' ? 'Override' : 'Accept'} recorded${certIds.length ? ` · ${certIds.join(', ')} issued` : ''}`, 'ok');
      return true;
    } catch (cause) {
      const status = (cause as Error & { status?: number }).status;
      if (status != null && status < 500) pendingRequest.current = null;
      if (status === 409) {
        await fetchContext(sessionId); setError('The suggestion changed. Review the refreshed state before deciding.');
        return false;
      }
      const refusal = (cause as Error & { refusal?: Refusal }).refusal;
      if (refusal) {
        setRefusals(rows => [...rows, refusal]);
        const entry: OperatorEntry = { id: `${sessionId}-refused-${Date.now()}`, step: pending.timestep, utc: new Date().toISOString(), decision: 'REFUSED', subject, cert_ids: [], kpi_delta: { safe: 0, waiting: 0, in_transit: 0 }, source: 'LIVE', reason_code: code, reason: text };
        setLog(rows => [entry, ...rows]); setFeed(rows => [toFeedItem({ type: 'refusal', payload: refusal as unknown as Record<string, unknown> }, sessionId), ...rows]);
        notify(`Gate refused ${alt} · not certified`, 'danger'); setPhase('AWAIT_DECISION');
      } else { setError(`${String(cause)}${pendingRequest.current ? ' Outcome unknown; retry this same decision to recover its original result.' : ''}`); setPhase('AWAIT_DECISION'); }
      return false;
    } finally { submitting.current = false; setBusy(false); }
  }, [sessionId, busy, setSnapshot, addCertificates, notify, fetchContext]);
  const stepOn = useCallback(async () => {
    if (!sessionId) return;
    setBusy(true);
    try { await fetchContext(sessionId); }
    catch (cause) { setError(String(cause)); }
    finally { setBusy(false); }
  }, [sessionId, fetchContext]);
  const fastForward = useCallback(async (n: number) => {
    setSpeed(null);
    fastForwarding.current = true;
    try {
      for (let i = 0; i < n; i++) {
        if (!contextRef.current) break;
        if (!await submit('ACCEPT')) break;
        await stepOn();
      }
    } finally { fastForwarding.current = false; }
  }, [submit, stepOn]);
  useEffect(() => {
    if (speed == null || phase !== 'RESULT') return;
    const timer = window.setTimeout(() => void stepOn(), 1500 / speed);
    return () => window.clearTimeout(timer);
  }, [speed, phase, stepOn]);
  const end = useCallback(async () => {
    if (sessionId && !window.confirm('End this session and remove its server audit? Download audit JSON/CSV first if you need to keep it.')) return;
    try {
      if (sessionId) { const response = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' }); if (!response.ok && response.status !== 404) throw new Error('Session could not be ended; audit retained.'); }
      pendingRequest.current = null; setSpeed(null); setSessionId(''); setContext(null); contextRef.current = null;
      setState(null); stateRef.current = null; setHorizonSteps(null); setPhase('IDLE');
      try { sessionStorage.removeItem('sentinel-live-session'); } catch { /* storage unavailable */ }
      notify('Live session ended', 'info');
    } catch (cause) { setError(String(cause)); }
  }, [notify, sessionId]);
  const practice = useCallback((decision: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', subject: Subject, step: number, certId?: string, reason?: string) => {
    setLog(rows => [{ id: `practice-${Date.now()}`, step, utc: new Date().toISOString(), decision, subject, cert_ids: certId ? [certId] : [], kpi_delta: { safe: null, waiting: null, in_transit: null }, source: 'PRACTICE', reason }, ...rows]);
    notify('PRACTICE — not sent to the engine; the recording continues with the original ACCEPT', 'info');
  }, [notify]);
  return <ContextStore.Provider value={{ operationsMode, setOperationsMode, sessionId, world, seed, horizonSteps, phase, context, state, kpiHistory, log, feed, certificates, refusals, toast, result, error, busy, autoRunning: speed != null, start, submit, stepOn, autoRun: setSpeed, fastForward, end, practice, clearToast: () => setToast(null) }}>{children}</ContextStore.Provider>;
}
