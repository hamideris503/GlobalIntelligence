const { test, expect } = require('@playwright/test');

const ROUTES = [
  'overview','ai-analysis','ai-chat','debate','evaluation','geopolitics','portfolio',
  'evidence','entity-graph','forecasts','risk','decisions','inbox','sources','providers',
  'screening','operations','archive','reports','macro','settings','markets','alerts',
  'world','iran'
];

for (const route of ROUTES) {
  test(`route ${route} renders without console errors`, async ({ page }) => {
    const errors = [];
    page.on('console', (m) => {
      if (m.type() !== 'error') return;
      const u = (m.location() || {}).url || '';
      if (u.includes('favicon')) return;
      errors.push(m.text() + (u ? ' @ ' + u : ''));
    });
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto('/');
    await page.waitForSelector('#dashLive', { timeout: 10000 });
    // navigate via nav
    const nav = page.locator(`[data-page="${route}"]`).first();
    if (await nav.count()) {
      await nav.click();
    } else {
      await page.evaluate((r) => renderPage(r), route);
    }
    await page.waitForTimeout(2500);
    expect(errors, `console errors on ${route}: ${errors.join(' | ')}`).toEqual([]);
  });
}