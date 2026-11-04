import {defineConfig} from '@playwright/test';
export default defineConfig({
 testDir:'./e2e',testMatch:'ledger-ranking-presentation.spec.ts',timeout:120_000,workers:1,
 use:{baseURL:process.env.E2E_REPLAY_URL??'http://127.0.0.1:3111',channel:'chrome',trace:'off',video:'off'},
 outputDir:process.env.E2E_REPLAY_OUTPUT??'../.work/ledger-ranking-ui/browser-results',
});
