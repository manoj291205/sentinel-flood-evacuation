// Phase 33 acceptance (Lead). the Lane X agent copies this file UNCHANGED to web/e2e/p33_pages.spec.ts.
// Mock mode: evidence comes from specs/contracts/evidence_manifest.json with every value null,
// system status from specs/contracts/system_status_fixture.json.
import { expect, test } from '@playwright/test';

const HONESTY = 'REAL ROAD TOPOLOGY · SIMULATED DISASTER CONDITIONS · NOT OPERATIONALLY VALIDATED';
const PAGES: [string, string][] = [
  ['/', 'Incident overview'],
  ['/evidence', 'Evidence & Results'],
  ['/system', 'System & Hardware'],
];

for (const [path, title] of PAGES) {
  test(`${title}: heading, honesty banner, no horizontal scroll at 390 px`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title);
    await expect(page.getByText(HONESTY)).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test('overview sections and links to certificates', async ({ page }) => {
  await page.goto('/');
  for (const name of ['Population ledger', 'Shelters', 'Dispatch gate activity', 'System health', 'Latest certificates']) {
    await expect(page.getByRole('heading', { name })).toBeVisible();
  }
  await page.getByRole('link', { name: /CERT-000128/ }).first().click();
  await expect(page).toHaveURL(/\/decisions\?cert=CERT-000128/);
});

test('evidence shows a dash with a reason when an artifact is absent', async ({ page }) => {
  await page.goto('/evidence');
  await expect(page.getByRole('heading', { name: 'Pre-registered evaluation (Phase 27)' })).toBeVisible();
  const row = page.getByRole('row', { name: /Pre-registered evaluation \(D-27\)/ });
  await expect(row).toContainText('-');
  await expect(row).toContainText('data/eval_results/phase27/analysis.json');
});

test('system page lists devices and MQTT topics', async ({ page }) => {
  await page.goto('/system');
  await expect(page.getByRole('heading', { name: 'Devices' })).toBeVisible();
  await expect(page.getByText('sim-shelter-01')).toBeVisible();
  await expect(page.getByText('sentinel/v1/shelter/+/occupancy')).toBeVisible();
  await expect(page.getByText('No commands yet')).toBeVisible();
});
