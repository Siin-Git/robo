import {defineConfig} from "@playwright/test";
export default defineConfig({
  testDir:"./e2e", workers:1, timeout:180_000, expect:{timeout:15_000},
  testMatch:process.env.NEXT_PUBLIC_CAPSTONE_DEMO === "1"
    ? ["capstone.spec.ts", "enrollment.spec.ts", "unified-design.spec.ts"] : "unified-design.spec.ts",
  outputDir:process.env.E2E_OUTPUT_DIR,
  use:{baseURL:process.env.E2E_BASE_URL, channel:"chrome", viewport:{width:1440,height:1000}, trace:"off", video:"off"},
});
