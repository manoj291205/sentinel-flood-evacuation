import { http, HttpResponse } from 'msw';
import demoFixture from '../../../specs/contracts/demo_steps.json';
import mapFixture from '../../../docs/design/sentinel-console/fort_kochi_map_geometry.json';
import certificateFixture from '../../../specs/contracts/certificates_fixture.json';
import whyFixture from '../../../specs/contracts/decision_why_fixture.json';
import evidenceManifest from '../../../specs/contracts/evidence_manifest.json';
import systemFixture from '../../../specs/contracts/system_status_fixture.json';
import outageSummary from '../../../data/eval_results/phase35lite/outages.json';
import type { DemoState, DemoStep } from '../types';

let current = 0;
let liveStep = 0;
let liveCertificate = 0;
let extendedLive = false;
let liveRows: Record<string, unknown>[] = [];
let liveRefusals: Record<string, unknown>[] = [];
let liveWaiting = 100, liveTransit = 0, liveSafe = 0;
const liveRequests = new Map<string, { body: string; status: number; response: Record<string, unknown> }>();
const liveIdentity = (id: string) => ({ session_id: id, state_version: liveStep,
  recommendation_id: (liveStep + 1).toString(16).padStart(64, '0') });
const liveRouting = () => ({ graph_fingerprint: 'MOCK-TOPOLOGY', timestep: liveStep, state_version: liveStep,
  closed_edge_svg_path: '', routes: Object.fromEntries(['Z1->S2', 'Z2->S2', 'Z3->S3', 'Z1->S1'].map(key => {
    const [zone, shelter] = key.split('->');
    const geometry = (mapFixture as unknown as Record<string, unknown>)[`route_${zone}_${shelter}`] as [string, number] | undefined;
    return [key, { action_key: key, edge_ids: [`mock-edge:${key}`], reachable: true, path_sha256: null,
      path_id: `mock-path:${key}`, svg_path: geometry?.[0] ?? '', graph_fingerprint: 'MOCK-TOPOLOGY',
      timestep: liveStep, distance_m: geometry?.[1] ?? null }];
  })) });
const liveSubject = (key: string) => {
  const [zone, shelter] = key.split('->');
  return { action_key: key, kind: key === 'WAIT' ? 'HOLD' : 'DISPATCH', people: key === 'WAIT' ? null : 20,
    zone_id: key === 'WAIT' ? null : zone, zone_name: null, zone_waiting: key === 'WAIT' ? null : liveWaiting,
    zone_flood_severity: key === 'WAIT' ? null : .2, shelter_id: key === 'WAIT' ? null : shelter, shelter_name: null,
    shelter_seats_free_before: key === 'WAIT' ? null : 80, shelter_seats_free_after: key === 'WAIT' ? null : 60,
    route_label: key === 'WAIT' ? null : `R-${zone}-${shelter}`, route_length_km: null, eta_minutes: key === 'WAIT' ? null : 18, closed_edges_on_route: null };
};
const liveState = () => ({ source: 'FIXTURE', current_timestep: liveStep, people_stranded: 0,
  summary: { terminal_reason: liveStep >= (extendedLive ? 4 : 3) ? 'HORIZON_REACHED' : null },
  kpis: { waiting: liveWaiting, in_transit: liveTransit, safe: liveSafe, certificates_issued: liveCertificate },
  zones: [{ zone_id: 'Z1', population_remaining: liveWaiting, flood_severity_current: .2 }],
  shelters: [{ shelter_id: 'S2', capacity_total: 100, occupancy_current: liveSafe, capacity_reserved: liveTransit, capacity_available: 100 - liveSafe - liveTransit, flood_severity_current: .1 }],
  route_rows: [], transit_positions: [] });
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
  http.post('/api/sessions', async ({ request }) => { const body = await request.json() as { seed?: number }; extendedLive = body.seed === 620004; liveStep = 0; liveCertificate = 0; liveRows = []; liveRefusals = []; liveWaiting = 100; liveTransit = 0; liveSafe = 0; liveRequests.clear(); return HttpResponse.json({ session_id: 'fixture-session', horizon_steps: extendedLive ? 4 : 3, source: 'FIXTURE' }); }),
  http.delete('/api/sessions/:id', () => HttpResponse.json({ ended: true, source: 'FIXTURE' })),
  http.get('/api/sessions/:id/context', ({ params }) => liveStep >= (extendedLive ? 4 : 3) ? HttpResponse.json({ detail: 'episode is complete' }, { status: 409 }) : HttpResponse.json({ decision_identity: liveIdentity(String(params.id)), routing: liveRouting(), active_rules: { enforced_count: 0, rules: [], digest: null }, certified: { timestep: liveStep, threshold: .9, futures_used: 64, looks: 1,
    recommendation: liveStep === 0 && !extendedLive ? { action_key: 'WAIT', label: 'HOLD', verdict: 'ALWAYS_ALLOWED', lower: null, certified: true, comparison: '', subject: liveSubject('WAIT') } : { action_key: 'Z1->S2', label: 'Z1 → S2', verdict: 'FEASIBLE', lower: .94, certified: true, comparison: '', subject: liveSubject('Z1->S2') },
    why: liveStep === 0 && !extendedLive ? ['No dispatch option reached the threshold'] : ['Certified lower bound 0.940 clears the bar'],
    alternatives: liveStep === 0 && !extendedLive ? [{ action_key: 'Z1->S1', label: 'Z1 → S1', verdict: 'UNDECIDED', lower: .5, certified: false, comparison: 'Below the safety bar', subject: liveSubject('Z1->S1') }] : [{ action_key: 'Z2->S2', label: 'Z2 → S2', verdict: 'FEASIBLE', lower: .92, certified: true, comparison: 'Certified alternate route', subject: liveSubject('Z2->S2') }, { action_key: 'Z3->S3', label: 'Z3 → S3', verdict: 'UNDECIDED', lower: .5, certified: false, comparison: 'Not certified', subject: liveSubject('Z3->S3') }], rechecks: [], note: 'Fixture scenario for interface testing' }, source: 'FIXTURE' })),
  http.get('/api/sessions/:id/state', () => HttpResponse.json(liveState())),
  http.get('/api/sessions/:id/timeline', () => HttpResponse.json({ timeline: liveRows })),
  http.get('/api/sessions/:id/certificates', () => HttpResponse.json({ certificates: liveRows.map(row => row.certificate) })),
  http.get('/api/sessions/:id/audit', () => HttpResponse.json({ audit: liveRows.map(row => row.audit_record), refusals: liveRefusals })),
  http.post('/api/sessions/:id/decisions', async ({ request, params }) => {
    const body = await request.json() as { decision: string; selected_action?: string; reason?: string; request_id: string; expected_state_version: number; recommendation_id: string };
    if (!body.request_id || body.expected_state_version == null || !body.recommendation_id) return HttpResponse.json({ detail: 'Decision identity required' }, { status: 422 });
    const cached = liveRequests.get(body.request_id);
    if (cached) return cached.body === JSON.stringify(body) ? HttpResponse.json(cached.response, { status: cached.status }) : HttpResponse.json({ detail: 'Request identity reused with different content' }, { status: 409 });
    const identity = liveIdentity(String(params.id));
    if (body.expected_state_version !== identity.state_version || body.recommendation_id !== identity.recommendation_id) return HttpResponse.json({ detail: 'Stale decision' }, { status: 409 });
    if (body.decision === 'OVERRIDE' && body.selected_action !== 'Z2->S2' && body.selected_action !== 'WAIT') {
      const refusal = { flag: 'UNCERTIFIED_OVERRIDE_REFUSED', timestep: liveStep, action_key: body.selected_action, verdict: 'UNDECIDED', reason: body.reason, detail: 'Override is not certified' };
      liveRefusals.push(refusal); liveRequests.set(body.request_id, { body: JSON.stringify(body), response: refusal, status: 422 }); return HttpResponse.json(refusal, { status: 422 });
    }
    liveCertificate++;
    const certId = `CERT-${String(liveCertificate).padStart(6, '0')}`;
    const fixture = certificateFixture.certificates[0];
    const action = body.decision === 'REJECT' ? 'WAIT' : body.selected_action ?? (liveStep === 0 && !extendedLive ? 'WAIT' : 'Z1->S2');
    const certificate = { ...fixture, cert_id: certId, kind: action === 'WAIT' ? 'HOLD' : 'DISPATCH', timestep: liveStep,
      chosen: { ...fixture.chosen, action_key: action, people: action === 'WAIT' ? 0 : Math.min(20, liveWaiting) },
      operator: { ...fixture.operator, actor: 'Mock operator', decision: body.decision, reason: body.reason ?? '' },
      commands: action === 'WAIT' ? [] : [{ target: 'mock-vehicle', command: `route ${action}` }] };
    const audit_record = { decision: body.decision, timestep: liveStep };
    liveRows.push({ audit_record, certificate, event_type: 'DECISION_COMMITTED', timestep: liveStep });
    const route = liveRouting().routes[action];
    liveSafe += liveTransit; liveTransit = 0;
    if (action !== 'WAIT') { const people = Math.min(20, liveWaiting); liveWaiting -= people; liveTransit += people; }
    liveStep++;
    const result = { audit_record, state: liveState(), certificates: [certificate], rechecks: [], executed_routes: route ? { [certId]: route } : {}, source: 'FIXTURE' };
    liveRequests.set(body.request_id, { body: JSON.stringify(body), response: result, status: 200 });
    return HttpResponse.json(result);
  }),
  http.get('/api/library/index', () => HttpResponse.json({ source: 'FIXTURE', runs: [], analysis: { bars: { bar1: { pass: false }, bar2: { pass: true }, bar3: { pass: false }, bar4: { pass: true } }, E2_ratio_P_over_A2: null }, analysis_source: 'Mock mode: no frozen run summaries loaded' })),
  http.get('/api/library/trace/:regime/:seed', () => HttpResponse.json({ detail: 'Recorded trace unavailable in mock mode' }, { status: 503 })),
  http.get('/api/project/facts', () => HttpResponse.json({ source: 'FIXTURE', facts: Object.fromEntries(['tests', 'recorded_runs', 'traces', 'corpus_chunks', 'phases'].map(key => [key, { value: null, source_path: 'Local artifact unavailable in mock mode', reason: 'Open the local API for counts' }])) })),
  http.get('/api/escrow/comparison', () => HttpResponse.json({ source: 'ARTIFACT', totals: outageSummary.totals, source_path: 'data/eval_results/phase35lite/outages.json', note: 'Exploratory offline capacity study; not pre-registered and no outcome-effect claim.' })),
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
