import type { DemoStep, GateCandidate } from '../types';
import styles from './Live.module.css';

export type SideTab = 'Suggestion' | 'In transit' | 'Shelters';

export function SideTabs({ active, onChange }: { active: SideTab; onChange: (tab: SideTab) => void }) {
  return <div className={styles.tabs} role="tablist" aria-label="Operations details">
    {(['Suggestion', 'In transit', 'Shelters'] as const).map(tab => <button key={tab} type="button" role="tab" aria-selected={active === tab} className={active === tab ? styles.activeTab : ''} onClick={() => onChange(tab)}>{tab}</button>)}
  </div>;
}

export function SuggestionCard({ step, recorded = false }: { step: DemoStep; recorded?: boolean }) {
  return <section className={styles.card} aria-label="Suggestion">
    <div className={styles.cardEyebrow}>{step.kind} · {recorded ? 'RECORDED RUN' : 'SCRIPTED PREVIEW'}</div>
    <h2>{step.suggestion.title}</h2>
    <p className={styles.muted}>{step.suggestion.meta}</p>
    <h3>WHY THIS SUGGESTION</h3>
    <ol className={styles.whyList}>{step.suggestion.why.map(reason => <li key={reason}>{reason}</li>)}</ol>
    {step.auto_note && <p className={styles.notice}>{step.auto_note}</p>}
  </section>;
}

function gateWord(status: GateCandidate['status']) {
  if (status === 'FEASIBLE') return '● FEASIBLE';
  if (status === 'UNDECIDED') return '◩ UNDECIDED';
  if (status === 'INFEASIBLE') return '▲ INFEASIBLE';
  return '□ ALWAYS ALLOWED';
}

export function GatePanel({ step, selected, onSelect }: { step: DemoStep; selected: string; onSelect: (id: string) => void }) {
  // The recorded demo contract supplies its threshold only in gate metadata.
  const thresholdText = /1\s*[−-]\s*ε\s*=\s*(\S+)/.exec(step.gate.meta)?.[1];
  const threshold = thresholdText === undefined ? NaN : Number(thresholdText);
  const hasThreshold = Number.isFinite(threshold) && threshold >= 0 && threshold <= 1;
  return <section className={styles.card} aria-label="Dispatch Gate">
    <div className={styles.cardEyebrow}>DISPATCH GATE</div>
    <h2>Candidate certification</h2>
    <p className={styles.muted}>{step.gate.meta}</p>
    <p className={styles.muted}>Interval scale 0–1{hasThreshold ? ' · marker from recorded threshold' : ' · threshold not provided in this context'}</p>
    <div className={styles.gateRows}>
      {step.gate.candidates.map(candidate => <button key={candidate.id} type="button" className={`${styles.gateRow} ${selected === candidate.id ? styles.gateSelected : ''}`} aria-label={`${candidate.label} ${candidate.status}`} aria-pressed={selected === candidate.id} onClick={() => onSelect(candidate.id)}>
        <span className={styles.gateMain}><strong>{candidate.label}</strong><small className="mono">{candidate.lower === null ? '—' : candidate.lower.toFixed(3)}{candidate.upper === null ? '' : `–${candidate.upper.toFixed(3)}`}</small></span>
        <span className={styles.interval} aria-hidden="true">{hasThreshold && <i className={styles.threshold} data-threshold={threshold} style={{ left: `${threshold * 100}%` }} />}{candidate.lower !== null && candidate.upper !== null && <i className={styles.intervalBand} style={{ left: `${Math.max(0, Math.min(1, candidate.lower)) * 100}%`, width: `${Math.max(0, Math.min(1, candidate.upper) - Math.max(0, candidate.lower)) * 100}%` }} />}</span>
        <span className={styles.gateFoot}><b data-status={candidate.status}>{gateWord(candidate.status)}</b><small>{candidate.meta}</small></span>
      </button>)}
    </div>
    {step.kind === 'HOLD' && <p className={styles.warning}>No certified dispatch — HOLD and escalate.</p>}
  </section>;
}

export function TransitList({ groups }: { groups: DemoStep['groups'] }) {
  return <section className={styles.card}><h2>Groups in transit</h2>
    {groups.length ? <ul className={styles.detailList}>{groups.map(group => <li key={group.group_id}>
      <strong className="mono">{group.group_id}</strong><span>{group.route}</span><small>{group.meta}</small><b data-tone={group.tone}>● {group.state}</b>
    </li>)}</ul> : <p className={styles.muted}>No groups in transit.</p>}
  </section>;
}

export function ShelterLedger({ shelters }: { shelters: DemoStep['shelters'] }) {
  return <section className={styles.card}><h2>Shelter ledger</h2>
    <ul className={styles.detailList}>{shelters.map(shelter => <li key={shelter.shelter_id}>
      <strong className="mono">{shelter.shelter_id} · {shelter.name}</strong>
      <span>{shelter.occupied} occupied · {shelter.reserved} reserved / {shelter.capacity_total} seats</span>
      <progress max={shelter.capacity_total} value={shelter.occupied + shelter.reserved} aria-label={`${shelter.shelter_id} occupied and reserved seats`} />
      <b data-tone={shelter.status === 'OPEN' ? 'ok' : 'warn'}>□ {shelter.status}</b>
    </li>)}</ul>
  </section>;
}

export function EventFeed({ events }: { events: DemoStep['events'] }) {
  return <section className={styles.events}><h2>Event feed</h2>
    <ul>{events.slice(-7).reverse().map((event, index) => <li key={`${event.timestep}-${event.text}-${index}`}><span data-kind={event.kind}>{event.kind === 'ok' ? '●' : event.kind === 'warn' ? '◆' : '■'}</span><span className="mono">t+{event.timestep}</span><span>{event.text}</span></li>)}</ul>
  </section>;
}
