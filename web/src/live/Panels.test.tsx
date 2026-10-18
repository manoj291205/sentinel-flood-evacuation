import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import fixture from '../../../specs/contracts/demo_steps.json';
import type { DemoStep } from '../types';
import { EventFeed, GatePanel, ShelterLedger, SideTabs, SuggestionCard, TransitList } from './Panels';

const step = fixture.steps[2] as DemoStep;

describe('operations side panels', () => {
  it('switches side tabs', async () => {
    const change = vi.fn();
    render(<SideTabs active="Suggestion" onChange={change} />);
    await userEvent.click(screen.getByRole('tab', { name: 'Shelters' }));
    expect(change).toHaveBeenCalledWith('Shelters');
  });

  it('shows each why reason', () => {
    render(<SuggestionCard step={step} />);
    expect(screen.getByText('WHY THIS SUGGESTION')).toBeVisible();
    for (const reason of step.suggestion.why) expect(screen.getByText(reason)).toBeVisible();
  });

  it('selects a gate candidate while preserving its verdict', async () => {
    const select = vi.fn();
    render(<GatePanel step={step} selected={step.default_selection} onSelect={select} />);
    const candidate = step.gate.candidates[0];
    await userEvent.click(screen.getByRole('button', { name: `${candidate.label} ${candidate.status}` }));
    expect(select).toHaveBeenCalledWith(candidate.id);
  });

  it('renders transit, shelter and event fixture records', () => {
    render(<><TransitList groups={step.groups} /><ShelterLedger shelters={step.shelters} /><EventFeed events={step.events} /></>);
    expect(screen.getByText(step.groups[0].group_id)).toBeVisible();
    expect(screen.getByText(`${step.shelters[0].shelter_id} · ${step.shelters[0].name}`)).toBeVisible();
    expect(screen.getByText(step.events.at(-1)!.text)).toBeVisible();
  });
});
