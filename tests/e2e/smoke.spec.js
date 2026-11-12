const { test, expect } = require('@playwright/test');

test('overview page renders without console errors', async ({ page }) => {
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
  // allow async load to settle
  await page.waitForTimeout(2000);
  expect(errors, `console errors: ${errors.join(' | ')}`).toEqual([]);
});

test('inbox page renders', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const u = (m.location() || {}).url || '';
    if (u.includes('favicon')) return;
    errors.push(m.text() + (u ? ' @ ' + u : ''));
  });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/#inbox');
  await page.waitForSelector('#inboxLive, #inboxTableWrap', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2000);
  expect(errors, `console errors: ${errors.join(' | ')}`).toEqual([]);
});

test('offline banner + stale cache fallback', async ({ page, context }) => {
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(e.message));
  await page.goto('/');
  await page.waitForSelector('#dashLive', { timeout: 10000 });
  await page.waitForTimeout(1500);

  // Warm the cache with a real GET while online.
  const online = await page.evaluate(async () => {
    try { const d = await api('GET', '/api/dashboard/overview', { timeout: 8000 }); return { ok: true, keys: Object.keys(d || {}).length }; }
    catch (e) { return { ok: false, err: e.message }; }
  });
  expect(online.ok, `online fetch failed: ${online.err || ''}`).toBeTruthy();

  // Go offline: the app should show a network banner.
  await context.setOffline(true);
  await page.waitForTimeout(400);
  await expect(page.locator('#giNetBanner')).toBeVisible();
  const bannerText = await page.locator('#giNetBanner').first().innerText();
  expect(bannerText.includes('آفلاین') || bannerText.includes('کهنه')).toBeTruthy();

  // Same GET offline must fall back to the cached copy, explicitly marked stale.
  const offline = await page.evaluate(async () => {
    try { const d = await api('GET', '/api/dashboard/overview', { timeout: 8000 }); return { ok: true, fromCache: !!d.__fromCache, cacheAt: d.__cacheAt || 0 }; }
    catch (e) { return { ok: false, err: e.message }; }
  });
  expect(offline.ok, `offline fetch should use cache: ${offline.err || ''}`).toBeTruthy();
  expect(offline.fromCache).toBe(true);
  expect(offline.cacheAt).toBeGreaterThan(0);

  // Retry while still offline: the banner must persist and nothing may crash.
  await page.locator('#giNetBanner button').click();
  await page.waitForTimeout(800);
  await expect(page.locator('#giNetBanner')).toBeVisible();

  expect(pageErrors, `page errors: ${pageErrors.join(' | ')}`).toEqual([]);
});

test('providers page renders', async ({ page }) => {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const u = (m.location() || {}).url || '';
    if (u.includes('favicon')) return;
    errors.push(m.text() + (u ? ' @ ' + u : ''));
  });
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/#providers');
  await page.waitForTimeout(2000);
  expect(errors, `console errors: ${errors.join(' | ')}`).toEqual([]);
});
