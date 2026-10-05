import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./e2e',testMatch:'internal-tracking.spec.ts',timeout:120_000,workers:1,
 use:{baseURL:process.env.E2E_TRACKING_URL??'http://127.0.0.1:3103',channel:'chrome',trace:'off',video:'off'},
 outputDir:process.env.E2E_TRACKING_OUTPUT??'/private/tmp/robo-internal-tracking-e2e',
});
