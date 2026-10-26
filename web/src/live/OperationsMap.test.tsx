import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import fixture from '../../../specs/contracts/demo_steps.json';
import geometry from '../../../docs/design/sentinel-console/fort_kochi_map_geometry.json';
import type { DemoStep, MapGeometry } from '../types';
import { Legend, OperationsMap, SimulationMap } from './OperationsMap';

describe('operations map and legend', () => {
  it('draws the selected route over road topology with accessible entities', async () => {
    const view = render(<OperationsMap geometry={geometry as unknown as MapGeometry} step={fixture.steps[0] as DemoStep} selectedCandidate="c2" />);
    expect(screen.getByRole('img', { name: /Fort Kochi road topology/ })).toBeVisible();
    expect(view.container.querySelectorAll(`path[d="${fixture.routes.c2.svg_path}"]`)).toHaveLength(2);
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Select zone Z-01' })).toBeVisible();
  });

  it('pairs map symbols with words', () => {
    render(<Legend />);
    expect(screen.getByText('Feasible dispatch')).toBeVisible();
    expect(screen.getByText('Closed road')).toBeVisible();
  });

  it('keeps committed marks and transit groups on their pinned paths after rerouting', () => {
    const view = render(<SimulationMap geometry={geometry as unknown as MapGeometry} label="Live"
      step={{ chosen_key: 'WAIT', candidates: [{ action_key: 'Z1->S1', people: 10, verdict: 'FEASIBLE', svg_path: 'M1 1L2 2' }], zone_severity: {}, shelter_severity: {}, edge_closed_path: '', shelters: [] }}
      marks={[{ id: 'cert-1', action_key: 'Z1->S1', decision: 'ACCEPT', svg_path: 'M3 3L4 4' }]}
      moving={[{ group_id: 'g1', action_key: 'Z1->S1', progress: .4, svg_path: 'M5 5L6 6' }]} />);
    expect(view.container.querySelector('path[data-decision="ACCEPT"]')).toHaveAttribute('d', 'M3 3L4 4');
    expect(view.container.querySelector('animateMotion[path="M5 5L6 6"]')).toBeTruthy();
  });
});
