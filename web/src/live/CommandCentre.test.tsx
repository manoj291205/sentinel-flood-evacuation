import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { OperatorBar } from './CommandCentre';

describe('operator decision bar', () => {
  it('shows a clear subject and routes each choice, then becomes a result strip', async () => {
    const accept = vi.fn(), override = vi.fn(), decline = vi.fn(), step = vi.fn();
    const props = { step: 2, subject: 'Dispatch 20 people · Z1 → S2 · ETA 18 min', verdict: 'CERTIFIED',
      phase: 'AWAIT_DECISION', busy: false, onAccept: accept, onOverride: override, onDecline: decline, onStep: step };
    const view = render(<OperatorBar {...props} />);
    expect(screen.getByRole('region', { name: 'Operator decides' })).toHaveTextContent(props.subject);
    for (const [name, callback] of [['Accept', accept], ['Override', override], ['Decline', decline]] as const) {
      await userEvent.click(screen.getByRole('button', { name }));
      expect(callback).toHaveBeenCalledOnce();
    }
    view.rerender(<OperatorBar {...props} phase="RESULT" result={{ id: 'one', step: 2, utc: '', decision: 'ACCEPT',
      subject: { action_key: 'Z1->S2', kind: 'DISPATCH', people: 20, zone_id: 'Z1', shelter_id: 'S2' },
      cert_ids: ['CERT-000001'], kpi_delta: { safe: 20, waiting: -20, in_transit: 0 }, source: 'LIVE' }} />);
    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    expect(screen.getByText(/CERT-000001/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'STEP ON' }));
    expect(step).toHaveBeenCalledOnce();
  });
});
