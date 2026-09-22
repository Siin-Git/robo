import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir:"./e2e", testMatch:"lab-meeting.spec.ts", workers:1, timeout:240_000, expect:{timeout:30_000},
  outputDir:process.env.E2E_OUTPUT_DIR || "/private/tmp/robo-lab-browser-results",
  use:{baseURL:process.env.E2E_BASE_URL, channel:"chrome", viewport:{width:1440,height:1000},actionTimeout:20_000,trace:"off",video:"off"},
});
