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
  try { return localStorage.getItem('sentinel-theme') === 'Day' ? 'Day' : 'Night'; }
  catch { return 'Night'; }
}

const navPaths: Record<string, string> = {
  '/': 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  '/live': 'M3 12h4l3-8 4 16 3-8h4',
  '/decisions': 'M6 3h9l4 4v14H6zM10 11h5M10 15h5M15 3v5h4',
  '/evidence': 'M4 20V4M4 20h17M8 16v-5M13 16V6M18 16V9',
  '/system': 'M5 5h14v10H5zM9 20h6M12 15v5M8 9h8',
  '/simulations': 'M4 4h16v16H4zM10 8l6 4-6 4z',
  '/journey': 'M4 4h6v6H4zM14 14h6v6h-6zM10 7h7v7M7 10v7h7',
};

function NavIcon({ path }: { path: string }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true" className={styles.navIcon}><path d={navPaths[path]} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" /></svg>;
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
  const nav = (path: string, text: string) => <NavLink to={path} end={path === '/'}><NavIcon path={path} /><span>{text}</span></NavLink>;
  return <div className="app" data-theme={theme}>
    <a className={styles.skipLink} href="#console-content">Skip to main content</a>
    <header className={styles.header}>
      <div className={styles.mark} aria-label="Sentinel">
        <svg viewBox="0 0 22 22" aria-hidden="true"><rect x="1" y="1" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" /><path d="M5 15L11 6L17 15" fill="none" stroke="currentColor" strokeWidth="2" /></svg>
        <span>SENTINEL<small>EVACUATION RESEARCH CONSOLE</small></span>
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
    {live.toast && <div className={styles.toast} data-tone={live.toast.tone} role="status"><span>{live.toast.text}</span><button type="button" aria-label="Dismiss notification" onClick={live.clearToast}>×</button></div>}
    <div className={styles.body}>
      <aside className={styles.nav} aria-label="Console navigation">
      <nav aria-label="Main" className={styles.navCore}>
        <span className={styles.navGroup}>OPERATE</span>
        {nav('/', 'Overview')}<NavLink to="/live"><NavIcon path="/live" />Live Operations{live.phase === 'AWAIT_DECISION' && <span aria-hidden="true" className={styles.pendingBadge}>1</span>}</NavLink>
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
      </nav><div className={styles.navFooter}><span>FORT KOCHI · KERALA</span><strong>Local research environment</strong><small>Human authorization required.<br />Simulated conditions throughout.</small></div></aside>
      <main id="console-content" tabIndex={-1} className={styles.content}>
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
  </div>;
}
