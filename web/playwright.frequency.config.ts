import { defineConfig } from "@playwright/test";

// Start the isolated Monday launcher first. Never reuse an operating DB.
export default defineConfig({
  testDir: "./e2e", testMatch: "initial-rebalance.spec.ts", workers: 1, timeout: 90_000,
  outputDir: process.env.E2E_OUTPUT_DIR ?? "/private/tmp/robo-frequency-results",
  expect: {timeout:20_000},
  use: {baseURL:process.env.E2E_BASE_URL ?? "http://127.0.0.1:3083",channel:"chrome",trace:"off",video:"off"},
});
