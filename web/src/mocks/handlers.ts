import { http, HttpResponse } from 'msw';
import demoFixture from '../../../specs/contracts/demo_steps.json';
import mapFixture from '../../../docs/design/sentinel-console/fort_kochi_map_geometry.json';
import certificateFixture from '../../../specs/contracts/certificates_fixture.json';
import whyFixture from '../../../specs/contracts/decision_why_fixture.json';
import evidenceManifest from '../../../specs/contracts/evidence_manifest.json';
import systemFixture from '../../../specs/contracts/system_status_fixture.json';
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
  http.get('/api/certificates', () => HttpResponse.json({ certificates: certificateFixture.certificates, source: 'FIXTURE', simulated: true, honesty })),
  http.get('/api/certificates/:id', ({ params }) => {
    const cert = certificateFixture.certificates.find(item => item.cert_id === params.id);
    return cert ? HttpResponse.json(cert) : new HttpResponse(null, { status: 404 });
  }),
  http.post('/api/certificates/:id/replay', async ({ params, request }) => {
    if (!certificateFixture.certificates.some(item => item.cert_id === params.id)) return new HttpResponse(null, { status: 404 });
    const body = await request.json() as { tamper?: boolean };
    return HttpResponse.json({ result: body.tamper ? 'MISMATCH' : 'MATCH', mismatched_fields: body.tamper ? ['forecast_hash'] : [], source: 'FIXTURE', simulated: true, honesty });
  }),
  http.get('/api/decisions/:id/why', ({ params }) => {
    const why = whyFixture.items.find(item => item.decision_id === params.id);
    return why ? HttpResponse.json(why) : new HttpResponse(null, { status: 404 });
  }),
  http.get('/api/evidence', () => HttpResponse.json({
    source: 'ARTIFACT', simulated: true, honesty,
    items: evidenceManifest.items.map(item => ({ id: item.id, group: item.group, label: item.label,
      value: null, display: '-', unit: item.unit, source_path: item.path,
      source_sha256: null, note: 'not produced yet in mock mode' })),
  })),
  http.get('/api/constraints/tiers', () => HttpResponse.json({ status: 'MISSING', status_reason: 'No tier run in mock mode', rules: [] })),
  http.get('/api/system/status', () => HttpResponse.json(systemFixture)),
  http.get('/api/system/acks', () => HttpResponse.json({ items: [], source: 'FIXTURE', simulated: true, honesty })),
];
