import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const pages: [string, string][] = [['/', 'Incident overview'], ['/evidence', 'Evidence & Results'], ['/system', 'System & Hardware']];

for (const [path, title] of pages) {
  for (const theme of ['Day', 'Night'] as const) {
    test(`${title} ${theme} has no serious or critical axe violations`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: title })).toBeVisible();
      if (await page.locator('[data-theme]').first().getAttribute('data-theme') !== theme) {
        await page.getByRole('button', { name: /theme/i }).click();
      }
      const results = await new AxeBuilder({ page }).analyze();
      const severe = results.violations.filter(item => item.impact === 'serious' || item.impact === 'critical');
      expect(severe.map(item => `${item.id}: ${item.nodes.map(node => node.target.join(' ')).join(', ')}`)).toEqual([]);
    });
  }
}
