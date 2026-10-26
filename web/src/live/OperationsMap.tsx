import { useEffect, useState } from 'react';
import demoFixture from '../../../specs/contracts/demo_steps.json';
import type { DemoStep, MapGeometry } from '../types';
import styles from './Live.module.css';

const routes = demoFixture.routes as Record<string, { label: string; svg_path: string }>;

function plateId(id: string) {
  return id.replace(/^([ZS])(\d+)$/, (_, prefix: string, number: string) => `${prefix}-${number.padStart(2, '0')}`);
}

export function OperationsMap({ geometry, step, selectedCandidate }: { geometry: MapGeometry; step: DemoStep; selectedCandidate: string }) {
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const activeRoute = routes[selectedCandidate]?.svg_path ?? '';
  const activate = (id: string) => setSelectedEntity(id);
  return <div className={styles.mapFrame}>
    <div className={styles.mapCanvas}>
    <svg viewBox={`0 0 ${geometry.W} ${geometry.H}`} width={geometry.W} height={geometry.H} role="img" aria-label="Fort Kochi road topology with simulated hazard and dispatch information">
      <defs>
        <pattern id="grid100" width="89.18" height="89.18" patternUnits="userSpaceOnUse"><path d="M89.18 0L0 0 0 89.18" fill="none" stroke="var(--rule)" strokeWidth=".6" /></pattern>
      </defs>
      <rect width={geometry.W} height={geometry.H} fill="var(--surface)" />
      <rect width={geometry.W} height={geometry.H} fill="url(#grid100)" />
      <g fill="var(--w2)" opacity=".55"><circle cx="760" cy="690" r="150" /><circle cx="150" cy="640" r="90" /><circle cx="470" cy="760" r="70" /></g>
      <circle cx="700" cy="740" r="95" fill="var(--w3)" opacity=".4" />
      <path d={geometry.minor} fill="none" stroke="var(--road)" strokeWidth="5" strokeLinecap="round" />
      <path d={geometry.major} fill="none" stroke="var(--road)" strokeWidth="11" strokeLinecap="round" strokeLinejoin="round" />
      <path d={geometry.major} fill="none" stroke="var(--roadc)" strokeWidth="1" strokeDasharray="6 6" />
      <path d={geometry.closed} fill="none" stroke="var(--ink)" strokeWidth="3" strokeDasharray="5 4" />
      {activeRoute && <><path d={activeRoute} fill="none" stroke="var(--surface)" strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" /><path d={activeRoute} fill="none" stroke="var(--route)" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" /></>}
      {Object.entries(geometry.zones).map(([id, point]) => {
        const [x, y] = point;
        const active = step.highlight_zone === plateId(id) || selectedEntity === id;
        return <g key={id}>
          <rect x={x - 35} y={y - 30} width="70" height="60" fill={active ? 'var(--w2)' : 'var(--w1)'} fillOpacity=".45" stroke="var(--ink)" strokeDasharray="7 5" strokeWidth={active ? 2.5 : 1.5} />
          <circle cx={x} cy={y} r="5" fill="var(--ink)" />
          <text x={x - 32} y={y - 38} className={styles.mapLabel}>ZONE {plateId(id).slice(2)}</text>
        </g>;
      })}
      {Object.entries(geometry.shelters).map(([id, point]) => {
        const [x, y] = point;
        const active = selectedEntity === id || routes[selectedCandidate]?.label.includes(plateId(id));
        const record = step.shelters.find(item => item.shelter_id === plateId(id));
        const restricted = record?.status !== 'OPEN';
        return <g key={id}>
          <circle cx={x} cy={y} r="27" fill="none" stroke="var(--ink2)" strokeDasharray="4 3" />
          <circle cx={x} cy={y} r="19" fill="none" stroke="var(--ink2)" strokeWidth="1.5" />
          {!restricted && <circle cx={x} cy={y} r="13" fill="none" stroke="var(--ok)" strokeWidth="3" />}
          <rect x={x - 7} y={y - 7} width="14" height="14" fill={restricted ? 'var(--surface)' : 'var(--ink)'} stroke="var(--ink)" strokeWidth="2" strokeDasharray={restricted ? '3 2' : undefined} />
          <rect x={x + 12} y={y - 33} width="40" height="20" fill={active ? 'var(--primary)' : 'var(--surface)'} stroke="var(--ink)" />
          <text x={x + 16} y={y - 19} style={{ fill: active ? 'var(--onprimary)' : 'var(--ink)' }} className={styles.mapLabel}>{plateId(id)}</text>
        </g>;
      })}
      {step.moving_group && <g aria-label={step.moving_group.label}><rect x={step.moving_group.x - 10} y={step.moving_group.y - 8} width="20" height="16" fill="var(--primary)" /><path d={`M${step.moving_group.x - 4} ${step.moving_group.y}h8`} stroke="var(--onprimary)" strokeWidth="2" /></g>}
      <g className={styles.mapLabel}><path d="M824 54v-30m0 0-7 11m7-11 7 11" stroke="var(--ink)" strokeWidth="2" fill="none" /><text x="818" y="19">N</text></g>
      <g className={styles.mapLabel}><path d="M740 751h89m-89-5v10m89-10v10" stroke="var(--ink)" strokeWidth="2" /><text x="760" y="744">100 m</text></g>
    </svg>
    {Object.entries(geometry.zones).map(([id, [x, y]]) => <button key={id} type="button" className={styles.mapEntityButton} style={{ left: x - 35, top: y - 30, width: 70, height: 60 }} aria-label={`Select zone ${plateId(id)}`} onClick={() => activate(id)} />)}
    {Object.entries(geometry.shelters).map(([id, [x, y]]) => <button key={id} type="button" className={styles.mapEntityButton} style={{ left: x - 20, top: y - 20, width: 50, height: 50 }} aria-label={`Select shelter ${plateId(id)}`} onClick={() => activate(id)} />)}
    </div>
  </div>;
}

const legend = [
  ['●', 'Feasible dispatch'], ['◩', 'Undecided, blocked'], ['▲', 'Infeasible'], ['□', 'Shelter'], ['▧', 'Zone'], ['┄', 'Closed road'],
];

export function Legend() {
  return <section className={styles.legend} aria-label="Map legend"><strong>LEGEND</strong>
    <ul>{legend.map(([symbol, label]) => <li key={label}><span aria-hidden="true">{symbol}</span>{label}</li>)}</ul>
  </section>;
}

export type SimulationMapStep = {
  chosen_key: string;
  candidates: { action_key: string; label?: string; people: number | null; verdict: string; svg_path: string }[];
  zone_severity: Record<string, number>;
  zone_waiting?: Record<string, number>;
  shelter_severity: Record<string, number>;
  edge_closed_path: string;
  shelters: { id: string; capacity: number; occupied: number; reserved: number }[];
};

/** The same SVG instrument is used for recorded traces and the live command view. */
export function SimulationMap({ geometry, step, label, moving = [], speed = 1, marks = [], previewKey }: { geometry: MapGeometry; step: SimulationMapStep; label: string; speed?: number; moving?: { group_id: string; action_key: string; progress: number; svg_path?: string }[]; marks?: { id: string; action_key: string; decision: string; svg_path?: string }[]; previewKey?: string }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<[number, number]>([0, 0]);
  const [drag, setDrag] = useState<[number, number] | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const active = step.candidates.find(item => item.action_key === (chosen ?? step.chosen_key));
  const maxWaiting = Math.max(1, ...Object.values(step.zone_waiting ?? {}));
  return <div className={styles.instrumentMap}>
    <div className={styles.mapToolbar}><strong>{label}</strong><div><button type="button" aria-label="Zoom in" onClick={() => setZoom(value => Math.min(value * 1.25, 3))}>+</button><button type="button" aria-label="Zoom out" onClick={() => setZoom(value => Math.max(value / 1.25, 1))}>−</button><button type="button" onClick={() => { setZoom(1); setOffset([0, 0]); }}>Map home</button></div></div>
    <svg viewBox={`${offset[0]} ${offset[1]} ${geometry.W / zoom} ${geometry.H / zoom}`} role="img" aria-label={`${label}: real Fort Kochi roads with simulated flood and shelter conditions`}
      onPointerDown={event => { setDrag([event.clientX, event.clientY]); event.currentTarget.setPointerCapture(event.pointerId); }}
      onPointerMove={event => { if (drag) { setOffset(([x, y]) => [x + (drag[0] - event.clientX) / zoom, y + (drag[1] - event.clientY) / zoom]); setDrag([event.clientX, event.clientY]); } }}
      onPointerUp={() => setDrag(null)}>
      <defs><marker id="live-reroute-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="var(--warn)" /></marker></defs>
      <rect width={geometry.W} height={geometry.H} fill="var(--surface)" />
      <path d={geometry.minor} fill="none" stroke="var(--road)" strokeWidth="4" />
      <path d={geometry.major} fill="none" stroke="var(--road)" strokeWidth="8" />
      <path d={step.edge_closed_path} fill="none" stroke="var(--bad)" strokeWidth="4" strokeDasharray="5 5" />
      {Object.entries(geometry.zones).map(([id, [x, y]]) => <g key={id}><circle cx={x} cy={y} r={18 + (step.zone_severity[id] ?? 0) * 32} fill="var(--w3)" opacity={.12 + (step.zone_severity[id] ?? 0) * .3} className={styles.hazardRing} /><circle cx={x} cy={y} r="9" fill="var(--w4)" fillOpacity={step.zone_waiting?.[id] == null ? .65 : .25 + .65 * step.zone_waiting[id] / maxWaiting} /><text x={x + 12} y={y - 12} className={styles.mapLabel}>{id}{step.zone_waiting?.[id] == null ? '' : ` · ${step.zone_waiting[id]} waiting`}</text></g>)}
      {step.candidates.map(item => <path key={item.action_key} d={item.svg_path} fill="none" stroke={item.action_key === (chosen ?? step.chosen_key) ? 'var(--route)' : 'var(--info)'} strokeOpacity={item.action_key === (chosen ?? step.chosen_key) ? 1 : .24} strokeWidth={item.action_key === (chosen ?? step.chosen_key) ? 5 : 2} onClick={() => setChosen(item.action_key)}><title>{item.label ?? item.action_key} · {item.people ?? '—'} people · {item.verdict}</title></path>)}
      {marks.map(mark => { const path = mark.svg_path ?? step.candidates.find(item => item.action_key === mark.action_key)?.svg_path; if (!path) return null; const colour = mark.decision === 'REFUSED' ? 'var(--bad)' : mark.decision === 'DECLINE' ? 'var(--ink2)' : mark.decision === 'OVERRIDE' || mark.decision === 'AUTO_REROUTE' ? 'var(--warn)' : 'var(--ok)'; return <path key={mark.id} data-decision={mark.decision} d={path} fill="none" stroke={colour} strokeWidth="6" strokeDasharray={mark.decision === 'AUTO_REROUTE' ? '12 8' : mark.decision === 'DECLINE' || mark.decision === 'REFUSED' ? '3 8' : undefined} markerEnd={mark.decision === 'AUTO_REROUTE' ? 'url(#live-reroute-arrow)' : undefined} strokeLinecap="round"><title>{mark.action_key} · {mark.decision.toLowerCase()}</title></path>; })}
      {previewKey && <path d={step.candidates.find(item => item.action_key === previewKey)?.svg_path ?? ''} fill="none" stroke="var(--warn)" strokeWidth="7" strokeDasharray="12 7"><title>{previewKey} · override preview</title></path>}
      {active && !reducedMotion && <circle r="7" fill="var(--primary)" stroke="var(--onprimary)" strokeWidth="2"><animateMotion dur={`${2 / speed}s`} repeatCount="indefinite" path={active.svg_path} /></circle>}
      {!reducedMotion && moving.map(group => { const path = group.svg_path ?? step.candidates.find(item => item.action_key === group.action_key)?.svg_path; return path ? <circle key={group.group_id} r="8" fill="var(--warn)" stroke="var(--ink)" strokeWidth="2"><title>{group.group_id} · {group.action_key} · {Math.round(group.progress * 100)}% along route</title><animateMotion path={path} keyPoints={`${group.progress};${Math.min(1, group.progress + .05)}`} keyTimes="0;1" calcMode="linear" dur={`${.8 / speed}s`} fill="freeze" /></circle> : null; })}
      {Object.entries(geometry.shelters).map(([id, [x, y]]) => { const row = step.shelters.find(item => item.id === id); const fraction = row && row.capacity ? Math.min(1, (row.occupied + row.reserved) / row.capacity) : 0; return <g key={id}><rect x={x - 12} y={y - 16} width="24" height="32" fill="var(--surface)" stroke="var(--ink)" /><rect x={x - 10} y={y + 14 - fraction * 28} width="20" height={fraction * 28} fill="var(--ok)" /><text x={x + 15} y={y} className={styles.mapLabel}>{id}</text><title>{id}: {row ? `${row.occupied} occupied, ${row.reserved} reserved, ${row.capacity} capacity` : 'ledger unavailable'}</title></g>; })}
    </svg>
    <div className={styles.mapLegend}>● Simulated zone severity · ▣ Occupied + reserved shelter seats · ┄ Closed graph edge · Bold: {active?.label ?? active?.action_key ?? 'HOLD'}{reducedMotion && moving.map(group => ` · ${group.group_id} ${Math.round(group.progress * 100)}% along ${group.action_key}`)}</div>
    <div className={styles.routePicker} role="group" aria-label="Route details">{step.candidates.map(item => <button type="button" key={item.action_key} onClick={() => setChosen(item.action_key)} aria-pressed={item.action_key === (chosen ?? step.chosen_key)}>{item.label ?? item.action_key} <small>{item.verdict}</small></button>)}</div>
    {active && <div className={styles.routeDrawer} role="status">Route {active.label ?? active.action_key} · {active.people ?? '—'} people{active.people == null && ' (not in context)'} · {active.verdict}</div>}
  </div>;
}
