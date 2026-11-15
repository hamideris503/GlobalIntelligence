// E2E — سفر کامل کاربر: ساخت منبع RSS از UI → اجرای دریافت → خواندن خبر در Inbox.
// پیش‌نیاز (همان قرارداد سایر specها): backend روی 127.0.0.1:18100 با دیتابیس
// SQLite ساخته‌شده با `alembic upgrade head`، MOCK_MODE=false و کاربر admin
// `e2e` (global-setup یک‌بار وارد می‌شود). هیچ mock یا page.route در این فایل
// استفاده نمی‌شود: فید و API واقعی هستند.
const { test, expect } = require('@playwright/test');

const FEED = process.env.E2E_FEED || 'https://feeds.bbci.co.uk/news/world/rss.xml';
const SOURCE_NAME = `E2E BBC ${Date.now()}`;

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

test('user adds an RSS source, runs ingest, and reads the article', async ({ page }) => {
  test.setTimeout(180000);
  const errors = collectErrors(page);

  await page.goto('/#/sources');
  await expect(page.locator('#srcAddBtn')).toBeVisible({ timeout: 20000 });

  await page.locator('#srcAddBtn').click();
  await page.fill('#sName', SOURCE_NAME);
  await page.selectOption('#sAdapter', { label: 'RSS / Atom' });
  await page.fill('#sUrl', FEED);
  // «ثبت در سرور» (create-source)، نه «ذخیرهٔ Draft محلی» (save-source)
  await page.locator('[data-modal-action="create-source"]').click();

  // منبع در جدول دیده می‌شود (پس از refresh)
  await expect(page.locator('#srcTableWrap')).toContainText(SOURCE_NAME, { timeout: 20000 });

  // اجرای دریافت واقعی؛ پاسخ تا ۱۲۰ ثانیه پذیرفته می‌شود
  page.once('dialog', (d) => d.accept());
  await page.locator('#srcIngestBtn').click();
  await expect(page.locator('#toast')).toContainText('دریافت انجام شد', { timeout: 130000 });

  await page.goto('/#/inbox');
  const rows = page.locator('#inboxTableWrap [data-inbox-id]');
  await expect(rows.first()).toBeVisible({ timeout: 30000 });
  expect(await rows.count(), 'inbox باید حداقل یک خبر داشته باشد').toBeGreaterThan(0);

  await rows.first().click();
  await expect(page.locator('#inboxDetail')).not.toBeEmpty({ timeout: 20000 });

  expect(errors, errors.join(' | ')).toEqual([]);
});
