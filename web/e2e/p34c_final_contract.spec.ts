import { expect, test } from '@playwright/test';

test('real operator lifecycle preserves retries, stale review, HOLD, reattach and exports', async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  await page.goto('/live');
  await expect(page.getByText('LIVE ENGINE · ready to start')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run demo' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Start' }).click();
  const bar = page.getByRole('region', { name: 'Operator decides' });
  await expect(bar.getByRole('button', { name: 'Accept' })).toBeEnabled({ timeout: 60_000 });
  const exportUrl = (await page.getByRole('link', { name: 'Download audit JSON' }).getAttribute('href'))!;
  const sessionUrl = exportUrl.replace('/audit.json', '');
  const read = async (path: string) => { const response = await page.request.get(path); expect(response.ok()).toBeTruthy(); return response.json(); };
  const postDecision = async (click: () => Promise<unknown>) => {
    const received = page.waitForResponse(response => response.url().endsWith(`${sessionUrl}/decisions`) && response.request().method() === 'POST');
    await click();
    const response = await received;
    expect(response.ok()).toBeTruthy();
    return { body: response.request().postDataJSON(), receipt: await response.json() };
  };

  const accepted = await postDecision(() => bar.getByRole('button', { name: 'Accept' }).click());
  expect(accepted.receipt.certificates[0].chosen.action_key).toBe('WAIT');
  expect(accepted.receipt.certificates[0].cert_version).toBe('sentinel-cert-v2');
  expect(accepted.receipt.certificates[0].inputs_digest).toMatch(/^[a-f0-9]{64}$/);
  const beforeRetry = await read(`${sessionUrl}/state`);
  const duplicate = await page.request.post(`${sessionUrl}/decisions`, { data: accepted.body });
  expect(duplicate.ok()).toBeTruthy();
  expect(await duplicate.json()).toEqual(accepted.receipt);
  expect(await read(`${sessionUrl}/state`)).toEqual(beforeRetry);

  await bar.getByRole('button', { name: 'Step on' }).click();
  await expect(bar.getByRole('button', { name: 'Override' })).toBeEnabled();
  const reviewed = await read(`${sessionUrl}/context?include_subject=true`);
  const alternative = reviewed.certified.alternatives.find(item => item.certified);
  expect(alternative).toBeTruthy();
  await bar.getByRole('button', { name: 'Override' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox', { name: /Alternative/ }).selectOption(alternative.action_key);
  await dialog.getByRole('radio', { name: 'Road report' }).check();
  await dialog.getByLabel('REASON').fill('Field road report selects the certified alternate');
  const overridden = await postDecision(() => dialog.getByRole('button', { name: 'Confirm override' }).click());
  const cert = overridden.receipt.certificates.find(item => item.kind === 'OVERRIDE');
  expect(cert.cert_version).toBe('sentinel-cert-v2');
  expect(cert.inputs_digest).toMatch(/^[a-f0-9]{64}$/);
  expect(cert.chosen.action_key).toBe(alternative.action_key);
  expect(overridden.receipt.executed_routes[cert.cert_id].edge_ids).toEqual(reviewed.routing.routes[alternative.action_key].edge_ids);
  const reused = await page.request.post(`${sessionUrl}/decisions`, { data: { ...overridden.body, reason: 'Different intent' } });
  expect(reused.status()).toBe(409);

  await dialog.getByRole('button', { name: 'Step on' }).click();
  await expect(bar.getByRole('button', { name: 'Accept' })).toBeEnabled();
  const old = await read(`${sessionUrl}/context?include_subject=true`);
  const external = await page.request.post(`${sessionUrl}/decisions`, { data: {
    ...accepted.body, request_id: crypto.randomUUID(), expected_state_version: old.decision_identity.state_version,
    recommendation_id: old.decision_identity.recommendation_id,
  } });
  expect(external.ok()).toBeTruthy();
  const afterExternal = await read(`${sessionUrl}/certificates`);
  const staleReply = page.waitForResponse(response => response.url().endsWith(`${sessionUrl}/decisions`) && response.status() === 409);
  await bar.getByRole('button', { name: 'Accept' }).click();
  await staleReply;
  await expect(page.getByRole('alert')).toContainText('Review the refreshed state');
  expect((await read(`${sessionUrl}/certificates`)).certificates).toEqual(afterExternal.certificates);

  await bar.getByRole('button', { name: 'Decline' }).click();
  await dialog.getByRole('radio', { name: 'Road report' }).check();
  await dialog.getByLabel('REASON').fill('Hold until a new field report arrives');
  const held = await postDecision(() => dialog.getByRole('button', { name: 'Confirm decline' }).click());
  expect(held.body.decision).toBe('REJECT');
  const holdCert = held.receipt.certificates.find(item => item.kind === 'HOLD');
  expect(holdCert.chosen.action_key).toBe('WAIT');
  expect(holdCert.cert_version).toBe('sentinel-cert-v2');
  expect(holdCert.inputs_digest).toMatch(/^[a-f0-9]{64}$/);
  expect(holdCert.commands).toEqual([]);
  await expect(dialog.getByText('HOLD: no dispatch this step', { exact: true })).toBeVisible();
  await expect(page.getByText(/LIVE SESSION .*4 decisions/)).toBeVisible();
  const exported = await read(exportUrl);
  expect(exported.audit).toHaveLength(4);
  expect(exported.audit.map(item => item.decision)).toEqual(['ACCEPT', 'OVERRIDE', 'ACCEPT', 'REJECT']);
  expect(exported.audit.map(item => item.timestep)).toEqual([0, 1, 2, 3]);
  expect(exported.request_history.filter(item => item.status === 200)).toHaveLength(4);
  expect(exported.certificate_inputs[cert.cert_id]).toBeTruthy();
  expect(exported.certificates.every(item => item.cert_version === 'sentinel-cert-v2' && /^[a-f0-9]{64}$/.test(item.inputs_digest))).toBeTruthy();
  const replay = await page.request.post(`${sessionUrl}/certificates/${cert.cert_id}/replay`, { data: { tamper: false } });
  expect((await replay.json()).result).toBe('MATCH');
  expect((await page.request.get(`${sessionUrl}/audit.csv`)).ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText(new RegExp(`LIVE SESSION .* step ${held.receipt.state.current_timestep}/`))).toBeVisible({ timeout: 60_000 });
  await expect(bar.getByRole('button', { name: 'Accept' })).toBeEnabled({ timeout: 60_000 });
  await page.getByRole('tab', { name: 'Decisions log' }).click();
  await expect(page.getByRole('region', { name: 'Decisions log' })).toContainText(holdCert.cert_id);
  await page.screenshot({ path: testInfo.outputPath('real-lifecycle.png'), fullPage: true });
  page.once('dialog', confirm => confirm.accept());
  await page.getByRole('button', { name: 'End', exact: true }).click();
  await expect(page.getByText('LIVE ENGINE · ready to start')).toBeVisible();
  expect((await page.request.get(`${sessionUrl}/state`)).status()).toBe(404);
  await page.reload();
  await expect(page.getByRole('button', { name: 'Start' })).toBeVisible();
});
