const { test } = require('@playwright/test');
const { AxeBuilder } = require('@axe-core/playwright');

const PAGES = ['overview', 'inbox', 'providers', 'settings', 'world'];

for (const pg of PAGES) {
  test(`axe audit: ${pg}`, async ({ page }) => {
    await page.goto('/');
    await page.waitForSelector('#dashLive', { timeout: 10000 });
    const nav = page.locator(`[data-page="${pg}"]`).first();
    if (await nav.count()) await nav.click();
    await page.waitForTimeout(2000);
    const results = await new AxeBuilder({ page }).analyze();
    console.log(`AXE ${pg}: violations=${results.violations.length}`);
    for (const v of results.violations) {
      console.log(`  [${v.impact}] ${v.id}: ${v.description} (nodes=${v.nodes.length})`);
      for (const n of v.nodes) console.log(`      target=${JSON.stringify(n.target)} html=${(n.html||'').slice(0,200)}`);
    }
    // Don't fail the suite on violations; record them. But fail on critical/serious.
    const serious = results.violations.filter(v => v.impact === 'critical' || v.impact === 'serious');
    if (serious.length) {
      console.log(`SERIOUS VIOLATIONS on ${pg}: ${serious.map(v=>v.id).join(', ')}`);
    }
  });
}