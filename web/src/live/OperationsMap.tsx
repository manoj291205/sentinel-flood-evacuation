import { useState } from 'react';
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
