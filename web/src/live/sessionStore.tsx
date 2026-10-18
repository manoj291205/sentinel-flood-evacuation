import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Context, Decision, Refusal } from './DecisionModal';

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
  current_timestep?: number; terminal?: boolean; people_stranded?: number | null; kpis: Kpis;
  zones?: { zone_id: string; population_remaining: number; flood_severity_current: number }[];
  shelters?: { shelter_id: string; capacity_total: number; occupancy_current: number; capacity_reserved: number; capacity_available?: number; flood_severity_current: number }[];
  route_rows?: { Source: string; Destination: string; Status: string }[];
  transit_positions?: { group_id: string; source_zone_id: string; destination_shelter_id: string; progress: number }[];
};
export type OperatorEntry = {
  id: string; step: number; utc: string;
  decision: 'ACCEPT' | 'OVERRIDE' | 'DECLINE' | 'REFUSED' | 'AUTO_REROUTE' | 'FAST_FORWARD_ACCEPT';
  subject: Subject; alternative?: Subject; reason_code?: string; reason?: string;
  cert_ids: string[]; kpi_delta: { safe: number | null; waiting: number | null; in_transit: number | null };
  source: 'LIVE' | 'PRACTICE';
};
export type FeedItem = { id: string; text: string; tone: 'ok' | 'warn' | 'danger' | 'info'; href?: string };
export type Toast = { id: number; text: string; tone: FeedItem['tone'] };
type Message = { seq?: number; type: 'decision' | 'certificate' | 'recheck' | 'event' | 'refusal' | 'state'; payload: Record<string, unknown> };

export function subjectOf(candidate: { action_key: string; subject?: Subject }): Subject {
  return candidate.subject ?? { action_key: candidate.action_key, kind: candidate.action_key === 'WAIT' ? 'HOLD' : 'DISPATCH', people: null, zone_id: null, shelter_id: null };
}
export function subjectSentence(subject: Subject): string {
  if (subject.kind === 'HOLD') return 'HOLD: no dispatch this step';
  const people = subject.people == null ? '— people' : `${subject.people} people`;
  const zone = subject.zone_name ?? subject.zone_id ?? '—';
  const shelter = subject.shelter_name ?? subject.shelter_id ?? '—';
  return `Dispatch ${people} · ${zone} → ${shelter} · via ${subject.route_label ?? '—'} · ETA ${subject.eta_minutes == null ? '—' : `${subject.eta_minutes} min`}`;
}
function restoredEntry(cert: Record<string, unknown>): OperatorEntry {
  const chosen = cert.chosen as { action_key?: string; people?: number } | undefined;
  const operator = cert.operator as { decision?: string; reason?: string } | undefined;
  const key = chosen?.action_key ?? 'WAIT';
  const [zone, shelter] = key.split('->');
  const decision = cert.kind === 'MIGRATION' ? 'AUTO_REROUTE' : operator?.decision === 'REJECT' ? 'DECLINE' : operator?.decision === 'OVERRIDE' ? 'OVERRIDE' : 'ACCEPT';
  return { id: `restored-${String(cert.cert_id)}`, step: Number(cert.timestep ?? 0), utc: String(cert.utc ?? ''), decision,
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
    const error = new Error(data.detail ?? `Request failed (${response.status})`) as Error & { status: number; refusal?: Refusal };
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
  sessionId: string; world: string; seed: number; horizonSteps: number | null; phase: 'IDLE' | 'STARTING' | 'AWAIT_DECISION' | 'SUBMITTING' | 'RESULT' | 'DONE' | 'ENDED';
  context: Context | null; state: LiveState | null; kpiHistory: Kpis[]; log: OperatorEntry[];
  feed: FeedItem[]; certificates: Record<string, unknown>[]; refusals: Refusal[]; toast: Toast | null;
  result: Decision | null; error: string; busy: boolean; autoRunning: boolean;
  start: (world: string, seed: number) => Promise<void>;
  submit: (choice: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', alt?: string, code?: string, text?: string) => Promise<void>;
  stepOn: () => Promise<void>; autoRun: (speed: number | null) => void;
  fastForward: (n: number) => Promise<void>; end: () => void;
  practice: (decision: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', subject: Subject, step: number, certId?: string, reason?: string) => void;
  clearToast: () => void;
};
const emptySession: SessionStore = {
  sessionId: '', world: 'v4-medium-dt2-v1', seed: 620003, horizonSteps: null, phase: 'IDLE', context: null, state: null,
  kpiHistory: [], log: [], feed: [], certificates: [], refusals: [], toast: null, result: null,
  error: '', busy: false, autoRunning: false,
  start: async () => {}, submit: async () => {}, stepOn: async () => {}, autoRun: () => {},
  fastForward: async () => {}, end: () => {}, practice: () => {}, clearToast: () => {},
};
const ContextStore = createContext<SessionStore>(emptySession);
export function useSessionStore(): SessionStore {
  return useContext(ContextStore);
}
export function SessionProvider({ children }: { children: ReactNode }) {
  const initial = useRef(initialSession());
  const [sessionId, setSessionId] = useState(initial.current.sessionId);
  const [world, setWorld] = useState(initial.current.world);
  const [seed, setSeed] = useState(initial.current.seed);
  const [horizonSteps, setHorizonSteps] = useState<number | null>(initial.current.horizonSteps ?? null);
  const [phase, setPhase] = useState<SessionStore['phase']>('IDLE');
  const [context, setContext] = useState<Context | null>(null);
  const [state, setState] = useState<LiveState | null>(null);
  const stateRef = useRef<LiveState | null>(null);
  const contextRef = useRef<Context | null>(null);
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
      const next = await request<Context>(`/api/sessions/${id}/context?include_subject=true`);
      contextRef.current = next; setContext(next); setPhase('AWAIT_DECISION'); setResult(null);
      const [snapshot, issued] = await Promise.all([
        request<LiveState>(`/api/sessions/${id}/state`),
        request<{ certificates: Record<string, unknown>[] }>(`/api/sessions/${id}/certificates`),
      ]);
      setSnapshot(snapshot); addCertificates(issued.certificates);
      for (const row of next.certified.rechecks.filter(item => item.action === 'MIGRATE')) {
        const cert = issued.certificates.find(item => item.cert_id === row.cert_id);
        const base = cert ? restoredEntry(cert) : restoredEntry({ cert_id: row.cert_id ?? row.group_id, timestep: next.certified.timestep,
          chosen: { action_key: row.route, people: null }, kind: 'MIGRATION' });
        const reroute: OperatorEntry = { ...base, decision: 'AUTO_REROUTE', reason: `Group ${row.group_id} re-routed automatically` };
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
      request<{ certificates: Record<string, unknown>[] }>(`/api/sessions/${sessionId}/certificates`),
      request<{ audit?: Record<string, unknown>[]; refusals?: Refusal[] }>(`/api/sessions/${sessionId}/audit`),
    ]).then(async ([snapshot, timeline, certs, audit]) => {
      if (cancelled) return;
      setSnapshot(snapshot); setCertificates(certs.certificates); setRefusals(audit.refusals ?? []);
      setLog(previous => previous.length ? previous : [
        ...certs.certificates.map(restoredEntry),
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
    if (!sessionId || !pending || busy) return;
    setBusy(true); setError(''); setPhase('SUBMITTING');
    const candidate = choice === 'OVERRIDE' ? pending.alternatives.find(item => item.action_key === alt) : pending.recommendation;
    const subject = subjectOf(candidate ?? pending.recommendation);
    const before = stateRef.current?.kpis;
    try {
      const response = await request<Decision & { state: LiveState }>(`/api/sessions/${sessionId}/decisions`, {
        decision: choice === 'DECLINE' ? 'REJECT' : choice,
        selected_action: choice === 'OVERRIDE' ? alt : undefined,
        reason: choice === 'ACCEPT' ? '' : `${code}: ${text}`, evidence,
      });
      const next = response.state ?? await request<LiveState>(`/api/sessions/${sessionId}/state`);
      const delta = { safe: next.kpis.safe - (before?.safe ?? next.kpis.safe), waiting: next.kpis.waiting - (before?.waiting ?? next.kpis.waiting), in_transit: next.kpis.in_transit - (before?.in_transit ?? next.kpis.in_transit) };
      const certIds = (response.certificates ?? []).map(item => item.cert_id);
      const loggedDecision = choice === 'ACCEPT' && fastForwarding.current ? 'FAST_FORWARD_ACCEPT' : choice;
      const entry: OperatorEntry = { id: `${sessionId}-${pending.timestep}-${Date.now()}`, step: pending.timestep, utc: new Date().toISOString(), decision: loggedDecision,
        subject, alternative: choice === 'OVERRIDE' ? subjectOf(pending.recommendation) : undefined,
        reason_code: code || undefined, reason: text || undefined, cert_ids: certIds, kpi_delta: delta, source: 'LIVE' };
      setLog(rows => [entry, ...rows]); setSnapshot(next); addCertificates(response.certificates ?? []); setResult(response); setPhase('RESULT');
      setFeed(rows => [{ id: entry.id, text: `${loggedDecision} recorded · ${subjectSentence(subject)}${certIds.length ? ` · ${certIds.join(', ')}` : ''}`, tone: 'ok', href: certIds[0] ? `/decisions?session=${sessionId}&cert=${certIds[0]}` : undefined }, ...rows]);
      for (const row of response.rechecks ?? []) if (row.action === 'MIGRATE') {
        setLog(rows => [{ ...entry, id: `${entry.id}-${row.group_id}`, decision: 'AUTO_REROUTE', cert_ids: row.cert_id ? [row.cert_id] : [], reason: `Group ${row.group_id} re-routed automatically` }, ...rows]);
      }
      notify(`${choice === 'DECLINE' ? 'Decline' : choice === 'OVERRIDE' ? 'Override' : 'Accept'} recorded${certIds.length ? ` · ${certIds.join(', ')} issued` : ''}`, 'ok');
    } catch (cause) {
      const refusal = (cause as Error & { refusal?: Refusal }).refusal;
      if (refusal) {
        setRefusals(rows => [...rows, refusal]);
        const entry: OperatorEntry = { id: `${sessionId}-refused-${Date.now()}`, step: pending.timestep, utc: new Date().toISOString(), decision: 'REFUSED', subject, cert_ids: [], kpi_delta: { safe: 0, waiting: 0, in_transit: 0 }, source: 'LIVE', reason_code: code, reason: text };
        setLog(rows => [entry, ...rows]); setFeed(rows => [toFeedItem({ type: 'refusal', payload: refusal as unknown as Record<string, unknown> }, sessionId), ...rows]);
        notify(`Gate refused ${alt} · not certified`, 'danger'); setPhase('AWAIT_DECISION');
      } else { setError(String(cause)); setPhase('AWAIT_DECISION'); }
    } finally { setBusy(false); }
  }, [sessionId, busy, setSnapshot, addCertificates, notify]);
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
        await submit('ACCEPT');
        await stepOn();
      }
    } finally { fastForwarding.current = false; }
  }, [submit, stepOn]);
  useEffect(() => {
    if (speed == null || phase !== 'RESULT') return;
    const timer = window.setTimeout(() => void stepOn(), 1500 / speed);
    return () => window.clearTimeout(timer);
  }, [speed, phase, stepOn]);
  const end = useCallback(() => { setSpeed(null); setSessionId(''); setContext(null); contextRef.current = null; setState(null); stateRef.current = null; setHorizonSteps(null); setPhase('IDLE'); try { sessionStorage.removeItem('sentinel-live-session'); } catch { /* storage unavailable */ } notify('Live session ended', 'info'); }, [notify]);
  const practice = useCallback((decision: 'ACCEPT' | 'OVERRIDE' | 'DECLINE', subject: Subject, step: number, certId?: string, reason?: string) => {
    setLog(rows => [{ id: `practice-${Date.now()}`, step, utc: new Date().toISOString(), decision, subject, cert_ids: certId ? [certId] : [], kpi_delta: { safe: null, waiting: null, in_transit: null }, source: 'PRACTICE', reason }, ...rows]);
    notify('PRACTICE — not sent to the engine; the recording continues with the original ACCEPT', 'info');
  }, [notify]);
  return <ContextStore.Provider value={{ sessionId, world, seed, horizonSteps, phase, context, state, kpiHistory, log, feed, certificates, refusals, toast, result, error, busy, autoRunning: speed != null, start, submit, stepOn, autoRun: setSpeed, fastForward, end, practice, clearToast: () => setToast(null) }}>{children}</ContextStore.Provider>;
}
