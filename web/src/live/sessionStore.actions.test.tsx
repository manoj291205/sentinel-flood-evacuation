import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SessionProvider, useSessionStore } from './sessionStore';

const subject = (key: string) => ({ action_key: key, kind: 'DISPATCH' as const, people: 20, zone_id: key.split('->')[0], shelter_id: key.split('->')[1], route_label: null, eta_minutes: null });
const context = { certified: { timestep: 1, recommendation: { action_key: 'Z1->S2', label: 'Z1 → S2', verdict: 'FEASIBLE', lower: .94, certified: true, comparison: '', subject: subject('Z1->S2') },
  alternatives: [{ action_key: 'Z2->S2', label: 'Z2 → S2', verdict: 'FEASIBLE', lower: .92, certified: true, comparison: '', subject: subject('Z2->S2') }, { action_key: 'Z3->S3', label: 'Z3 → S3', verdict: 'UNDECIDED', lower: .5, certified: false, comparison: '', subject: subject('Z3->S3') }],
  why: [], rechecks: [], note: '' } };
const initialState = { current_timestep: 1, people_stranded: 0, kpis: { waiting: 100, in_transit: 0, safe: 0, certificates_issued: 0 }, zones: [], shelters: [] };
const finalState = { ...initialState, current_timestep: 2, kpis: { waiting: 80, in_transit: 10, safe: 10, certificates_issued: 1 } };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function Probe() {
  const live = useSessionStore();
  return <><output aria-label="phase">{live.phase}</output><output aria-label="log">{JSON.stringify(live.log)}</output><output aria-label="toast">{live.toast?.text ?? ''}</output>
    <button onClick={() => void live.submit('ACCEPT')}>Accept action</button>
    <button onClick={() => void live.submit('OVERRIDE', 'Z2->S2', 'Road report', 'Bridge flooded')}>Override action</button>
    <button onClick={() => void live.submit('OVERRIDE', 'Z3->S3', 'Road report', 'Bridge flooded')}>Refuse action</button>
    <button onClick={() => void live.submit('DECLINE', '', 'Road report', 'Bridge flooded')}>Decline action</button>
    <button onClick={() => live.practice('OVERRIDE', subject('Z2->S2'), 1, 'CERT-PRACTICE')}>Practice action</button>
  </>;
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); });

describe('shared live session actions', () => {
  it('keeps recorded walkthrough decisions visibly separate from engine decisions', async () => {
    render(<SessionProvider><Probe /></SessionProvider>);
    await userEvent.click(screen.getByRole('button', { name: 'Practice action' }));
    const log = JSON.parse(screen.getByLabelText('log').textContent ?? '[]');
    expect(log).toHaveLength(1);
    expect(log[0]).toMatchObject({ decision: 'OVERRIDE', source: 'PRACTICE', cert_ids: ['CERT-PRACTICE'] });
    expect(screen.getByLabelText('toast')).toHaveTextContent('PRACTICE — not sent to the engine');
  });
  for (const [button, decision] of [['Accept action', 'ACCEPT'], ['Override action', 'OVERRIDE'], ['Decline action', 'DECLINE']] as const) {
    it(`${decision} writes one entry, KPI delta and toast`, async () => {
      sessionStorage.setItem('sentinel-live-session', JSON.stringify({ sessionId: 'one', world: 'v4-medium-dt2-v1', seed: 620003 }));
      vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
        const url = String(input);
        if (url.endsWith('/state')) return response(initialState);
        if (url.endsWith('/timeline')) return response({ timeline: [] });
        if (url.endsWith('/certificates')) return response({ certificates: [] });
        if (url.endsWith('/audit')) return response({ audit: [], refusals: [] });
        if (url.includes('/context')) return response(context);
        if (url.endsWith('/decisions')) return response({ audit_record: { decision: decision === 'DECLINE' ? 'REJECT' : decision }, state: finalState,
          certificates: [{ cert_id: 'CERT-000001', kind: decision === 'DECLINE' ? 'HOLD' : 'DISPATCH' }], rechecks: [] });
        throw new Error(url);
      });
      render(<SessionProvider><Probe /></SessionProvider>);
      await screen.findByText('AWAIT_DECISION');
      await userEvent.click(screen.getByRole('button', { name: button }));
      await waitFor(() => expect(screen.getByLabelText('phase')).toHaveTextContent('RESULT'));
      const log = JSON.parse(screen.getByLabelText('log').textContent ?? '[]');
      expect(log).toHaveLength(1);
      expect(log[0].decision).toBe(decision);
      expect(log[0].kpi_delta).toEqual({ safe: 10, waiting: -20, in_transit: 10 });
      expect(screen.getByLabelText('toast').textContent).toContain('CERT-000001 issued');
    });
  }

  it('keeps the pending context and logs a refused uncertified override', async () => {
    sessionStorage.setItem('sentinel-live-session', JSON.stringify({ sessionId: 'one', world: 'v4-medium-dt2-v1', seed: 620003 }));
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith('/state')) return response(initialState);
      if (url.endsWith('/timeline')) return response({ timeline: [] });
      if (url.endsWith('/certificates')) return response({ certificates: [] });
      if (url.endsWith('/audit')) return response({ audit: [], refusals: [] });
      if (url.includes('/context')) return response(context);
      if (url.endsWith('/decisions')) return response({ flag: 'UNCERTIFIED_OVERRIDE_REFUSED', timestep: 1, action_key: 'Z3->S3', verdict: 'UNDECIDED', reason: 'Road report: Bridge flooded' }, 422);
      throw new Error(url);
    });
    render(<SessionProvider><Probe /></SessionProvider>);
    await screen.findByText('AWAIT_DECISION');
    await userEvent.click(screen.getByRole('button', { name: 'Refuse action' }));
    await waitFor(() => expect(JSON.parse(screen.getByLabelText('log').textContent ?? '[]')).toHaveLength(1));
    expect(screen.getByLabelText('phase')).toHaveTextContent('AWAIT_DECISION');
    expect(screen.getByLabelText('log').textContent).toContain('REFUSED');
    expect(screen.getByLabelText('toast').textContent).toContain('Gate refused');
  });

  it('reattaches from sessionStorage and fetches the three required resources', async () => {
    sessionStorage.setItem('sentinel-live-session', JSON.stringify({ sessionId: 'one', world: 'v4-medium-dt2-v1', seed: 620003 }));
    const fetcher = vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input);
      if (url.endsWith('/state')) return response(initialState);
      if (url.endsWith('/timeline')) return response({ timeline: [] });
      if (url.endsWith('/certificates')) return response({ certificates: [] });
      if (url.endsWith('/audit')) return response({ audit: [], refusals: [] });
      if (url.includes('/context')) return response(context);
      throw new Error(url);
    });
    render(<SessionProvider><Probe /></SessionProvider>);
    await screen.findByText('AWAIT_DECISION');
    const paths = fetcher.mock.calls.map(([input]) => String(input));
    expect(paths).toContain('/api/sessions/one/state');
    expect(paths).toContain('/api/sessions/one/timeline');
    expect(paths).toContain('/api/sessions/one/certificates');
  });
});
