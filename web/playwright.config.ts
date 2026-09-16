import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: "http://localhost:3000",
    ...devices["Desktop Chrome"],
    channel: undefined,
  },
  webServer: {
    command: "node \"C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js\" run dev",
    url: "http://localhost:3000/login",
    timeout: 180_000,
    reuseExistingServer: true,
    env: {
      FASTAPI_INTERNAL_URL: process.env.FASTAPI_INTERNAL_URL ?? "http://127.0.0.1:8000",
    },
  },
});
