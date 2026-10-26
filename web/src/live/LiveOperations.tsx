import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { DemoState } from '../types';
import { GuidedDemoBar, PipelineStrip } from './GuidedDemoBar';
import { Legend, SimulationMap, type SimulationMapStep } from './OperationsMap';
import { EventFeed, GatePanel, ShelterLedger, SideTabs, SuggestionCard, TransitList, type SideTab } from './Panels';
import styles from './Live.module.css';
import { CommandCentre, KpiStrip, OperatorBar, DecisionsLog } from './CommandCentre';
import { committedDecisionCount, useSessionStore, type Subject } from './sessionStore';
import LiveSession from './LiveSession';
import DecisionModal, { type Candidate, type Context } from './DecisionModal';
import demoFixture from '../../../specs/contracts/demo_steps.json';

function recordedSubject(key: string, label: string): Subject {
  if (key === 'WAIT') return { action_key: key, kind: 'HOLD', people: null, zone_id: null, shelter_id: null };
  const route = /\b(Z-\d+)\s*→\s*(S-\d+)\b/.exec(label);
  const count = /(?:·|\s)(\d+)\s*(?:people)?\b/.exec(label);
  return { action_key: key, kind: 'DISPATCH', people: count ? Number(count[1]) : null,
    zone_id: route?.[1] ?? null, zone_name: route?.[1] ?? null,
    shelter_id: route?.[2] ?? null, shelter_name: route?.[2] ?? null };
}

export default function LiveOperations() {
  const [networkMode, setNetworkMode] = useState(false);
  const live = useSessionStore();
  const { operationsMode: mode, setOperationsMode: setMode } = live;
  const [practiceChoice, setPracticeChoice] = useState<'OVERRIDE' | 'DECLINE' | null>(null);
  const [practiceLogOpen, setPracticeLogOpen] = useState(false);
  const queryClient = useQueryClient();
  const demo = useQuery({ queryKey: ['demo'], queryFn: api.demoState, refetchInterval: import.meta.env.VITE_API_MOCK === '1' ? false : 3000 });
  const geometry = useQuery({ queryKey: ['geometry'], queryFn: api.geometry, staleTime: Infinity });
  const [selectedCandidate, setSelectedCandidate] = useState('');
  const [tab, setTab] = useState<SideTab>('Suggestion');
  const [playing, setPlaying] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const firstTick = useRef(true);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const update = (next: DemoState) => {
    queryClient.setQueryData(['demo'], next);
    setSelectedCandidate(next.step.default_selection);
    setAccepted(false);
    setActionError(null);
    if (next.step_index === next.step_count - 1 && playing) {
      setPlaying(false);
      setCompleted(true);
    }
  };

  const action = async (kind: 'next' | 'prev' | 'reset', manual = true) => {
    if (manual) { setPlaying(false); setCompleted(false); }
    try {
      const result = kind === 'reset' ? await api.demoStart() : await api.demoStep(kind);
      update(result);
    } catch (error) {
      setPlaying(false);
      setActionError(error instanceof Error ? error.message : 'Demo action failed');
    }
  };

  const togglePlay = async () => {
    if (playing) { setPlaying(false); return; }
    if (completed) {
      await action('reset', false);
      setCompleted(false);
    }
    firstTick.current = true;
    setPlaying(true);
  };

  const step = demo.data?.step;
  const practiceContext = useMemo<Context | null>(() => {
    if (!step) return null;
    const candidate = (row: typeof step.gate.candidates[number]): Candidate => {
      return { action_key: row.id, label: row.label, verdict: row.status, lower: row.lower,
        certified: row.status === 'FEASIBLE' || row.status === 'ALWAYS ALLOWED', comparison: row.meta,
        subject: recordedSubject(row.id, row.label) };
    };
    const candidates = step.gate.candidates.map(candidate);
    const recommendation = candidates.find(row => row.action_key === step.default_selection) ??
      { action_key: 'WAIT', label: 'HOLD', verdict: 'ALWAYS ALLOWED', lower: null, certified: true,
        comparison: '', subject: { action_key: 'WAIT', kind: 'HOLD' as const, people: null, zone_id: null, shelter_id: null } };
    return { certified: { timestep: step.timestep, recommendation, why: step.suggestion.why,
      alternatives: candidates.filter(row => row.action_key !== recommendation.action_key), rechecks: [], note: step.caption } };
  }, [step]);
  useEffect(() => {
    if (!playing || !step) return;
    if (step.step_index === (demo.data?.step_count ?? 6) - 1) {
      setPlaying(false);
      setCompleted(true);
      return;
    }
    if (step.decision_required && !accepted) setAccepted(true);
    const delay = firstTick.current ? 1500 : step.decision_required ? 2200 : 4200;
    firstTick.current = false;
    const timer = window.setTimeout(() => { void action('next', false); }, delay);
    return () => window.clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, step?.step_index]);

  const modeSwitch = <div role="radiogroup" aria-label="Mode" className={styles.modeSwitch}><label className={mode === 'session' ? styles.modeActive : ''}><input type="radio" name="mode" checked={mode === 'session'} onChange={() => setMode('session')} aria-label="Live session" />LIVE ENGINE</label><label className={mode === 'guided' ? styles.modeActive : ''}><input type="radio" name="mode" checked={mode === 'guided'} onChange={() => setMode('guided')} aria-label="Guided demo" />RECORDED WALKTHROUGH</label></div>;
  if (mode === 'session') return <div className={styles.page}>{modeSwitch}{!networkMode && <label><input type="checkbox" checked={false} onChange={() => setNetworkMode(true)} />Two-team network demo</label>}{networkMode ? <LiveSession geometry={geometry.data} initialNetworkDemo /> : <CommandCentre geometry={geometry.data} />}</div>;
  if (demo.isPending || geometry.isPending) return <section className={styles.loading} aria-label="Loading operations"><h1>Live Operations</h1><div /><div /><div /></section>;
  if (demo.isError || geometry.isError) return <section className={styles.error} role="alert"><h1>Live Operations</h1><p>API unavailable. {String(demo.error ?? geometry.error)}</p><button type="button" onClick={() => { void demo.refetch(); void geometry.refetch(); }}>Retry</button></section>;

  const current = demo.data.step;
  const practiceSubject: Subject = recordedSubject(current.default_selection, current.gate.candidates.find(row => row.id === current.default_selection)?.label ?? current.suggestion.title);
  const practiceResult = live.log.find(row => row.source === 'PRACTICE' && row.step === current.timestep);
  const chosen = selectedCandidate || current.default_selection;
  const recordedRoutes = demoFixture.routes as Record<string, { svg_path: string }>;
  const recordedMap: SimulationMapStep = {
    chosen_key: chosen,
    candidates: current.gate.candidates.filter(item => recordedRoutes[item.id]).map(item => { const subject = recordedSubject(item.id, item.label); return { action_key: item.id, label: subject.zone_name && subject.shelter_name ? `${subject.zone_name} → ${subject.shelter_name}` : item.label, people: subject.people, verdict: item.status, svg_path: recordedRoutes[item.id].svg_path }; }),
    zone_severity: {}, shelter_severity: {}, edge_closed_path: geometry.data.closed,
    shelters: current.shelters.map(item => ({ id: item.shelter_id.replace('-', ''), capacity: item.capacity_total, occupied: item.occupied, reserved: item.reserved })),
  };
  const stale = import.meta.env.VITE_API_MOCK !== '1' && now - demo.dataUpdatedAt > 5000;
  return <div className={styles.page}>
    {modeSwitch}
    <div className={styles.pageHeading}><div><p className={styles.eyebrow}>OPERATIONS / LIVE</p><h1>Live Operations</h1></div><span className={styles.liveBadge}>● {demo.data.source === 'FIXTURE' ? 'SCRIPTED PREVIEW' : 'RECORDED RUN'}</span></div>
    {demo.data.source === 'RECORDED' && <p>Recorded run of the real engine · demo parameters v4-cert-test-v1 (not the evaluated configuration)</p>}
    {stale && <p className={styles.stale}>STALE {Math.round((now - demo.dataUpdatedAt) / 1000)} s · last successful update</p>}
    {actionError && <div className={styles.error} role="alert">{actionError} <button type="button" onClick={() => void demo.refetch()}>Retry</button></div>}
    <div className={styles.timeline}><span className="mono">t = {current.timestep}</span><span>SIMULATED CONDITIONS</span><span>{playing ? 'AUTO PLAY' : 'PAUSED'}</span></div>
    <GuidedDemoBar step={current} count={demo.data.step_count} playing={playing} completed={completed} onPrevious={() => void action('prev')} onNext={() => void action('next')} onReset={() => void action('reset')} onTogglePlay={() => void togglePlay()} />
    {demo.data.seed_note && <p>{demo.data.seed_note}</p>}
    <PipelineStrip current={current.pipeline_stage} />
    <OperatorBar step={current.timestep} subject={current.suggestion.title.replace(/^HOLD (Zone \d+)/, '$1 · HOLD')} verdict={current.kind} phase={practiceResult ? 'RESULT' : 'AWAIT_DECISION'} result={practiceResult} busy={false} onAccept={() => { live.practice('ACCEPT', practiceSubject, current.timestep, current.certificate_id ?? undefined); setAccepted(true); }} onOverride={() => setPracticeChoice('OVERRIDE')} onDecline={() => setPracticeChoice('DECLINE')} onStep={() => void action('next')} />
    {practiceChoice && practiceContext && <><p className={styles.notice}>PRACTICE — not sent to the engine; the recording continues with the original ACCEPT</p><button type="button" onClick={() => { setPracticeChoice(null); setMode('session'); }}>Try this step in the live engine</button><DecisionModal context={practiceContext} result={null} refusal={null} busy={false} session="" safeDelta={null} initialChoice={practiceChoice === 'DECLINE' ? 'REJECT' : 'OVERRIDE'} onClose={() => setPracticeChoice(null)} onNext={() => void action('next')} onSubmit={(choice, selected, reason) => { const chosen = practiceContext.certified.alternatives.find(item => item.action_key === selected)?.subject ?? practiceSubject; live.practice(choice === 'REJECT' ? 'DECLINE' : choice, choice === 'OVERRIDE' ? chosen : practiceSubject, current.timestep, undefined, reason); setAccepted(true); setPracticeChoice(null); }} /></>}
    <KpiStrip values={{ waiting: current.kpis.waiting, in_transit: current.kpis.on_road, safe: current.kpis.safe, certificates_issued: current.kpis.certificates_issued, decisions: committedDecisionCount(live.log, 'PRACTICE') }} history={[{ waiting: current.kpis.waiting, in_transit: current.kpis.on_road, safe: current.kpis.safe, certificates_issued: current.kpis.certificates_issued }]} />
    <div className={styles.operationsGrid}>
      <section className={styles.mapColumn} aria-label="Operations map">
        <SimulationMap geometry={geometry.data} step={recordedMap} label="Recorded walkthrough" marks={live.log.filter(row => row.source === 'PRACTICE' && row.step === current.timestep).map(row => ({ id: row.id, action_key: row.subject.action_key, decision: row.decision }))} />
        <p className={styles.mapSummary}>{Object.keys(geometry.data.zones).length} zones · {current.shelters.length} shelters · {current.groups.length} groups in transit · simulated road closures</p>
        <Legend />
        <EventFeed events={current.events} />
      </section>
      <aside className={styles.sidePanel} aria-label="Operational details">
        <SideTabs active={tab} onChange={setTab} />
        {tab === 'Suggestion' && <>
          <SuggestionCard step={current} recorded={demo.data.source === 'RECORDED'} />
          <GatePanel step={current} selected={chosen} onSelect={setSelectedCandidate} />
          {live.log.some(row => row.source === 'PRACTICE') && <><button type="button" onClick={() => setPracticeLogOpen(value => !value)}>Decisions log</button>{practiceLogOpen && <DecisionsLog entries={live.log.filter(row => row.source === 'PRACTICE')} sessionId={live.sessionId} />}</>}
        </>}
        {tab === 'In transit' && <TransitList groups={current.groups} />}
        {tab === 'Shelters' && <ShelterLedger shelters={current.shelters} />}
      </aside>
    </div>
  </div>;
}
