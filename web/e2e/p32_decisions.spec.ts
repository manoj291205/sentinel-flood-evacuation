// Phase 32 acceptance (Lead). the Lane X agent copies this file UNCHANGED to web/e2e/p32_decisions.spec.ts.
// Runs against the dev server in mock mode (VITE_API_MOCK=1) on the contract fixtures.
import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/decisions');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Decisions & Certificates');
});

test('lists every fixture certificate, newest first', async ({ page }) => {
  const list = page.getByLabel('Decision list');
  const rows = list.getByRole('button', { name: /^(CERT|AUD)-\d{6}/ });
  await expect(rows).toHaveCount(5);
  await expect(rows.first()).toHaveAccessibleName(/^AUD-000412/);
});

test('detail shows candidates, hash chain and replays MATCH', async ({ page }) => {
  await page.getByRole('button', { name: /^CERT-000127/ }).click();
  const detail = page.getByLabel('Decision detail');
  await expect(detail.getByText('Z-03 → S-04').first()).toBeVisible();
  await expect(detail.getByText(/FEASIBLE/).first()).toBeVisible();
  await expect(detail.getByText('e61a6b4a5ae2')).toBeVisible();
  await expect(detail.getByText('38bfdd3d68c8')).toBeVisible();
  await detail.getByRole('button', { name: 'Replay certificate' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'MATCH' })).toBeVisible();
});

test('tamper demo replays MISMATCH naming the field', async ({ page }) => {
  await page.getByRole('button', { name: /^CERT-000127/ }).click();
  await page.getByLabel('Tamper with forecast (demo)').check();
  await page.getByRole('button', { name: 'Replay certificate' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'MISMATCH' })).toContainText('forecast_hash');
});

test('deep link and kind filter', async ({ page }) => {
  await page.goto('/decisions?cert=CERT-000126');
  await expect(page.getByLabel('Decision detail')).toContainText('MIGRATION');
  await page.getByRole('radiogroup', { name: 'Kind' }).getByRole('radio', { name: 'Migration' }).check();
  await expect(page.getByLabel('Decision list').getByRole('button', { name: /^(CERT|AUD)-\d{6}/ })).toHaveCount(1);
});

test('phone width has no horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
