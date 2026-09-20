import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir:"./e2e", testMatch:"capstone.spec.ts", workers:1, timeout:60_000,
  use:{baseURL:process.env.E2E_BASE_URL||"http://127.0.0.1:3001",channel:"chrome",viewport:{width:1440,height:1000},trace:"retain-on-failure"},
});
