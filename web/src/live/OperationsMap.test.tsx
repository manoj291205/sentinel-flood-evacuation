import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import fixture from '../../../specs/contracts/demo_steps.json';
import geometry from '../../../docs/design/sentinel-console/fort_kochi_map_geometry.json';
import type { DemoStep, MapGeometry } from '../types';
import { Legend, OperationsMap } from './OperationsMap';

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
});
