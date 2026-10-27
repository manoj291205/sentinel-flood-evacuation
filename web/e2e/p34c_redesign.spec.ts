import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const pages = [
  ['overview', '/', 'Incident overview'],
  ['live', '/live', 'Live Operations'],
  ['simulations', '/simulations', 'Simulation library'],
  ['decisions', '/decisions', 'Decisions & Certificates'],
  ['evidence', '/evidence', 'Evidence & Results'],
  ['system', '/system', 'System & Hardware'],
  ['journey', '/journey', 'How it was built'],
] as const;

for (const width of [1440, 1280, 768, 390]) {
  for (const [name, route, title] of pages) {
    test(`${name} at ${width}px preserves readable controls in both themes`, async ({ page }, testInfo) => {
      test.setTimeout(90_000);
      await page.setViewportSize({ width, height: width < 600 ? 844 : 1000 });
      await page.goto(route);
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
      if (route === '/live') {
        await page.getByRole('button', { name: 'Start', exact: true }).click();
        await expect(page.getByRole('region', { name: 'Operator decides' })).toContainText('HOLD', { timeout: 60_000 });
      }
      if (route === '/simulations') await expect(page.getByRole('region', { name: 'Recorded simulation replay' })).toBeVisible();
      if (route === '/decisions') await expect(page.getByRole('heading', { name: 'Certificate & bit-exact replay' })).toBeVisible();
      if (route === '/evidence') await expect(page.getByRole('table', { name: 'Document rules (Phase 15 tiers)' })).toBeVisible();
      if (route === '/system') await expect(page.getByRole('heading', { name: 'MQTT topics' })).toBeVisible();
      for (const theme of ['Night', 'Day']) {
        if (await page.locator('[data-theme]').getAttribute('data-theme') !== theme) {
          await page.getByRole('button', { name: /Switch Day or Night theme/ }).click();
        }
        await expect(page.getByRole('note')).toContainText('NOT OPERATIONALLY VALIDATED');
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
        for (const link of await page.getByRole('navigation', { name: 'Main', exact: true }).getByRole('link').all()) await expect(link).toBeVisible();
        const results = await new AxeBuilder({ page }).analyze();
        expect(results.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => ({ target: node.target, failure: node.failureSummary })) }))).toEqual([]);
        if (route === '/live') {
          const bar = page.getByRole('region', { name: 'Operator decides' });
          for (const action of ['Accept', 'Override', 'Decline']) {
            const button = bar.getByRole('button', { name: action, exact: true });
            await expect(button).toBeEnabled();
            const bounds = await button.boundingBox();
            expect(bounds && bounds.width >= 44 && bounds.height >= 44).toBeTruthy();
          }
        }
        await page.getByRole('heading', { name: title, exact: true }).scrollIntoViewIfNeeded();
        await page.screenshot({ path: testInfo.outputPath(`${name}-${width}-${theme}.png`), animations: 'disabled' });
      }
    });
  }
}

test('phone operator dialog keeps reasons and all three decisions reachable', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/live');
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  const bar = page.getByRole('region', { name: 'Operator decides' });
  await expect(bar).toContainText('HOLD', { timeout: 60_000 });
  await bar.getByRole('button', { name: 'Decline', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel('REASON', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Confirm decline' })).toBeDisabled();
  await dialog.getByRole('radio', { name: 'Road report' }).check();
  await dialog.getByLabel('REASON', { exact: true }).fill('Route review from field team');
  await expect(dialog.getByRole('button', { name: 'Confirm decline' })).toBeEnabled();
  for (const action of ['Accept', 'Override', 'Decline']) {
    const button = dialog.getByRole('button', { name: action, exact: true });
    await button.scrollIntoViewIfNeeded();
    await expect(button).toBeEnabled();
    const bounds = await button.boundingBox();
    expect(bounds && bounds.x >= 0 && bounds.x + bounds.width <= 391 && bounds.height >= 44).toBeTruthy();
    expect(await button.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      const hit = document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
      return hit === element || (hit !== null && element.contains(hit));
    })).toBe(true);
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('phone-decision-dialog.png'), animations: 'disabled' });
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(bar.getByRole('button', { name: 'Decline', exact: true })).toBeFocused();
});
