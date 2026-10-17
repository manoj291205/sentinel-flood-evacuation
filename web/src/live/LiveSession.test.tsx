import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LiveSession from './LiveSession';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('live certified session', () => {
  it('shows the exploratory network cut, team shares, held dispatch, and rebalance', async () => {
    const base = { session_id: 'escrow-1', mode: 'escrow', timestep: 0, note: 'Exploratory: not part of the pre-registered evaluation.', blocked: [], teams: [], last_reconciliation: null };
    const responses = [
      { ...base, network: 'ONLINE', label: null },
      { ...base, network: 'OFFLINE', label: 'Simulated network outage', teams: [{ team: 'TEAM-A', seats_left: 3, seats_total: 5, zones: ['Z-01'] }, { team: 'TEAM-B', seats_left: 2, seats_total: 4, zones: ['Z-02'] }] },
      { ...base, network: 'OFFLINE', label: 'Simulated network outage', blocked: [{ team: 'TEAM-A', action_key: 'Z-01->S-01', people: 2, reason: 'Share exhausted', suggested: 'Hold' }], teams: [] },
      { ...base, network: 'ONLINE', label: null, last_reconciliation: { returned_to_pool: 3, overbooked_seats: 0, executed: [] } },
    ];
    vi.stubGlobal('fetch', vi.fn().mockImplementation(async () => ({ ok: true, json: async () => responses.shift() })));
    render(<LiveSession />);
    await userEvent.click(screen.getByLabelText('Two-team network demo'));
    await userEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(await screen.findByRole('region', { name: 'Network' })).toHaveTextContent('ONLINE');
    await userEvent.click(screen.getByRole('button', { name: 'Cut network' }));
    expect(await screen.findByText(/TEAM-A: 3 of 5 seats left/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Step on' }));
    expect(await screen.findByText(/Held dispatch/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Restore network' }));
    expect(await screen.findByText(/Rebalanced: 3 seats back to the pool/)).toBeVisible();
  });
  it('shows the pending reason, disables an uncertified option, and commits an accepted certificate', async () => {
    const responses = [
      { session_id: 'live-1' },
      { certified: { timestep: 0, recommendation: { label: 'HOLD' },
        why: ['No dispatch option reached the threshold', 'Best option is undecided', 'The gate holds'],
        alternatives: [{ action_key: 'Z1->S1', label: 'Z-01 → S-01', verdict: 'UNDECIDED',
          lower: 0.5, certified: false, comparison: 'Not certified by the gate' }],
        rechecks: [], note: 'Groups on the road are re-checked.' } },
      { kpis: { waiting: 100, in_transit: 0, safe: 0, certificates_issued: 0 } },
      { audit_record: { decision: 'ACCEPT' }, certificates: [{ cert_id: 'CERT-000001', kind: 'HOLD' }], rechecks: [] },
      { kpis: { waiting: 100, in_transit: 0, safe: 0, certificates_issued: 1 } },
    ];
    const fetchMock = vi.fn().mockImplementation(async () => ({ ok: true, json: async () => responses.shift() }));
    vi.stubGlobal('fetch', fetchMock);
    render(<LiveSession />);
    await userEvent.click(screen.getByRole('button', { name: 'Start' }));
    expect(await screen.findByText('No dispatch option reached the threshold')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Choose Z-01 → S-01' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(screen.getByRole('link', { name: 'CERT-000001' })).toHaveAttribute(
      'href', '/decisions?session=live-1&cert=CERT-000001'));
  });
});
