// ناوبری URL و deep-link (WP-05.1/WP-05.2).
// پیش‌نیاز مثل بقیهٔ specها: بک‌اند روی 127.0.0.1:18100 با کاربر e2e.
//
// توجه: `[data-page]` هم روی لینک ناوبری هست و هم روی نتیجهٔ palette؛ پس
// بررسی «صفحهٔ فعال» باید با `.nav-item[data-page=…]` انجام شود.
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

test('deep link renders the requested page on first load', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/#/macro');
  await page.waitForSelector('#content .page-head h1', { timeout: 10000 });
  await expect(nav(page, 'macro')).toHaveClass(/active/);
  expect(page.url()).toContain('#/macro');
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('clicking nav updates the URL', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#dashLive', { timeout: 10000 });
  await nav(page, 'markets').click();
  await page.waitForTimeout(800);
  expect(page.url()).toContain('#/markets');
  await expect(nav(page, 'markets')).toHaveClass(/active/);
});

test('back and forward navigate between pages', async ({ page }) => {
  await page.goto('/');
  await page.waitForSelector('#dashLive', { timeout: 10000 });
  await nav(page, 'risk').click();
  await page.waitForTimeout(600);
  await nav(page, 'alerts').click();
  await page.waitForTimeout(600);
  expect(page.url()).toContain('#/alerts');

  await page.goBack();
  await page.waitForTimeout(700);
  expect(page.url()).toContain('#/risk');
  await expect(nav(page, 'risk')).toHaveClass(/active/);

  await page.goForward();
  await page.waitForTimeout(700);
  expect(page.url()).toContain('#/alerts');
  await expect(nav(page, 'alerts')).toHaveClass(/active/);
});

test('refresh keeps the current page', async ({ page }) => {
  await page.goto('/#/sources');
  await page.waitForSelector('#content .page-head h1', { timeout: 10000 });
  await page.reload();
  await page.waitForSelector('#content .page-head h1', { timeout: 10000 });
  expect(page.url()).toContain('#/sources');
  await expect(nav(page, 'sources')).toHaveClass(/active/);
});

test('unknown hash falls back to overview', async ({ page }) => {
  await page.goto('/#/not-a-page');
  await page.waitForSelector('#dashLive', { timeout: 10000 });
  await expect(nav(page, 'overview')).toHaveClass(/active/);
});

test('debate page exposes a wired run button', async ({ page }) => {
  await page.goto('/#/debate');
  await page.waitForSelector('#debateTarget', { timeout: 10000 });
  await expect(page.locator('[data-action="debate"]')).toBeEnabled();
  // دکمهٔ «بررسی انسانی» که API ندارد باید صریحاً علامت‌خورده باشد، نه مرده.
  await expect(page.locator('text=NOT_CONNECTED')).toBeVisible();
});
