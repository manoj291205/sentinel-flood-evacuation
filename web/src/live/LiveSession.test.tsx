import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LiveSession from './LiveSession';

afterEach(() => vi.unstubAllGlobals());

describe('live certified session', () => {
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
