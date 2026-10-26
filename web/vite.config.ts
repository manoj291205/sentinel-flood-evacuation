import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: process.env.VITE_API_MOCK === '1' ? undefined : { '/api': process.env.SENTINEL_API_URL || 'http://localhost:8000',
      '/ws': { target: (process.env.SENTINEL_API_URL || 'http://localhost:8000').replace(/^http/, 'ws'), ws: true } },
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    css: true,
    exclude: ['e2e/**', '**/node_modules/**'],
  },
});
