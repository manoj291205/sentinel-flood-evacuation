import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const cli = new URL('../node_modules/@playwright/test/cli.js', import.meta.url);
const result = spawnSync(process.execPath, [fileURLToPath(cli), 'test', '--project=live', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: { ...process.env, SENTINEL_E2E_LIVE: '1' },
});
process.exit(result.status ?? 1);
