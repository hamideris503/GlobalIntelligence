import { defineConfig } from "@playwright/test";

import { resolveLoopbackPort } from "./e2e/test-ports";

/** Full-stack E2E: real UI + real FastAPI app + throwaway test DB (no mocks).
 *
 * Two servers, both local: `e2e/fullstack-server.py` runs the project's own app
 * with a fake API key, SQLite inside `.e2e-fullstack/`, MOCK_MODE=true and a
 * fail-closed outbound socket guard; Vite serves the real frontend with
 * VITE_API_BASE_URL pointing at it. Nothing outside localhost is contacted.
 * Run with: npm run test:e2e:fullstack
 *
 * Ports: the API stays on 127.0.0.1:8010 (free on a normal machine; the spec
 * pins it). The frontend port is `E2E_FRONTEND_PORT` (default 4174, loopback
 * only) and is handed to the API process so its CORS allow-list matches the
 * origin the browser really uses — the list stays explicit, never `*`.
 */
const API_PORT = 8010;
const frontendPort = resolveLoopbackPort("E2E_FRONTEND_PORT", 4174);
const frontendOrigin = `http://127.0.0.1:${frontendPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/fullstack.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL: frontendOrigin,
    headless: true,
  },
  webServer: [
    {
      command: "python e2e/fullstack-server.py",
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { E2E_FRONTEND_PORT: String(frontendPort) },
    },
    {
      command: `npm run dev -- --port ${frontendPort} --strictPort --host 127.0.0.1`,
      url: frontendOrigin,
      env: { VITE_API_BASE_URL: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
