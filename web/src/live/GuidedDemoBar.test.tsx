import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import fixture from '../../../specs/contracts/demo_steps.json';
import type { DemoStep } from '../types';
import { GuidedDemoBar, KpiTiles, PipelineStrip } from './GuidedDemoBar';

const step = fixture.steps[0] as DemoStep;

describe('guided demo controls', () => {
  it('announces the current step and invokes navigation', async () => {
    const next = vi.fn();
    render(<GuidedDemoBar step={step} count={6} playing={false} completed={false} onPrevious={vi.fn()} onNext={next} onReset={vi.fn()} onTogglePlay={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent(step.caption);
    expect(screen.getByText(/Step 1 \/ 6/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Next step' }));
    expect(next).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Previous step' })).toBeDisabled();
  });
});

describe('pipeline and KPIs', () => {
  it('shows all six stages and fixture counts', () => {
    render(<><PipelineStrip current={step.pipeline_stage} /><KpiTiles kpis={step.kpis} /></>);
    expect(screen.getByRole('list', { name: 'Decision pipeline' }).children).toHaveLength(6);
    expect(screen.getByText('WAITING')).toBeVisible();
    expect(screen.getByText(step.kpis.waiting.toLocaleString('en-IN'))).toBeVisible();
  });
});
