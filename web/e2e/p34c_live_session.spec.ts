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
  await expect(page.getByRole('link', { name: /CERT-000001/ })).toBeVisible({ timeout: 60_000 });
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
  await expect(page.getByRole('link', { name: /CERT-000001/ })).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: 'Step on' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 60_000 });
  await page.getByRole('button', { name: 'Override' }).click();
  const reason = page.getByLabel(/REASON/);
  await expect(reason).toHaveAttribute('required', '');
  await reason.fill('field team reports the preferred road is busy');
  await page.getByRole('button', { name: /Confirm override/ }).click();
  await expect(page.getByRole('link', { name: /CERT-000002/ })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/OVERRIDE/).first()).toBeVisible();
  await page.getByRole('link', { name: /CERT-000002/ }).click();
  await expect(page.getByLabel('Decision detail')).toContainText(/OVERRIDE|HOLD/);
});
