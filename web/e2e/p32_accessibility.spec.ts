import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

for (const theme of ['Day', 'Night'] as const) {
  test(`${theme} Decisions page has no severe accessibility violations`, async ({ page }) => {
    await page.goto('/decisions');
    await expect(page.getByRole('heading', { name: 'Decisions & Certificates' })).toBeVisible();
    await expect(page.getByLabel('Decision detail').getByRole('heading', { name: 'Options the gate checked' })).toBeVisible();
    if (await page.locator('[data-theme]').first().getAttribute('data-theme') !== theme) {
      await page.getByRole('button', { name: /theme/i }).click();
    }
    const results = await new AxeBuilder({ page }).analyze();
    const severe = results.violations.filter(item => item.impact === 'serious' || item.impact === 'critical');
    expect(severe.map(item => `${item.id}: ${item.nodes.map(node => node.target.join(' ')).join(', ')}`)).toEqual([]);
  });
}
