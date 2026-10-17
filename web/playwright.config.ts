import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL: 'http://127.0.0.1:5173' },
  projects: [
    { name: 'mock', testIgnore: /p34[ac]_.*\.spec\.ts/ },
    { name: 'live', testMatch: /p34[ac]_.*\.spec\.ts/ },
  ],
  webServer: process.env.SENTINEL_E2E_LIVE ? [
    {
      command: `${process.env.SENTINEL_PYTHON || 'python'} -m uvicorn src.api.app:create_app --factory --host 127.0.0.1 --port 8000`,
      url: 'http://127.0.0.1:8000/api/health',
      cwd: '..',
      reuseExistingServer: false,
      env: { SENTINEL_DEMO_SOURCE: 'RECORDED', HF_HUB_OFFLINE: '1' },
      timeout: 60_000,
    },
    { command: 'npm run dev', url: 'http://127.0.0.1:5173', reuseExistingServer: false,
      env: { VITE_API_MOCK: '' }, timeout: 60_000 },
  ] : {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    env: { VITE_API_MOCK: '1' },
    timeout: 60_000,
  },
});
