import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import DecisionModal, { type Context } from './DecisionModal';
import { livePhase } from './LiveSession';

afterEach(cleanup);
const context: Context = { certified: { timestep: 1, recommendation: { action_key: 'Z1->S1', label: 'Z1 → S1', verdict: 'FEASIBLE', lower: .96, certified: true, comparison: '' }, why: ['Certified lower bound 0.960'], alternatives: [
  { action_key: 'Z2->S2', label: 'Z2 → S2', verdict: 'FEASIBLE', lower: .95, certified: true, comparison: 'Certified alternative' },
  { action_key: 'Z3->S3', label: 'Z3 → S3', verdict: 'UNDECIDED', lower: .72, certified: false, comparison: 'No certificate' },
], rechecks: [], note: 'Re-checks happen on consultation.', threshold: .9, futures_used: 256, looks: 2 } };

describe('operator decision dialog', () => {
  it('describes the committed HOLD instead of the original dispatch suggestion', () => {
    render(<DecisionModal context={context} result={{ audit_record: { decision: 'REJECT' }, certificates: [{ cert_id: 'HOLD-1', kind: 'HOLD', chosen: { action_key: 'WAIT' } }], rechecks: [] }} refusal={null} busy={false} session="one" safeDelta={0} onSubmit={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByText('HOLD: no dispatch this step', { exact: true })).toBeVisible();
  });
  it('shows refusal and cannot select uncertified alternatives', async () => {
    render(<DecisionModal context={context} result={null} refusal={{ timestep: 1, action_key: 'Z3->S3', verdict: 'UNDECIDED', reason: 'test', flag: 'UNCERTIFIED_OVERRIDE_REFUSED' }} busy={false} session="one" safeDelta={null} onSubmit={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Gate refused: not certified');
    expect(screen.getByRole('button', { name: 'Choose Z3 → S3' })).toBeDisabled();
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true');
  });
  it('requires a reason and responds to A O D and Escape', async () => {
    const submit = vi.fn();
    const user = userEvent.setup();
    render(<DecisionModal context={context} result={null} refusal={null} busy={false} session="one" safeDelta={null} onSubmit={submit} onNext={vi.fn()} />);
    await user.keyboard('o');
    expect(screen.getByLabelText('REASON')).toBeRequired();
    await user.click(screen.getByRole('button', { name: 'Confirm override' }));
    expect(submit).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText('REASON'), 'Local road blocked');
    await user.click(screen.getByRole('button', { name: 'Confirm override' }));
    expect(submit).toHaveBeenCalledWith('OVERRIDE', 'Z2->S2', 'Local knowledge: Local road blocked');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Decision pending/ }));
    await user.keyboard('d');
    expect(screen.getByRole('button', { name: 'Confirm decline' })).toBeInTheDocument();
    await user.keyboard('a');
    expect(submit).toHaveBeenCalledWith('ACCEPT', '', '');
  });
});

it('enforces live decision transitions', () => {
  expect(livePhase('IDLE', 'START')).toBe('STARTING');
  expect(livePhase('STARTING', 'CONTEXT')).toBe('AWAIT_DECISION');
  expect(livePhase('AWAIT_DECISION', 'SUBMIT')).toBe('SUBMITTING');
  expect(livePhase('SUBMITTING', 'COMMIT')).toBe('RESULT');
  expect(livePhase('RESULT', 'NEXT')).toBe('AWAIT_DECISION');
  expect(livePhase('RESULT', 'END')).toBe('DONE');
});
