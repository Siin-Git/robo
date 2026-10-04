import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',testMatch:'strategy-comparison.spec.ts',workers:1,timeout:120_000,
  expect:{timeout:20_000},outputDir:process.env.E2E_OUTPUT_DIR??'/private/tmp/robo-strategy-comparison-browser',
  use:{baseURL:process.env.E2E_BASE_URL??'http://127.0.0.1:3091',channel:'chrome',trace:'off',video:'off'},
});
