import { defineConfig } from "@playwright/test";

import { resolveLoopbackPort } from "./e2e/test-ports";

/** Local-only E2E: real page in Chromium, all /api/* mocked, external net
 * blocked in-spec. No backend, no network, no secrets. Prod build served.
 *
 * Frontend port: `E2E_FRONTEND_PORT` (default 4173). If the port is reserved by
 * the OS or already busy, the config fails fast with an actionable message
 * instead of a bare `listen EACCES`. Bind is loopback-only.
 */
const frontendPort = resolveLoopbackPort("E2E_FRONTEND_PORT", 4173);

export default defineConfig({
  testDir: "./e2e",
  testMatch: [
    "**/settings-models.spec.ts",
    "**/news-priority.spec.ts",
    "**/screening-ops.spec.ts",
  ],
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    headless: true,
  },
  webServer: {
    command: `npx vite preview --port ${frontendPort} --strictPort --host 127.0.0.1`,
    url: `http://127.0.0.1:${frontendPort}`,
    reuseExistingServer: true,
    timeout: 60000,
  },
});
