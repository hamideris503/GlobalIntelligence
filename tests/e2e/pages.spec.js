// WP-05.3 — کارکرد واقعی صفحه‌های باقی‌مانده: world، entity-graph، markets، evidence.
// پیش‌نیاز: بک‌اند روی 127.0.0.1:18100 با کاربر e2e و دادهٔ seed (claims، entities، market observations).
const { test, expect } = require('@playwright/test');

const nav = (page, id) => page.locator(`.nav-item[data-page="${id}"]`);

function collectErrors(page) {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const u = (m.location() || {}).url || '';
    if (u.includes('favicon')) return;
    errors.push(m.text() + (u ? ' @ ' + u : ''));
  });
  page.on('pageerror', (e) => errors.push(e.message));
  return errors;
}

test('evidence: local status filter narrows the claim list', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/#/evidence');
  await page.waitForSelector('#evidenceFilter', { timeout: 10000 });
  await expect(page.locator('#evidenceLive .panel')).toHaveCount(3, { timeout: 10000 });

  await page.selectOption('#evidenceFilter', 'verified');
  await expect(page.locator('#evidenceLive .panel')).toHaveCount(1, { timeout: 10000 });

  await page.selectOption('#evidenceFilter', 'with_evidence');
  await expect(page.locator('#evidenceLive .panel')).toHaveCount(2, { timeout: 10000 });

  await page.selectOption('#evidenceFilter', 'rejected');
  await expect(page.locator('#evidenceLive .panel')).toHaveCount(1, { timeout: 10000 });

  await page.selectOption('#evidenceFilter', 'all');
  await expect(page.locator('#evidenceLive .panel')).toHaveCount(3, { timeout: 10000 });
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('markets: table renders real observations and the fetch button is wired', async ({ page }) => {
  const errors = collectErrors(page);
  let fetchPayload = null;
  // درخواست بیرونی را قطع نمی‌کنیم؛ فقط پاسخ را جایگزین می‌کنیم تا سیم‌کشی UI سنجیده شود.
  await page.route('**/api/markets/fetch*', async (route) => {
    fetchPayload = route.request().url();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ symbols_fetched: 1, stored: 1, failed: [] }),
    });
  });
  await page.goto('/#/markets');
  await expect(page.locator('#marketsLive table tbody tr')).toHaveCount(2, { timeout: 10000 });
  await expect(page.locator('#marketsLive')).toContainText('BRENT');
  await expect(page.locator('#marketsLive')).toContainText('e2e-seed');

  page.once('dialog', (d) => d.accept());
  await page.fill('#marketsSymbol', 'brent');
  await page.locator('[data-action="marketsFetch"]').click();
  await expect(page.locator('#toast')).toContainText('دریافت بازار', { timeout: 10000 });
  expect(fetchPayload, 'fetch endpoint must be called').toContain('/api/markets/fetch');
  expect(fetchPayload).toContain('symbol=BRENT');
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('entity-graph: node click shows details and neighbours', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/#/entity-graph');
  await page.waitForSelector('#graphSvgContainer svg', { timeout: 15000 });
  const nodes = page.locator('#graphSvgContainer circle[data-entity-id]');
  await expect(nodes.first()).toBeVisible();
  await nodes.first().click();
  const detail = page.locator('#graphDetail');
  await expect(detail).toContainText('Iran', { timeout: 10000 });
  await expect(detail).toContainText('IAEA');
  await expect(detail).toContainText('cooperates_with');
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('world: feed refresh button re-requests data without console errors', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/#/world');
  await page.waitForSelector('#wmRefreshTop', { timeout: 15000 });
  await page.locator('#wmRefreshTop').click();
  await page.waitForTimeout(1500);
  await expect(page.locator('#wmConnectionStatus')).toBeVisible();
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('deep link to each remaining page keeps the nav in sync', async ({ page }) => {
  for (const id of ['world', 'entity-graph', 'markets', 'evidence']) {
    await page.goto(`/#/${id}`);
    await page.waitForSelector('#content .page-head h1', { timeout: 15000 });
    await expect(nav(page, id)).toHaveClass(/active/, { timeout: 10000 });
  }
});
