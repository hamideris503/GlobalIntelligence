// WP-06 — Configuration Control Plane در صفحهٔ تنظیمات.
// پیش‌نیاز مثل بقیهٔ specها: بک‌اند روی 127.0.0.1:18100 با کاربر e2e.
const { test, expect } = require('@playwright/test');

function collectErrors(page) {
  const errors = [];
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const u = (m.location() || {}).url || '';
    if (u.includes('favicon')) return;
    // درخواست‌های جانبی/فونت‌ها در محیط آفلاین نباید این اسپک را بشکنند.
    if (m.text().includes('Failed to load resource')) return;
    errors.push(m.text() + (u ? ' @ ' + u : ''));
  });
  page.on('pageerror', (e) => errors.push(e.message));
  return errors;
}

test('settings page renders the configuration control plane', async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto('/#/settings');
  await expect(page.locator('#cfgPlane table').first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator('#cfgPlane')).toContainText('source');
  await expect(page.locator('#cfgPlane')).toContainText('آماده');
  await expect(page.locator('#cfgPlane')).toContainText('NEEDS_ADAPTER');
  // گروه‌های بدون adapter باید صریحاً غیرقابل‌ذخیره باشند، نه دکمهٔ ساختگی.
  await expect(page.locator('#cfgPlane')).toContainText('scheduling');
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('draft → validate works from the UI and stays out of runtime', async ({ page }) => {
  const errors = collectErrors(page);
  const slug = `e2e-${Date.now()}`;
  await page.goto('/#/settings');
  await expect(page.locator('#cfgSlug')).toBeVisible({ timeout: 15000 });

  await page.fill('#cfgSlug', slug);
  await page.locator('[data-action="cfgCreate"]').click();
  await expect(page.locator('#toast')).toContainText('Draft ثبت شد', { timeout: 15000 });

  // تاریخچه باز می‌شود و r1 در وضعیت Draft است.
  const detail = page.locator('#cfgDetail');
  await expect(detail).toContainText(slug, { timeout: 15000 });
  await expect(detail).toContainText('Draft');
  await expect(detail.locator('[data-action="cfgValidate"]')).toBeVisible();
  // تا قبل از Test، دکمهٔ فعال‌سازی وجود ندارد (گذار مجاز نیست).
  await expect(detail.locator('[data-action="cfgActivate"]')).toHaveCount(0);

  await detail.locator('[data-action="cfgValidate"]').first().click();
  await expect(page.locator('#toast')).toContainText('معتبر است', { timeout: 15000 });
  await expect(detail).toContainText('اعتبارسنجی‌شده');
  // بعد از اعتبارسنجی، تست (بدون ingest) در دسترس است.
  await expect(detail.locator('[data-action="cfgTest"]')).toBeVisible();
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('instance list shows the created draft with its revision', async ({ page }) => {
  const slug = `e2e-list-${Date.now()}`;
  await page.goto('/#/settings');
  await expect(page.locator('#cfgSlug')).toBeVisible({ timeout: 15000 });
  await page.fill('#cfgSlug', slug);
  await page.locator('[data-action="cfgCreate"]').click();
  await expect(page.locator('#toast')).toContainText('Draft ثبت شد', { timeout: 15000 });
  await expect(page.locator('#cfgPlane')).toContainText(slug);
  const row = page.locator('#cfgPlane tbody tr', { hasText: slug });
  // اعداد با nf() فارسی نمایش داده می‌شوند: r۱
  await expect(row).toContainText(/r\s*[1۱]/);
});
