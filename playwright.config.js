// Minimal Playwright E2E config for GlobalIntelligence UI.
//
// Local setup used here (no `npx playwright install` needed):
//   1. A Chromium build was downloaded manually and unpacked into ./chrome-win64/
//      (gitignored). `launchOptions.executablePath` points Playwright at it.
//   2. The Playwright CLI is resolved from the npx cache; run tests with:
//        NODE_PATH=%LOCALAPPDATA%/npm-cache/_npx/<hash>/node_modules npx playwright test
//      or install locally once network allows:
//        npm install --save-dev @playwright/test
//
// Prereq: backend running on 127.0.0.1:18100 with a SQLite DB whose schema was
// created from the models (MOCK_MODE=true, API_KEY empty).
module.exports = {
  testDir: './tests/e2e',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:18100',
    headless: true,
    viewport: { width: 1280, height: 800 },
    launchOptions: {
      executablePath: './chrome-win64/chrome.exe',
    },
  },
  reporter: [['list']],
};
