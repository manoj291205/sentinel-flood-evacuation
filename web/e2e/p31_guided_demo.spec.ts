// Phase 31 acceptance (Lead). the Lane X agent copies this file UNCHANGED to web/e2e/p31_guided_demo.spec.ts.
// Runs against the dev server in mock mode (VITE_API_MOCK=1) or against the real API in fixture mode.
import { expect, test } from '@playwright/test';

const HONESTY = 'REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED';

test.beforeEach(async ({ page }) => {
  await page.goto('/live');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Live Operations');
});

test('shell: five nav entries and the honesty banner', async ({ page }) => {
  const nav = page.getByRole('navigation', { name: 'Main' });
  for (const name of ['Overview', 'Live Operations', 'Decisions & Certificates', 'Evidence & Results', 'System & Hardware']) {
    await expect(nav.getByRole('link', { name })).toBeVisible();
  }
  await expect(nav.getByRole('link')).toHaveCount(5);
  await expect(page.getByText(HONESTY)).toBeVisible();
});

test('guided demo: manual walk shows suggestions, blocking, HOLD and certificates', async ({ page }) => {
  await page.getByRole('button', { name: 'Reset' }).click();
  await expect(page.getByText('Step 1 / 6')).toBeVisible();
  await expect(page.getByText('WHY THIS SUGGESTION')).toBeVisible();

  await page.getByRole('button', { name: 'Next step' }).click();
  await page.getByRole('button', { name: 'Next step' }).click();
  await expect(page.getByText('Step 3 / 6')).toBeVisible();
  await expect(page.getByRole('button', { name: /Z-02 → S-05 · 40.*UNDECIDED/ })).toBeVisible();
  await page.getByRole('button', { name: 'Accept', exact: true }).click();
  await expect(page.getByText('CERT-000127')).toBeVisible();

  await page.getByRole('button', { name: 'Next step' }).click();
  await expect(page.getByRole('status').filter({ hasText: '512' })).toBeVisible();

  await page.getByRole('button', { name: 'Next step' }).click();
  await expect(page.getByText('HOLD Zone 04')).toBeVisible();
});

test('override requires a reason', async ({ page }) => {
  await page.getByRole('button', { name: 'Reset' }).click();
  await page.getByRole('button', { name: 'Next step' }).click();
  await page.getByRole('button', { name: 'Next step' }).click();
  await page.getByRole('button', { name: 'Override', exact: true }).click();
  const reason = page.getByLabel(/REASON/);
  await expect(reason).toBeVisible();
  await expect(reason).toHaveAttribute('required', '');
});

test('run demo auto-plays to the last step', async ({ page }) => {
  test.setTimeout(90_000);
  await page.getByRole('button', { name: 'Reset' }).click();
  await page.getByRole('button', { name: 'Run demo' }).click();
  await expect(page.getByText('Step 6 / 6')).toBeVisible({ timeout: 75_000 });
  await expect(page.getByRole('button', { name: 'Replay demo' })).toBeVisible({ timeout: 10_000 });
});

test('day / night theme toggle', async ({ page }) => {
  const app = page.locator('[data-theme]').first();
  const before = await app.getAttribute('data-theme');
  await page.getByRole('button', { name: /theme/i }).click();
  await expect(app).not.toHaveAttribute('data-theme', before ?? '');
});

test('phone width has no horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
