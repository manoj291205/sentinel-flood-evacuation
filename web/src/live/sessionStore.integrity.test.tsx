import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
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
    <output aria-label="log">{JSON.stringify(live.log)}</output>
    <output aria-label="state">{JSON.stringify(live.state)}</output>
    <output aria-label="feed">{live.feed.map(item => item.text).join(' | ')}</output>
    <button onClick={() => void live.submit('ACCEPT')}>Accept action</button>
    <button onClick={() => void live.submit('OVERRIDE', 'WAIT', 'Road report', 'Hold')}>Override hold</button>
    <button onClick={() => void live.stepOn()}>Refresh action</button>
    <button onClick={() => void live.end()}>End action</button>
    <button onClick={() => void live.fastForward(3)}>Fast forward</button></>;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); sessionStorage.clear(); });

function attach(post: (body: Record<string, unknown>) => Promise<Response>, timeline: Record<string, unknown>[] = []) {
  sessionStorage.setItem('sentinel-live-session', JSON.stringify({ sessionId: 'one', world: 'v4-medium-dt2-v1', seed: 620003 }));
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (init?.method === 'DELETE') return response({ ended: true });
    if (url.endsWith('/state')) return response(snapshot);
    if (url.endsWith('/timeline')) return response({ timeline });
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

it('restores the event feed newest first, matching incoming live events', async () => {
  attach(async () => response({}), [
    { event_type: 'FLOOD_STATE_UPDATED', description: 'older hazard update' },
    { event_type: 'ROUTE_CLOSED', description: 'newer road closure' },
  ]);
  await screen.findByText('AWAIT_DECISION');
  expect(screen.getByLabelText('feed').textContent).toBe('ROUTE_CLOSED | FLOOD_STATE_UPDATED');
});

it('logs an override to HOLD as no dispatch', async () => {
  attach(async () => response({ audit_record: { decision: 'OVERRIDE' }, state: snapshot,
    certificates: [{ cert_id: 'HOLD-1', kind: 'HOLD', chosen: { action_key: 'WAIT' } }], rechecks: [] }));
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Override hold' }));
  await screen.findByText('RESULT');
  expect(JSON.parse(screen.getByLabelText('log').textContent!)[0].subject.kind).toBe('HOLD');
});

it('retains the original KPI baseline if state refreshes before an uncertain retry', async () => {
  let tries = 0;
  attach(async () => {
    if (++tries === 1) throw new TypeError('lost reply');
    return response({ audit_record: { decision: 'ACCEPT' }, state: { ...snapshot, state_version: 5, kpis: { ...snapshot.kpis, waiting: 10, safe: 10 } }, certificates: [], rechecks: [] });
  });
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await waitFor(() => expect(screen.getByLabelText('error')).toHaveTextContent(/retry/i));
  const fetchMock = vi.mocked(fetch);
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => String(input).endsWith('/state')
    ? response({ ...snapshot, state_version: 5, kpis: { ...snapshot.kpis, waiting: 10, safe: 10 } }) : previous(input, init));
  await userEvent.click(screen.getByRole('button', { name: 'Refresh action' }));
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await screen.findByText('RESULT');
  expect(JSON.parse(screen.getByLabelText('log').textContent!)[0].kpi_delta).toMatchObject({ waiting: -10, safe: 10 });
});

it('does not roll current state back to an older cached decision receipt', async () => {
  attach(async () => response({ audit_record: { decision: 'ACCEPT' }, state: { ...snapshot, state_version: 5 }, certificates: [], rechecks: [] }));
  const fetchMock = vi.mocked(fetch);
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => String(input).endsWith('/state')
    ? response({ ...snapshot, state_version: 7 }) : previous(input, init));
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await screen.findByText('RESULT');
  expect(JSON.parse(screen.getByLabelText('state').textContent!).state_version).toBe(7);
});

it('does not close a session while its decision result is unresolved', async () => {
  let resolve!: (value: Response) => void;
  attach(async () => new Promise<Response>(done => { resolve = done; }));
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await screen.findByText('SUBMITTING');
  await userEvent.click(screen.getByRole('button', { name: 'End action' }));
  expect(window.confirm).not.toHaveBeenCalled();
  resolve(response({ audit_record: { decision: 'ACCEPT' }, state: snapshot, certificates: [], rechecks: [] }));
  await screen.findByText('RESULT');
});

it('clears active presentation after the operator exports and closes a session', async () => {
  attach(async () => response({ audit_record: { decision: 'ACCEPT' }, state: snapshot, certificates: [], rechecks: [] }));
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  await screen.findByText('AWAIT_DECISION');
  await userEvent.click(screen.getByRole('button', { name: 'Accept action' }));
  await screen.findByText('RESULT');
  await userEvent.click(screen.getByRole('button', { name: 'End action' }));
  await screen.findByText('IDLE');
  expect(JSON.parse(screen.getByLabelText('log').textContent!)).toEqual([]);
  expect(sessionStorage.getItem('sentinel-live-session')).toBeNull();
});

it('ignores a late context response after the operator closes the session', async () => {
  let resolve!: (value: Response) => void;
  attach(async () => response({}));
  const fetchMock = vi.mocked(fetch);
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => String(input).includes('/context')
    ? new Promise<Response>(done => { resolve = done; }) : previous(input, init));
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  await waitFor(() => expect(resolve).toBeTypeOf('function'));
  await userEvent.click(screen.getByRole('button', { name: 'End action' }));
  await act(async () => { resolve(response(context)); });
  expect(screen.getByLabelText('phase')).toHaveTextContent('IDLE');
  expect(screen.getByLabelText('state')).toHaveTextContent('null');
});

it('serializes duplicate close gestures into one release request', async () => {
  let resolve!: (value: Response) => void;
  attach(async () => response({}));
  const fetchMock = vi.mocked(fetch);
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => init?.method === 'DELETE'
    ? new Promise<Response>(done => { resolve = done; }) : previous(input, init));
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  await screen.findByText('AWAIT_DECISION');
  await userEvent.dblClick(screen.getByRole('button', { name: 'End action' }));
  expect(window.confirm).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE')).toHaveLength(1);
  await act(async () => { resolve(response({ ended: true })); });
  await screen.findByText('IDLE');
});

it('keeps reattachment pending until the current snapshot and recommendation both load', async () => {
  let resolve!: (value: Response) => void;
  attach(async () => response({}));
  const fetchMock = vi.mocked(fetch);
  const previous = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(async (input, init) => String(input).endsWith('/state')
    ? new Promise<Response>(done => { resolve = done; }) : previous(input, init));
  await waitFor(() => expect(resolve).toBeTypeOf('function'));
  expect(screen.getByLabelText('phase')).toHaveTextContent('STARTING');
  await act(async () => { resolve(response(snapshot)); });
  await screen.findByText('AWAIT_DECISION');
});
