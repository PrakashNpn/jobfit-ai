import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
    // Locally, reuse the installed Chrome; CI installs Playwright's own Chromium.
    ...(process.env.CI ? {} : { channel: "chrome" }),
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    // The API is mocked in every test, so point the app at an address nothing listens on.
    command: `npm run build && npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    env: { NEXT_PUBLIC_API_URL: "http://localhost:8999", NEXT_DIST_DIR: ".next-e2e" },
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
