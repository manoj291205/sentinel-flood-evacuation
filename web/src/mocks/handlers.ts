import { http, HttpResponse } from 'msw';
import demoFixture from '../../../specs/contracts/demo_steps.json';
import mapFixture from '../../../docs/design/sentinel-console/fort_kochi_map_geometry.json';
import type { DemoState, DemoStep } from '../types';

let current = 0;
const steps = demoFixture.steps as DemoStep[];
const honesty = 'REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED';

const state = (): DemoState => ({
  source: 'FIXTURE',
  step_index: current,
  step_count: steps.length,
  step: steps[current],
  simulated: true,
  honesty,
});

export const handlers = [
  http.get('/api/demo/state', () => HttpResponse.json(state())),
  http.post('/api/demo/start', () => {
    current = 0;
    return HttpResponse.json(state());
  }),
  http.post('/api/demo/step', async ({ request }) => {
    const body = await request.json() as { action?: string };
    if (body.action === 'next') current = Math.min(current + 1, steps.length - 1);
    else if (body.action === 'prev') current = Math.max(current - 1, 0);
    else current = 0;
    return HttpResponse.json(state());
  }),
  http.get('/api/map/geometry', () => HttpResponse.json({ ...mapFixture, source: 'FIXTURE', simulated: true, honesty })),
];
