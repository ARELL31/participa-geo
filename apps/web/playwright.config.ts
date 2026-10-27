import { defineConfig, devices } from "@playwright/test";

/**
 * The E2E suite runs against the real stack through the web (same-origin nginx)
 * proxy. It never mocks the API: start `docker compose up -d db geoserver api web`
 * before `npm run test:e2e`.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:8080",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
