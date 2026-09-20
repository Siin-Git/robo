import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir:"./e2e", testMatch:"enrollment.spec.ts", workers:1, timeout:180_000, expect:{timeout:15_000},
  outputDir:process.env.E2E_OUTPUT_DIR||"/private/tmp/robo-enrollment-browser-results",
  // New credentials must not be recorded in traces or video.
  use:{baseURL:process.env.E2E_BASE_URL||"http://127.0.0.1:3012",channel:"chrome",viewport:{width:1440,height:1000},trace:"off",video:"off"},
});
