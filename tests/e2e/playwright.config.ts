import { defineConfig, devices } from "@playwright/test";

/**
 * Acceptance suite for the institutional MVP.
 *
 * It runs inside the `e2e` Compose service against the real stack (PostGIS,
 * API, nginx and GeoServer) through `http://web:80`. MSW is never used here.
 * The service mounts this directory at `/app/tests/e2e`, so the suite shares
 * the pinned Playwright/Chromium dependencies from the web image.
 *
 * One worker keeps peak memory compatible with an ~8 GB host and the single
 * PostgreSQL/GeoServer stack.
 */
export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: [["list"]],
  outputDir: "/tmp/participa-geo-playwright-results",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
