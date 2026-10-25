import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: './e2e', testMatch: 'investment-rehearsal.spec.ts', workers: 1, timeout: 120_000,
  expect: {timeout: 15_000}, outputDir: process.env.E2E_OUTPUT_DIR,
  use: {baseURL: process.env.E2E_BASE_URL, channel: 'chrome', viewport: {width: 1440, height: 1050}, trace: 'off', video: 'off'},
});
