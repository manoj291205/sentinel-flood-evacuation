// Phase 35-lite acceptance (Lead). the Lane X agent copies this file UNCHANGED to web/e2e/p35l_network.spec.ts.
// Runs only in the Playwright project "live" (`npm run test:e2e:live`): real FastAPI + Vite without VITE_API_MOCK.
// Exploratory simulated network outage with two field teams; never presented as an outcome improvement.
import { expect, test } from '@playwright/test';

test.setTimeout(180_000);

async function startNetworkDemo(page, escrow: 'With escrow' | 'Without escrow') {
  await page.goto('/live');
  await page.getByRole('radiogroup', { name: 'Mode' }).getByRole('radio', { name: 'Live session' }).check();
  await page.getByLabel('Two-team network demo').check();
  await page.getByRole('radiogroup', { name: 'Escrow' }).getByRole('radio', { name: escrow }).check();
  await page.getByLabel('Seed').fill('620003');
  await page.getByLabel('World').selectOption('v4-medium-dt2-v1');
  await page.getByRole('button', { name: 'Start' }).click();
  const network = page.getByLabel('Network');
  await expect(network).toContainText('ONLINE', { timeout: 60_000 });
  return network;
}

test('cut, offline step with per-team seats, restore and rebalance (with escrow)', async ({ page }) => {
  const network = await startNetworkDemo(page, 'With escrow');
  await network.getByRole('button', { name: 'Cut network' }).click();
  await expect(network).toContainText('OFFLINE', { timeout: 60_000 });
  await expect(page.getByText('Simulated network outage').first()).toBeVisible();
  await expect(network.getByText(/TEAM-A: \d+ of \d+ seats left/)).toBeVisible();
  await expect(network.getByText(/TEAM-B: \d+ of \d+ seats left/)).toBeVisible();
  await page.getByRole('button', { name: 'Step on' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 90_000 });
  await network.getByRole('button', { name: 'Restore network' }).click();
  await expect(network).toContainText('ONLINE', { timeout: 60_000 });
  await expect(network.getByText(/Rebalanced: \d+ seats back to the pool · overbooked seats: 0/)).toBeVisible();
  await expect(page.getByText('Simulated network outage')).toHaveCount(0);
});

test('without escrow the comparison mode reports overbooked seats as a count', async ({ page }) => {
  const network = await startNetworkDemo(page, 'Without escrow');
  await network.getByRole('button', { name: 'Cut network' }).click();
  await expect(network).toContainText('OFFLINE', { timeout: 60_000 });
  await page.getByRole('button', { name: 'Step on' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Certifying…' })).toHaveCount(0, { timeout: 90_000 });
  await network.getByRole('button', { name: 'Restore network' }).click();
  await expect(network.getByText(/overbooked seats: \d+/)).toBeVisible({ timeout: 60_000 });
});

test('evidence shows the exploratory outage items with their note', async ({ page }) => {
  await page.goto('/evidence');
  await expect(page.getByText('Exploratory: network outage (not pre-registered)')).toBeVisible();
  await expect(page.getByText(/Exploratory — not pre-registered/)).toBeVisible();
  await expect(page.getByText('Outages with overbooked seats, with escrow')).toBeVisible();
});
