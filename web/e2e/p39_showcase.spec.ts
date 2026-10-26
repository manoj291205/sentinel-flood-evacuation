import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

test('live command dialog records accept, override, refusal and decline', async ({ page }) => {
  await page.goto('/live');
  await page.getByRole('radiogroup', { name: 'Mode' }).getByRole('radio', { name: 'Live session' }).check();
  await page.getByRole('button', { name: 'Start' }).click();
  const bar = page.getByRole('region', { name: 'Operator decides' });
  await expect(bar).toContainText('HOLD');
  await bar.getByRole('button', { name: 'Override' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Suggested: HOLD');
  await dialog.getByRole('button', { name: 'Accept' }).click();
  await expect(dialog.getByRole('link', { name: 'CERT-000001' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Step on' }).click();
  await bar.getByRole('button', { name: 'Override' }).click();
  await expect(dialog).toContainText('Certified lower bound 0.940');
  await dialog.getByRole('radio', { name: 'Road report' }).check();
  await dialog.getByLabel('REASON').fill('Road report from team');
  await dialog.getByRole('button', { name: 'Confirm override' }).click();
  await expect(dialog.getByRole('link', { name: 'CERT-000002' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Step on' }).click();
  await bar.getByRole('button', { name: 'Override' }).click();
  await dialog.getByRole('button', { name: 'Test gate refusal (demo)' }).click();
  await expect(dialog.getByRole('alert')).toContainText('Gate refused: not certified');
  await dialog.getByRole('button', { name: 'Decline' }).click();
  await dialog.getByRole('radio', { name: 'Road report' }).check();
  await dialog.getByLabel('REASON').fill('Decline after road report');
  await dialog.getByRole('button', { name: 'Confirm decline' }).click();
  await expect(dialog.getByRole('link', { name: 'CERT-000003' })).toBeVisible();
  await dialog.getByRole('button', { name: 'Step on' }).click();
  await expect(page.getByRole('heading', { name: 'Episode ended — horizon reached' })).toBeVisible();
  await expect(page.getByText('Overrides 1 · declines 1 · gate refusals 1')).toBeVisible();
  await expect(page.getByText(/Certificates by kind:/)).toBeVisible();
  await expect(page.getByText(/Certificates by kind:/)).toContainText('OVERRIDE 1');
});

for (const path of ['/', '/live', '/simulations', '/decisions', '/evidence', '/system', '/journey']) {
  test(`new console accessibility: ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole('main')).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}

test('recorded replay offers all speeds, compare summary, and advances the showcase', async ({ page }) => {
  test.skip(process.env.SENTINEL_E2E_LIVE !== '1', 'Requires the frozen local Phase 27 artifacts');
  await page.goto('/simulations');
  await expect(page.getByText('1260', { exact: true })).toBeVisible({ timeout: 60_000 });
  for (const speed of ['1×', '2×', '3×', '5×', '10×']) {
    await page.getByRole('button', { name: speed }).click();
    await expect(page.getByRole('button', { name: speed })).toHaveAttribute('aria-pressed', 'true');
  }
  await expect(page.getByRole('heading', { name: 'A2', exact: true })).toBeVisible();
  await expect(page.getByText('222', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: /Run-all showcase/ }).click();
  await expect(page.getByText(/SHOWCASE · v4-medium-dt2-v1/)).toBeVisible();
  await expect(page.getByText(/t=1 ·/)).toBeVisible({ timeout: 10_000 });
});

test('capture Phase 39 review pages', async ({ page }) => {
  test.skip(process.env.SENTINEL_CAPTURE_LX39 !== '1', 'One-time self-audit capture');
  test.setTimeout(180_000);
  const directory = path.resolve('../docs/course/LX39_shots');
  await mkdir(directory, { recursive: true });
  for (const [name, route] of [['overview', '/'], ['live', '/live'], ['simulations', '/simulations'], ['decisions', '/decisions'], ['evidence', '/evidence'], ['system', '/system'], ['journey', '/journey']]) {
    await page.goto(route);
    await expect(page.getByRole('main')).toBeVisible();
    if (route === '/simulations') {
      await expect(page.getByRole('region', { name: 'Recorded simulation replay' })).toBeVisible();
      await expect(page.getByText('1260', { exact: true })).toBeVisible({ timeout: 60_000 });
    }
    if (route === '/live') {
      await page.getByRole('radiogroup', { name: 'Mode' }).getByRole('radio', { name: 'Live session' }).check();
      await page.getByRole('button', { name: 'Start' }).click();
      await page.getByRole('region', { name: 'Operator decides' }).getByRole('button', { name: 'Override' }).click();
      await expect(page.getByRole('dialog')).toBeVisible({ timeout: 90_000 });
      await page.screenshot({ path: path.join(directory, 'live-modal.png'), fullPage: false, animations: 'disabled' });
      await page.keyboard.press('Escape');
    }
    await page.screenshot({ path: path.join(directory, `${name}.png`), fullPage: true, animations: 'disabled' });
  }
});
