import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

for (const theme of ['Day', 'Night'] as const) {
  test(`${theme} Live Operations has no serious or critical accessibility violations`, async ({ page }) => {
    await page.goto('/live');
    await expect(page.getByRole('heading', { name: 'Live Operations' })).toBeVisible();
    const app = page.locator('[data-theme]').first();
    if (await app.getAttribute('data-theme') !== theme) {
      await page.getByRole('button', { name: /theme/i }).click();
    }
    const results = await new AxeBuilder({ page }).analyze();
    const severe = results.violations.filter(item => item.impact === 'serious' || item.impact === 'critical');
    expect(severe.map(item => `${item.id}: ${item.nodes.map(node => `${node.target.join(' ')} ${node.failureSummary}`).join(' | ')}`)).toEqual([]);
    await page.screenshot({ path: `test-results/live-${theme.toLowerCase()}.png`, fullPage: true });
  });
}

test('phone Live Operations accessibility and layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/live');
  await expect(page.getByRole('heading', { name: 'Live Operations' })).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  const severe = results.violations.filter(item => item.impact === 'serious' || item.impact === 'critical');
  expect(severe.map(item => `${item.id}: ${item.nodes.map(node => `${node.target.join(' ')} ${node.failureSummary}`).join(' | ')}`)).toEqual([]);
  await page.screenshot({ path: 'test-results/live-phone.png', fullPage: true });
});
