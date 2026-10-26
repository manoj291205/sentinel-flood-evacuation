// Phase 34C acceptance (Lead). the Lane X agent copies this file UNCHANGED to web/e2e/p34c_live_session.spec.ts.
// Runs only in the Playwright project "live" (`npm run test:e2e:live`): real FastAPI + Vite without VITE_API_MOCK.
// Live certified session on v4-medium-dt2-v1, seed 620003, params v4-cert-test-v1. Lead pilot: step 0 is a HOLD with
// every option UNDECIDED (so every alternative is uncertified), step 1 suggests a certified dispatch.
import { expect, test } from '@playwright/test';

test.setTimeout(180_000);

async function start(page) {
  await page.goto('/live');
  await page.getByRole('radiogroup', { name: 'Mode' }).getByRole('radio', { name: 'Live session' }).check();
  await page.getByLabel('Seed').fill('620003');
  await page.getByLabel('World').selectOption('v4-medium-dt2-v1');
  await page.getByRole('button', { name: 'Start' }).click();
  await expect(page.getByText(/Live session · simulated hazards/)).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 60_000 });
}

test('live session: hold, uncertified alternatives, accept, step on to a certified suggestion', async ({ page }) => {
  await start(page);
  const alternatives = page.getByLabel('Alternatives');
  await expect(alternatives.getByText('Not certified — the gate will not dispatch this').first()).toBeVisible();
  await expect(page.getByText(/No dispatch option reached the threshold/)).toBeVisible();
  await page.getByRole('button', { name: 'Accept' }).click();
  await expect(page.getByRole('region', { name: 'Event feed' }).getByRole('link', { name: /^CERT-000001 issued/ })).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: 'Step on' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 60_000 });
  await expect(page.getByText(/Certified lower bound \d\.\d{3}/)).toBeVisible();
  await expect(alternatives).toBeVisible();
});

test('groups already on the road are re-checked and re-routed live', async ({ page }) => {
  await start(page);
  for (let step = 0; step < 5; step++) {
    await page.getByRole('button', { name: 'Accept' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 60_000 });
    await page.getByRole('button', { name: 'Step on' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 60_000 });
  }
  // Lead pilot of this seed: with ACCEPT at every step a group is re-routed at step 4
  await expect(page.getByText(/Re-routed automatically as CERT-\d{6}/).first()).toBeVisible();
});

test('override needs a reason and commits a certificate with an audit row', async ({ page }) => {
  await start(page);
  await page.getByRole('button', { name: 'Accept' }).click();
  await expect(page.getByRole('region', { name: 'Event feed' }).getByRole('link', { name: /^CERT-000001 issued/ })).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: 'Step on' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 60_000 });
  await page.getByRole('button', { name: 'Override' }).click();
  const reason = page.getByLabel(/REASON/);
  await expect(reason).toHaveAttribute('required', '');
  await page.getByRole('radio', { name: 'Road report' }).check();
  await reason.fill('field team reports the preferred road is busy');
  await page.getByRole('button', { name: /Confirm override/ }).click();
  await expect(page.getByRole('dialog').getByRole('link', { name: 'CERT-000002', exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/OVERRIDE/).first()).toBeVisible();
  await page.getByRole('dialog').getByRole('link', { name: 'CERT-000002', exact: true }).click();
  await expect(page.getByLabel('Decision detail')).toContainText(/OVERRIDE|HOLD/);
});

test('live engine binds an accepted route, updated state, replay and audit export', async ({ page }, testInfo) => {
  await start(page);
  const bar = page.getByRole('region', { name: 'Operator decides' });
  await bar.getByRole('button', { name: 'Accept' }).click();
  await bar.getByRole('button', { name: 'Step on' }).click();
  await expect(bar.getByRole('button', { name: 'Accept' })).toBeEnabled({ timeout: 60_000 });
  const exportLink = page.getByRole('link', { name: 'Download audit JSON' });
  const exportUrl = await exportLink.getAttribute('href');
  const sessionUrl = exportUrl!.replace('/audit.json', '');
  const current = await (await page.request.get(`${sessionUrl}/context?include_subject=true`)).json();
  const before = await (await page.request.get(`${sessionUrl}/state`)).json();
  const key = current.certified.recommendation.action_key;
  expect(key).not.toBe('WAIT');
  const displayed = current.routing.routes[key];
  expect(displayed.edge_ids.length).toBeGreaterThan(0);
  await expect(page.locator('path').filter({ has: page.locator('title', { hasText: key }) }).first()).toHaveAttribute('d', displayed.svg_path);
  const committedResponse = page.waitForResponse(response => response.url().endsWith(`${sessionUrl}/decisions`) && response.request().method() === 'POST');
  await bar.getByRole('button', { name: 'Accept' }).click();
  const committed = await (await committedResponse).json();
  const cert = committed.certificates.find(item => item.kind === 'DISPATCH');
  expect(cert.chosen.action_key).toBe(key);
  expect(committed.executed_routes[cert.cert_id]).toMatchObject({ edge_ids: displayed.edge_ids, path_id: displayed.path_id, graph_fingerprint: displayed.graph_fingerprint });
  expect(committed.state.kpis.waiting).toBeLessThan(before.kpis.waiting);
  await expect(bar).toContainText(cert.cert_id);
  await expect(page.getByText(new RegExp(`LIVE SESSION .* step ${committed.state.current_timestep}/`))).toBeVisible();
  await expect(bar).toContainText(`REVIEWED DECISION · step ${current.certified.timestep}`);
  await expect(page.getByRole('img', { name: /Live certified session:/ }).locator('path[stroke="var(--bad)"]')).toHaveAttribute('d', committed.state.closed_edge_svg_path);
  const exportedResponse = await page.request.get(exportUrl!);
  expect(exportedResponse.ok()).toBeTruthy();
  const exported = await exportedResponse.json();
  expect(exported.export_schema).toBe('sentinel-session-v2');
  expect(exported.provenance.configuration_sha256).toMatch(/^[a-f0-9]{64}$/);
  expect(exported.certificates.find(item => item.cert_id === cert.cert_id)).toEqual(cert);
  expect(exported.certificate_inputs[cert.cert_id].candidates.some(item => `${item.zone_id}->${item.shelter_id}` === key && JSON.stringify(item.edge_ids) === JSON.stringify(displayed.edge_ids))).toBeTruthy();
  const replay = await (await page.request.post(`${sessionUrl}/certificates/${cert.cert_id}/replay`, { data: { tamper: false } })).json();
  expect(replay.result).toBe('MATCH');
  expect(replay.executed_routes[cert.cert_id].edge_ids).toEqual(displayed.edge_ids);
  await page.screenshot({ path: testInfo.outputPath('live-dispatch.png'), fullPage: true });
  await page.request.delete(sessionUrl);
});
