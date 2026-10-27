import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import styles from './Pages.module.css';

const pipeline = [
  ['SENSE', 'Sensors and simulator state'],
  ['FORECAST', 'Sampled hazard futures'],
  ['SUGGEST', 'Planner ranks dispatch options'],
  ['CERTIFY', 'Statistical lower-bound check'],
  ['DECIDE', 'Operator accepts, overrides, or rejects'],
  ['COMMIT', 'Ledger, certificate, then commands'],
];

export default function System() {
  const status = useQuery({ queryKey: ['system-status'], queryFn: api.systemStatus });
  const acks = useQuery({ queryKey: ['system-acks'], queryFn: api.systemAcks });
  const devices = status.data?.devices ?? [];
  return <div className={styles.page}>
    <header className={styles.heading}><div><p className={styles.eyebrow}>SYSTEM / HARDWARE</p><h1>System &amp; Hardware</h1><p>Local broker, simulated sensors, and certificate-gated actuation.</p></div><span className={styles.sourceBadge}>SIMULATED HIL · NO PHYSICAL BENCH CLAIM</span></header>
    {(status.isError || acks.isError) && <p role="alert" className={styles.error}>System data unavailable. <button type="button" onClick={() => { void status.refetch(); void acks.refetch(); }}>Retry</button></p>}
    {status.isPending && <p role="status">Loading system status…</p>}
    {status.data && <p className={styles.sourceBadge}>{status.data.source} · Broker {status.data.broker.connected ? '● CONNECTED' : '○ OFFLINE'}{status.data.broker.host && ` · ${status.data.broker.host}`}</p>}
    <div className={styles.columns}>
      <section className={styles.panel}><h2>Devices</h2><div className={styles.tableScroll} role="region" tabIndex={0} aria-label="Devices table"><table className={styles.table}>
        <thead><tr><th scope="col">Device ID</th><th scope="col">Kind</th><th scope="col">State</th><th scope="col">Last seen</th><th scope="col">Age</th></tr></thead>
        <tbody>{devices.map(device => <tr key={device.device_id}><th scope="row" className="mono">{device.device_id}</th><td>{device.kind}</td><td>{device.online ? '● ONLINE' : '○ OFFLINE'}</td><td>{device.last_seen_utc ?? '-'}{!device.last_seen_utc && <small className={styles.note}>No reading yet</small>}</td><td>{device.age_s == null ? '- No reading yet' : `${device.age_s.toFixed(0)} s`}</td></tr>)}</tbody>
      </table></div></section>
      <section className={styles.panel}><h2>MQTT topics</h2><ul className={styles.rows}>{status.data?.topics.map(topic => <li key={topic} className={styles.source}>{topic}</li>)}</ul></section>
    </div>
    <div className={styles.columns}>
      <section className={styles.panel}><h2>Actuator command log</h2>{acks.isPending ? <p>Loading ACKs…</p> : !acks.data?.items.length ? <p>No commands yet</p> : <ul className={styles.rows}>{[...acks.data.items].sort((a, b) => b.ts_utc.localeCompare(a.ts_utc)).slice(0, 20).map((ack, index) => <li key={`${ack.device_id}-${ack.cert_id}-${index}`}><span>{ack.accepted ? '● ACCEPTED' : '▲ REJECTED'}</span><span className="mono">{ack.cert_id}</span><span>{ack.device_id} · {ack.reason}</span></li>)}</ul>}</section>
      <section className={styles.panel}><h2>HIL latency</h2>{status.data?.latency.p95_ms == null ? <p>- No physical bench result yet. {status.data?.latency.source_path ?? 'Phase 28 hardware has not been assembled.'}</p> : <p className="mono">p50 {status.data.latency.p50_ms?.toFixed(0) ?? '-'} ms · p95 {status.data.latency.p95_ms.toFixed(0)} ms</p>}</section>
    </div>
    <section className={styles.panel}><h2>How a suggestion becomes a dispatch</h2><ol className={styles.pipeline}>{pipeline.map(([name, description]) => <li key={name}><b>{name}</b><span>{description}</span></li>)}</ol></section>
    <section className={styles.panel}><h2>HIL bench path</h2><svg viewBox="0 0 900 140" role="img" aria-label="Console to certificate gate to local broker to simulated device acknowledgement" style={{ width: '100%' }}><path d="M140 70H760" stroke="var(--info)" strokeWidth="3" fill="none" markerEnd="url(#arrow)" /><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="var(--info)" /></marker></defs>{[['Console', 30], ['Certificate gate', 250], ['Local broker', 480], ['Device ACK', 700]].map(([label, x]) => <g key={label}><rect x={Number(x)} y="38" width="150" height="64" fill="var(--sunk)" stroke="var(--ink)" /><text x={Number(x) + 10} y="76" fill="var(--ink)" fontSize="15">{label}</text></g>)}</svg><p className={styles.note}>Device and broker state above is from the current system response. No physical bench latency is claimed without a measured artifact.</p></section>
  </div>;
}
