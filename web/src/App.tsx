import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { NavLink, Route, Routes } from 'react-router-dom';
import { api } from './api';
import LiveOperations from './live/LiveOperations';
import Decisions from './decisions/Decisions';
import Overview from './pages/Overview';
import Evidence from './pages/Evidence';
import System from './pages/System';
import styles from './App.module.css';

const HONESTY = 'REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED';

type Theme = 'Day' | 'Night';

function initialTheme(): Theme {
  try { return localStorage.getItem('sentinel-theme') === 'Night' ? 'Night' : 'Day'; }
  catch { return 'Day'; }
}

export default function App() {
  const demo = useQuery({ queryKey: ['demo'], queryFn: api.demoState });
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [clock, setClock] = useState(() => new Date());
  useEffect(() => {
    const interval = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(interval);
  }, []);
  const toggleTheme = () => {
    const next = theme === 'Day' ? 'Night' : 'Day';
    setTheme(next);
    try { localStorage.setItem('sentinel-theme', next); } catch { /* storage may be unavailable */ }
  };
  const nav = (path: string, text: string) => <NavLink to={path} end={path === '/'}>{text}</NavLink>;
  return <div className="app" data-theme={theme}>
    <header className={styles.header}>
      <div className={styles.mark} aria-label="Sentinel">
        <svg viewBox="0 0 22 22" aria-hidden="true"><rect x="1" y="1" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M5 15L11 6L17 15" fill="none" stroke="currentColor" strokeWidth="2" /></svg>
        SENTINEL
      </div>
      <div className={styles.incident}>{demo.data ? `GUIDED DEMO · t = ${demo.data.step.timestep}` : `INCIDENT — · ${demo.isError ? 'API unavailable' : 'loading demo state'}`}</div>
      <div className={styles.headerRight}>
        <span className={styles.regime}>SIMULATED CONDITIONS</span>
        <time className={styles.incident} dateTime={clock.toISOString()}>{clock.toLocaleTimeString('en-IN', { hour12: false })}</time>
        <button type="button" className={styles.theme} aria-label="Switch Day or Night theme" onClick={toggleTheme}>{theme} theme</button>
        <span className={styles.operator}>Operator · local preview</span>
      </div>
    </header>
    <div className={styles.honesty} role="note">{HONESTY}</div>
    <div className={styles.body}>
      <nav aria-label="Main" className={styles.nav}>
        <span className={styles.navGroup}>OPERATE</span>
        {nav('/', 'Overview')}{nav('/live', 'Live Operations')}
        <span className={styles.navGroup}>VERIFY</span>
        {nav('/decisions', 'Decisions & Certificates')}
        <span className={styles.navGroup}>EVIDENCE</span>
        {nav('/evidence', 'Evidence & Results')}
        <span className={styles.navGroup}>SYSTEM</span>
        {nav('/system', 'System & Hardware')}
      </nav>
      <main className={styles.content}>
        <Routes>
          <Route path="/live" element={<LiveOperations />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/" element={<Overview />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/system" element={<System />} />
        </Routes>
      </main>
    </div>
  </div>;
}
