import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';
import type { DemoState } from '../types';
import { GuidedDemoBar, KpiTiles, PipelineStrip } from './GuidedDemoBar';
import { Legend, OperationsMap } from './OperationsMap';
import { DecisionConsole, EventFeed, GatePanel, ShelterLedger, SideTabs, SuggestionCard, TransitList, type SideTab } from './Panels';
import styles from './Live.module.css';

export default function LiveOperations() {
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

  if (demo.isPending || geometry.isPending) return <section className={styles.loading} aria-label="Loading operations"><h1>Live Operations</h1><div /><div /><div /></section>;
  if (demo.isError || geometry.isError) return <section className={styles.error} role="alert"><h1>Live Operations</h1><p>API unavailable. {String(demo.error ?? geometry.error)}</p><button type="button" onClick={() => { void demo.refetch(); void geometry.refetch(); }}>Retry</button></section>;

  const current = demo.data.step;
  const chosen = selectedCandidate || current.default_selection;
  const stale = import.meta.env.VITE_API_MOCK !== '1' && now - demo.dataUpdatedAt > 5000;
  return <div className={styles.page}>
    <div className={styles.pageHeading}><div><p className={styles.eyebrow}>OPERATIONS / LIVE</p><h1>Live Operations</h1></div><span className={styles.liveBadge}>● {demo.data.source === 'FIXTURE' ? 'SCRIPTED PREVIEW' : 'RECORDED RUN'}</span></div>
    {demo.data.source === 'RECORDED' && <p>Recorded run of the real engine · demo parameters v4-cert-test-v1 (not the evaluated configuration)</p>}
    {stale && <p className={styles.stale}>STALE {Math.round((now - demo.dataUpdatedAt) / 1000)} s · last successful update</p>}
    {actionError && <div className={styles.error} role="alert">{actionError} <button type="button" onClick={() => void demo.refetch()}>Retry</button></div>}
    <div className={styles.timeline}><span className="mono">t = {current.timestep}</span><span>SIMULATED CONDITIONS</span><span>{playing ? 'AUTO PLAY' : 'PAUSED'}</span></div>
    <GuidedDemoBar step={current} count={demo.data.step_count} playing={playing} completed={completed} onPrevious={() => void action('prev')} onNext={() => void action('next')} onReset={() => void action('reset')} onTogglePlay={() => void togglePlay()} />
    {demo.data.seed_note && <p>{demo.data.seed_note}</p>}
    <PipelineStrip current={current.pipeline_stage} />
    <KpiTiles kpis={current.kpis} />
    <div className={styles.operationsGrid}>
      <section className={styles.mapColumn} aria-label="Operations map">
        <OperationsMap geometry={geometry.data} step={current} selectedCandidate={chosen} />
        <p className={styles.mapSummary}>{Object.keys(geometry.data.zones).length} zones · {current.shelters.length} shelters · {current.groups.length} groups in transit · simulated road closures</p>
        <Legend />
        <EventFeed events={current.events} />
      </section>
      <aside className={styles.sidePanel} aria-label="Operational details">
        <SideTabs active={tab} onChange={setTab} />
        {tab === 'Suggestion' && <>
          <SuggestionCard step={current} recorded={demo.data.source === 'RECORDED'} />
          <GatePanel step={current} selected={chosen} onSelect={setSelectedCandidate} />
          <DecisionConsole key={current.step_index} step={current} accepted={accepted} onAccept={() => setAccepted(true)} recorded={demo.data.source === 'RECORDED'} />
        </>}
        {tab === 'In transit' && <TransitList groups={current.groups} />}
        {tab === 'Shelters' && <ShelterLedger shelters={current.shelters} />}
      </aside>
    </div>
  </div>;
}
