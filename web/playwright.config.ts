import { defineConfig, devices } from '@playwright/test';

const apiPort = Number(process.env.SENTINEL_API_PORT || 8000);
if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535) throw new Error('Invalid SENTINEL_API_PORT');
const apiUrl = process.env.SENTINEL_API_URL || `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL: 'http://127.0.0.1:5174' },
  projects: [
    { name: 'mock', testIgnore: /p(?:34[ac]|35l)_.*\.spec\.ts/ },
    { name: 'live', testMatch: /p(?:34[ac]|35l)_.*\.spec\.ts/ },
  ],
  webServer: process.env.SENTINEL_E2E_LIVE ? [
    {
      command: `"${process.env.SENTINEL_PYTHON || 'python'}" -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port ${apiPort}`,
      url: `${apiUrl}/api/health`,
      cwd: '..',
      reuseExistingServer: false,
      env: { SENTINEL_DEMO_SOURCE: 'RECORDED', HF_HUB_OFFLINE: '1' },
      timeout: 60_000,
    },
    { command: 'npm run dev -- --port 5174', url: 'http://127.0.0.1:5174', reuseExistingServer: false,
      env: { VITE_API_MOCK: '', SENTINEL_API_URL: apiUrl }, timeout: 60_000 },
  ] : {
    command: 'npm run dev -- --port 5174',
    url: 'http://127.0.0.1:5174',
    reuseExistingServer: false,
    env: { VITE_API_MOCK: '1' },
    timeout: 60_000,
  },
});
