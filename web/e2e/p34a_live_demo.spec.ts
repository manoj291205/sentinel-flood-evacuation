// Phase 34A acceptance (Lead). the Lane X agent copies this file UNCHANGED to web/e2e/p34a_live_demo.spec.ts.
// Runs only in the Playwright project "live" (`npm run test:e2e:live`): real FastAPI with SENTINEL_DEMO_SOURCE=RECORDED
// and the Vite dev server WITHOUT VITE_API_MOCK. Data = the recorded run of the real engine (v4-demo-trace-v1:
// v4-medium-dt2-v1, seed 620003, v4-cert-test-v1). CERT-000001 is the epoch-0 HOLD, CERT-000002 the first DISPATCH.
import { expect, test } from '@playwright/test';

test.setTimeout(120_000);

test('Run demo plays six recorded steps from the real engine', async ({ page }) => {
  await page.goto('/live');
  await page.getByRole('radio', { name: 'Guided demo' }).check();
  await expect(page.getByText(/Recorded run of the real engine/)).toBeVisible();
  await expect(page.getByText(/not a performance sample/)).toBeVisible();
  await expect(page.getByText('scripted preview')).toHaveCount(0);
  await page.getByRole('button', { name: 'Run demo' }).click();
  await expect(page.getByText('Step 6 / 6')).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole('button', { name: 'Replay demo' })).toBeVisible({ timeout: 15_000 });
});

test('a real certificate replays MATCH and the tampered copy MISMATCH', async ({ page }) => {
  await page.goto('/decisions');
  const rows = page.getByLabel('Decision list').getByRole('button', { name: /^CERT-\d{6}/ });
  await expect(rows.first()).toBeVisible();
  expect(await rows.count()).toBeGreaterThanOrEqual(6);
  await page.getByRole('button', { name: /^CERT-000002/ }).click();
  const detail = page.getByLabel('Decision detail');
  await expect(detail).toContainText('DISPATCH');
  await detail.getByRole('button', { name: 'Replay certificate' }).click();
  await expect(page.getByRole('status').filter({ hasText: /^MATCH/ })).toBeVisible({ timeout: 60_000 });
  await page.getByLabel('Tamper with forecast (demo)').check();
  await detail.getByRole('button', { name: 'Replay certificate' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'MISMATCH' })).toContainText('forecast_hash', { timeout: 60_000 });
});

test('why panel shows reasons derived from the certificate', async ({ page }) => {
  await page.goto('/decisions?cert=CERT-000002');
  await expect(page.getByText(/Certified lower bound \d\.\d{3}/)).toBeVisible();
  await page.goto('/decisions?cert=CERT-000001');
  await expect(page.getByLabel('Decision detail')).toContainText('HOLD');
  await expect(page.getByText(/No dispatch option reached the threshold/)).toBeVisible();
});

test('rule tiers come from the P15T2 run and 14D is the evaluation of record', async ({ page }) => {
  await page.goto('/evidence');
  const table = page.getByRole('table', { name: /^Document rules/ });
  await expect(table.getByRole('row', { name: /NDMA-R01/ })).toContainText('T1');
  await expect(table.getByRole('row', { name: /NDMA-R02/ })).toContainText('T1');
  await expect(table.getByText('T2', { exact: true })).toHaveCount(0);
  await expect(page.getByText(/evaluation of record/).first()).toBeVisible();
  await expect(page.getByText('1.531')).toBeVisible();
  await expect(page.getByText('21.4 %')).toBeVisible();
});
