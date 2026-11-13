// ورود یک‌باره برای E2E: کوکی نشست را می‌گیرد و به همهٔ تست‌ها می‌دهد.
// پیش‌نیاز: کاربر `e2e` (role=admin، بدون ایمیل) در دیتابیس تست وجود داشته باشد.
const os = require('os');
const path = require('path');
const { request } = require('@playwright/test');

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:18100';
const USERNAME = process.env.E2E_USERNAME || 'e2e';
const PASSWORD = process.env.E2E_PASSWORD || 'E2eTestPassword123';

module.exports = async () => {
  const context = await request.newContext({ baseURL: BASE_URL });
  try {
    const res = await context.post('/api/auth/session', {
      data: { username: USERNAME, password: PASSWORD },
    });
    if (!res.ok()) {
      throw new Error(`e2e login failed: ${res.status()} ${await res.text()}`);
    }
    await context.storageState({ path: path.join(os.tmpdir(), 'gi-e2e-auth.json') });
  } finally {
    await context.dispose();
  }
};
