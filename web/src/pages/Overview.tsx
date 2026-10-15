import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { actionLabel, orderedCertificates } from '../decisions/Decisions';
import styles from './Pages.module.css';

export default function Overview() {
  const demo = useQuery({ queryKey: ['demo'], queryFn: api.demoState });
  const certs = useQuery({ queryKey: ['certificates'], queryFn: api.certificates });
  const system = useQuery({ queryKey: ['system-status'], queryFn: api.systemStatus });
  const step = demo.data?.step;
  const ordered = orderedCertificates(certs.data?.certificates ?? []);
  const kinds = ['DISPATCH', 'MIGRATION', 'HOLD', 'OVERRIDE'];
  return <div className={styles.page}>
    <header className={styles.heading}><div><p className={styles.eyebrow}>OPERATE / OVERVIEW</p><h1>Incident overview</h1><p>Simulated flood incident · Fort Kochi, Ernakulam district</p></div><Link className={styles.primaryLink} to="/live">Run the live demo</Link></header>
    {(demo.isError || certs.isError || system.isError) && <p role="alert" className={styles.error}>Some data is unavailable. <button type="button" onClick={() => { void demo.refetch(); void certs.refetch(); void system.refetch(); }}>Retry</button></p>}
    <section className={styles.panel}><h2>Population ledger</h2>
      {!step ? <p role="status">Loading incident state…</p> : <div className={styles.kpis}>
        <div><span>WAITING</span><strong>{step.kpis.waiting.toLocaleString('en-IN')}</strong></div>
        <div><span>IN TRANSIT</span><strong>{step.kpis.on_road.toLocaleString('en-IN')}</strong></div>
        <div><span>SAFE IN SHELTER</span><strong>{step.kpis.safe.toLocaleString('en-IN')}</strong></div>
        <div><span>STRANDED EN ROUTE</span><strong>—</strong><small>Not in demo state</small></div>
      </div>}
    </section>
    <div className={styles.columns}>
      <section className={styles.panel}><h2>Shelters</h2>{!step ? <p>Loading shelter ledger…</p> : <ul className={styles.rows}>{step.shelters.map(shelter => <li key={shelter.shelter_id}>
        <b className="mono">{shelter.shelter_id}</b><span>{shelter.name}</span><span className="mono">{shelter.occupied} occupied · {shelter.reserved} reserved / {shelter.capacity_total}</span><span>{shelter.status}</span>
      </li>)}</ul>}</section>
      <section className={styles.panel}><h2>Dispatch gate activity</h2>{certs.isPending ? <p>Loading certificates…</p> : <div className={styles.kpis}>{kinds.map(kind => <div key={kind}><span>{kind}</span><strong>{ordered.filter(cert => cert.kind === kind).length}</strong></div>)}</div>}<p className={styles.note}>Counts are from the current certificate response, not evaluation results.</p></section>
      <section className={styles.panel}><h2>System health</h2>{system.isPending ? <p>Loading system status…</p> : system.data && <><p>{system.data.source} · Broker {system.data.broker.connected ? '● CONNECTED' : '○ OFFLINE'}</p><ul className={styles.rows}>{system.data.devices.map(device => <li key={device.device_id}><span className="mono">{device.device_id}</span><span>{device.kind}</span><span>{device.online ? '● ONLINE' : '○ OFFLINE'}</span></li>)}</ul></>}</section>
    </div>
    <div className={styles.columns}>
      <section className={styles.panel}><h2>Latest certificates</h2>{certs.isPending ? <p>Loading certificates…</p> : <ul className={styles.rows}>{ordered.slice(0, 5).map(cert => <li key={cert.cert_id}><Link className="mono" to={`/decisions?cert=${encodeURIComponent(cert.cert_id)}`}>{cert.cert_id}</Link><span>{cert.kind}</span><span>{actionLabel(cert.chosen.action_key)}</span></li>)}</ul>}</section>
      <section className={styles.panel}><h2>What is real vs simulated</h2><dl className={styles.facts}><dt>REAL</dt><dd>Fort Kochi road topology and the cited NDMA documents.</dd><dt>SIMULATED</dt><dd>Flood hazards, populations, shelters, capacities, closures, travel, and decisions.</dd><dt>MEASURED</dt><dd>Only completed evaluation artifacts listed on Evidence &amp; Results.</dd></dl></section>
    </div>
  </div>;
}
