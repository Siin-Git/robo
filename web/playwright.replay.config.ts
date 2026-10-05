import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./e2e',testMatch:'competition-replay.spec.ts',timeout:120_000,workers:1,
 use:{baseURL:process.env.E2E_REPLAY_URL??'http://127.0.0.1:3097',channel:'chrome',trace:'off',video:'off'},
 outputDir:process.env.E2E_REPLAY_OUTPUT??'/private/tmp/robo-replay-e2e',
});
