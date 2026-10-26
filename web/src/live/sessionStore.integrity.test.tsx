import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { SessionProvider, useSessionStore } from './sessionStore';

const identity = { session_id: 'one', state_version: 4, recommendation_id: 'a'.repeat(64) };
const snapshot = { current_timestep: 1, kpis: { waiting: 20, in_transit: 0, safe: 0, certificates_issued: 0 } };
const context = { decision_identity: identity, routing: { graph_fingerprint: 'graph', timestep: 1, state_version: 4, routes: {}, closed_edge_svg_path: '' },
  certified: { timestep: 1, recommendation: { action_key: 'WAIT', label: 'HOLD', verdict: 'ALWAYS_ALLOWED', lower: null, certified: true, comparison: '' },
    why: [], alternatives: [], rechecks: [], note: '' } };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
function Probe() {
  const live = useSessionStore();
  return <><output aria-label="phase">{live.phase}</output><output aria-label="error">{live.error}</output>
    <button onClick={() => void live.submit('ACCEPT')}>Accept action</button>
    <button onClick={() => void live.fastForward(3)}>Fast forward</button></>;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); });

function attach(post: (body: Record<string, unknown>) => Promise<Response>) {
  sessionStorage.setItem('sentinel-live-session', JSON.stringify({ sessionId: 'one', world: 'v4-medium-dt2-v1', seed: 620003 }));
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/state')) return response(snapshot);
    if (url.endsWith('/timeline')) return response({ timeline: [] });
    if (url.endsWith('/certificates')) return response({ certificates: [] });
    if (url.endsWith('/audit')) return response({ audit: [], refusals: [] });
    if (url.includes('/context')) return response(context);
    if (url.endsWith('/decisions')) return post(JSON.parse(String(init?.body)));
    throw new Error(url);
  });
  render(<SessionProvider><Probe /></SessionProvider>);
}

it('binds an operator request to the exact displayed recommendation and state', async () => {
  const sent: Record<string, unknown>[] = [];
  attach(async body => { sent.push(body); return response({ audit_record: { decision: 'ACCEPT' }, state: snapshot, certificates: [], rechecks: [] }); });
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await waitFor(() => expect(sent).toHaveLength(1));
  expect(sent[0]).toMatchObject({ expected_state_version: 4, recommendation_id: identity.recommendation_id });
  expect(sent[0].request_id).toMatch(/^[0-9a-f-]{36}$/);
});

it('retries the identical UUID and body after a lost transport response', async () => {
  const sent: Record<string, unknown>[] = [];
  attach(async body => {
    sent.push(body);
    if (sent.length === 1) throw new TypeError('connection lost after server commit');
    return response({ audit_record: { decision: 'ACCEPT' }, state: snapshot, certificates: [], rechecks: [] });
  });
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await waitFor(() => expect(screen.getByLabelText('error')).toHaveTextContent(/retry/i));
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await waitFor(() => expect(screen.getByLabelText('phase')).toHaveTextContent('RESULT'));
  expect(sent).toHaveLength(2);
  expect(sent[1]).toEqual(sent[0]);
});

it('refreshes a stale context without automatically submitting another decision', async () => {
  const sent: Record<string, unknown>[] = [];
  attach(async body => { sent.push(body); return response({ detail: 'STALE_DECISION' }, 409); });
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await waitFor(() => expect(screen.getByLabelText('error')).toHaveTextContent(/review/i));
  expect(sent).toHaveLength(1);
  expect(screen.getByLabelText('phase')).toHaveTextContent('AWAIT_DECISION');
});

it('stops fast-forward when a decision outcome is unknown', async () => {
  const sent: Record<string, unknown>[] = [];
  attach(async body => { sent.push(body); throw new TypeError('lost response'); });
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Fast forward' }));
  await waitFor(() => expect(screen.getByLabelText('error')).toHaveTextContent(/retry/i));
  expect(sent).toHaveLength(1);
});
