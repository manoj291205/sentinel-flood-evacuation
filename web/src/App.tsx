import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { NavLink, Route, Routes } from 'react-router-dom';
import { api } from './api';
import LiveOperations from './live/LiveOperations';
import Decisions from './decisions/Decisions';
import Overview from './pages/Overview';
import Evidence from './pages/Evidence';
import System from './pages/System';
import Simulations from './sims/Simulations';
import Journey from './pages/Journey';
import styles from './App.module.css';
import { committedDecisionCount, useSessionStore } from './live/sessionStore';

const HONESTY = 'REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED';

type Theme = 'Day' | 'Night';

function initialTheme(): Theme {
  try { return localStorage.getItem('sentinel-theme') === 'Night' ? 'Night' : 'Day'; }
  catch { return 'Day'; }
}

export default function App() {
  const live = useSessionStore();
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
      <div className={styles.incident}>{live.operationsMode === 'guided' ? (demo.data ? `RECORDED WALKTHROUGH · t = ${demo.data.step.timestep}` : `RECORDED WALKTHROUGH · ${demo.isError ? 'API unavailable' : 'loading'}`) : live.sessionId ? `LIVE SESSION · ${live.world} · step ${live.state?.current_timestep ?? live.context?.certified.timestep ?? '—'}/${live.horizonSteps ?? '—'} · ${committedDecisionCount(live.log)} decisions · ${live.phase === 'AWAIT_DECISION' ? 1 : 0} pending` : 'LIVE ENGINE · ready to start'}</div>
      <div className={styles.headerRight}>
        <span className={styles.regime}>SIMULATED CONDITIONS</span>
        <time className={styles.incident} dateTime={clock.toISOString()}>{clock.toLocaleTimeString('en-IN', { hour12: false })}</time>
        <button type="button" className={styles.theme} aria-label="Switch Day or Night theme" onClick={toggleTheme}>{theme} theme</button>
        <span className={styles.operator}>Operator · local preview</span>
      </div>
    </header>
    <section aria-label="Simulation honesty"><div className={styles.honesty} role="note">{HONESTY}</div></section>
    <div className={styles.body}>
      <aside className={styles.nav} aria-label="Console navigation">
      <nav aria-label="Main" className={styles.navCore}>
        <span className={styles.navGroup}>OPERATE</span>
        {nav('/', 'Overview')}<NavLink to="/live">Live Operations {live.phase === 'AWAIT_DECISION' && <span aria-hidden="true" className={styles.pendingBadge}>1</span>}</NavLink>
        <span className={styles.navGroup}>VERIFY</span>
        {nav('/decisions', 'Decisions & Certificates')}
        <span className={styles.navGroup}>EVIDENCE</span>
        {nav('/evidence', 'Evidence & Results')}
        <span className={styles.navGroup}>SYSTEM</span>
        {nav('/system', 'System & Hardware')}
      </nav>
      <nav aria-label="Showcase" className={styles.navCore}>
        <span className={styles.navGroup}>OPERATE / REPLAY</span>
        {nav('/simulations', 'Simulations')}
        <span className={styles.navGroup}>ABOUT</span>
        {nav('/journey', 'How it was built')}
      </nav></aside>
      <main className={styles.content}>
        <Routes>
          <Route path="/live" element={<LiveOperations />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/" element={<Overview />} />
          <Route path="/evidence" element={<Evidence />} />
          <Route path="/system" element={<System />} />
          <Route path="/simulations" element={<Simulations />} />
          <Route path="/journey" element={<Journey />} />
        </Routes>
      </main>
    </div>
    {live.toast && <div className={styles.toast} data-tone={live.toast.tone} role="status"><span>{live.toast.text}</span><button type="button" aria-label="Dismiss notification" onClick={live.clearToast}>×</button></div>}
  </div>;
}
