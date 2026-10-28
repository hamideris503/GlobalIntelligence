/** Full-stack E2E: the REAL React UI against the REAL FastAPI app + test DB.
 *
 * `playwright.fullstack.config.ts` starts `e2e/fullstack-server.py` (real app,
 * throwaway SQLite DB, MOCK_MODE=true, outbound sockets blocked) and the real
 * Vite dev server pointed at it. Nothing here mocks the API: every request goes
 * over HTTP to that server. Routes unrelated to localhost are aborted and
 * recorded, and the server-side socket guard log is asserted empty.
 *
 * Tests run in order: they build one model through its whole lifecycle. The DB
 * starts empty for every run (the server recreates it), and the last test
 * removes everything it created.
 */
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:8010";
const API_KEY = "e2e-local-fake-api-key"; // fake; the same value the E2E server puts in its env
const PROVIDER_NAME = "E2E Groq";
const FAKE_PROVIDER_KEY = "e2e-fake-key-SECRET9";
const MODEL_NAME = "e2e-model-a";
const GUARD_LOG = fileURLToPath(new URL("../.e2e-fullstack/network-guard.log", import.meta.url));

/** Every request in the whole run is audited here (single worker, in order). */
const AUDIT = {
  blocked: [] as string[],
  urls: [] as string[],
  pageErrors: [] as string[],
  consoleErrors: [] as string[],
  badResponses: [] as string[], // "<status> <url>"
};

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => {
  page.on("request", (req) => AUDIT.urls.push(req.url()));
  page.on("pageerror", (err) => AUDIT.pageErrors.push(err.message));
  page.on("console", (msg) => {
    // "Failed to load resource" is the browser echo of a >=400 response; those are
    // audited precisely (status + url) below, so keeping them here would duplicate
    // and force a coarser filter. Anything else at error level is a real signal.
    if (msg.type() === "error" && !msg.text().startsWith("Failed to load resource")) {
      AUDIT.consoleErrors.push(msg.text());
    }
  });
  page.on("response", (res) => {
    if (res.status() >= 400) AUDIT.badResponses.push(`${res.status()} ${res.url()}`);
  });
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.hostname === "127.0.0.1" || url.hostname === "localhost") {
      return route.continue();
    }
    AUDIT.blocked.push(url.href);
    return route.abort();
  });
});

/** Puts the fake key into this tab's memory through the manual key field.
 *  (Login itself is rate-limited per IP, so it is exercised once, in its own
 *  test; both paths store exactly the same in-memory key.) */
async function signIn(page: Page): Promise<void> {
  await page.goto("#/settings");
  await page.getByRole("tab", { name: "اتصال داخلی" }).click();
  await page.getByRole("region", { name: "کلید API داخلی (دستی)" })
    .locator('input[type="password"]').fill(API_KEY);
  await page.getByRole("button", { name: "ذخیره در حافظه" }).click();
  await expect(page.getByText("ثبت‌شده (فقط حافظه)")).toBeVisible();
}

async function openModels(page: Page): Promise<void> {
  await signIn(page);
  await page.getByRole("tab", { name: "مدل‌ها و قیمت" }).click();
  await expect(page.getByText("مدل‌ها و قیمت").first()).toBeVisible();
}

function api(page: Page) {
  const request = page.request;
  const headers = { "X-API-Key": API_KEY };
  return {
    models: async () =>
      (await request.get(`${BASE}/api/settings/models`, { headers })).json(),
    providers: async () =>
      (await request.get(`${BASE}/api/settings/providers`, { headers })).json(),
    enable: async (id: string, enabled: boolean) =>
      request.put(`${BASE}/api/settings/models/${id}`, { headers, data: { enabled } }),
    remove: async (path: string) => request.delete(`${BASE}${path}`, { headers }),
  };
}

function row(page: Page, text: string) {
  return page.locator("tr", { hasText: text });
}

function badge(page: Page, rowText: string, label: string) {
  return row(page, rowText).locator("span.badge", { hasText: label });
}

test("settings data is not served without a key", async ({ page }) => {
  await page.goto("#/settings");
  await expect(page.getByRole("alert")).toContainText("کلید API");
  await expect(page.locator("tr")).toHaveCount(0);
});

test("UI login against the real /api/auth/login keeps the key in memory only", async ({ page }) => {
  await page.goto("#/settings");
  await page.getByRole("tab", { name: "اتصال داخلی" }).click();
  await page.locator("label.field", { hasText: "رمز" }).locator("input").fill("admin");
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page.getByText("وارد شدید؛ کلید در حافظهٔ همین زبانه ثبت شد.")).toBeVisible();
  const stored = await page.evaluate(() => Object.keys(localStorage));
  expect(JSON.stringify(stored)).not.toContain("api");
  expect(await page.content()).not.toContain(API_KEY);
});

test("provider is created through the UI and its key is never shown in full", async ({ page }) => {
  await signIn(page);
  await page.getByRole("tab", { name: "ارائه‌دهندگان AI" }).click();
  await page.getByRole("button", { name: "افزودن" }).click();
  const modal = page.getByRole("dialog", { name: "افزودن ارائه‌دهنده" });
  await modal.locator("label.field", { hasText: "نام شرکت" }).locator("input").fill(PROVIDER_NAME);
  await modal.locator("label.field", { hasText: "نوع" }).locator("select").selectOption("groq");
  await modal.locator('input[type="password"]').fill(FAKE_PROVIDER_KEY);
  await modal.getByRole("button", { name: "ذخیره" }).click();
  await expect(modal).toBeHidden();

  await expect(row(page, PROVIDER_NAME)).toBeVisible();
  await expect(row(page, PROVIDER_NAME).getByText("••••RET9")).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain(FAKE_PROVIDER_KEY);
  expect(html).not.toContain("SECRET9");

  const providers = await api(page).providers();
  expect(providers).toHaveLength(1);
  expect(providers[0]).toMatchObject({ name: PROVIDER_NAME, kind: "groq", key_set: true, enabled: true });
  expect(JSON.stringify(providers)).not.toContain("SECRET9");
});

test("a new model is stored UNVERIFIED + disabled and survives a reload", async ({ page }) => {
  await openModels(page);
  const providers = await api(page).providers();
  await page.locator('select[aria-label="ارائه‌دهنده"]').selectOption(providers[0].id);
  await page.getByPlaceholder("نام مدل (دستی)").fill(MODEL_NAME);
  await page.getByPlaceholder("لینک رسمی طرح رایگان").fill("https://example.com/free-tier");
  await page.getByRole("button", { name: "ثبت مدل" }).click();
  await expect(page.locator(".toasts")).toContainText("تأییدنشده و غیرفعال");

  await expect(badge(page, MODEL_NAME, "تأییدنشده")).toBeVisible();
  await expect(row(page, MODEL_NAME).getByRole("button", { name: "خیر" })).toBeVisible();

  const [model] = await api(page).models();
  expect(model).toMatchObject({
    model_name: MODEL_NAME,
    enabled: false,
    free_status: "UNVERIFIED",
    free_source_url: "https://example.com/free-tier",
  });

  // the API key is memory-only, so log in again; the row must then come from the DB,
  // not from client state
  await page.reload();
  await openModels(page);
  await expect(badge(page, MODEL_NAME, "تأییدنشده")).toBeVisible();
});

test("enabling an UNVERIFIED model fails; the UI cannot force it", async ({ page }) => {
  await openModels(page);
  await row(page, MODEL_NAME).getByRole("button", { name: "خیر" }).click();
  await expect(page.locator(".toasts")).toContainText("cannot enable");
  await expect(row(page, MODEL_NAME).getByRole("button", { name: "خیر" })).toBeVisible();

  // Same request issued outside the UI (valid key, tampered body): still refused.
  const [model] = await api(page).models();
  const tamper = await api(page).enable(model.id, true);
  expect(tamper.status()).toBe(422);
  expect(((await tamper.json()) as { detail: string }).detail).toContain("UNVERIFIED");
  const [after] = await api(page).models();
  expect(after.enabled).toBe(false);
});

test("verify with incomplete evidence fails and keeps the form values", async ({ page }) => {
  await openModels(page);
  await row(page, MODEL_NAME).getByRole("button", { name: "تأیید" }).click();
  const modal = page.getByRole("dialog", { name: "تأیید طرح رایگان مدل" });
  await expect(modal.getByText("ملاحظات حریم خصوصی")).toBeVisible();

  await modal.locator("label.field", { hasText: "محدودیت‌ها" }).locator("input").fill("10/day");
  await modal.getByRole("checkbox").check();
  await modal.getByRole("button", { name: "تأیید" }).click();

  await expect(page.locator(".toasts")).toContainText("incomplete free-tier evidence");
  await expect(modal).toBeVisible();
  await expect(modal.locator("label.field", { hasText: "محدودیت‌ها" }).locator("input"))
    .toHaveValue("10/day");
  const [model] = await api(page).models();
  expect(model.free_status).toBe("UNVERIFIED");
});

test("verify with complete evidence marks FREE_VERIFIED but never enables", async ({ page }) => {
  await openModels(page);
  await row(page, MODEL_NAME).getByRole("button", { name: "تأیید" }).click();
  const modal = page.getByRole("dialog", { name: "تأیید طرح رایگان مدل" });
  await modal.locator("label.field", { hasText: "محدودیت‌ها" }).locator("input").fill("30 RPM / 1000 RPD");
  await modal.locator("label.field", { hasText: "پیش‌شرط حساب" }).locator("input").fill("free, no card");
  await modal.locator("label.field", { hasText: "ملاحظات حریم خصوصی" }).locator("input").fill("no training");
  await modal.getByRole("checkbox").check();
  await modal.getByRole("button", { name: "تأیید" }).click();

  await expect(modal).toBeHidden();
  await expect(page.locator(".toasts")).toContainText("هنوز غیرفعال است");
  await expect(badge(page, MODEL_NAME, "تأییدشده")).toBeVisible();
  await expect(row(page, MODEL_NAME).getByRole("button", { name: "خیر" })).toBeVisible();

  const [model] = await api(page).models();
  expect(model.free_status).toBe("FREE_VERIFIED");
  expect(model.enabled).toBe(false);
  expect(model.free_verified_on).toBeTruthy();
  expect(model.free_review_after).toBeTruthy();
  expect(model.free_verified_by).toBe("settings");
});

test("the verified model can then be enabled, and the list follows", async ({ page }) => {
  await openModels(page);
  await row(page, MODEL_NAME).getByRole("button", { name: "خیر" }).click();
  await expect(row(page, MODEL_NAME).getByRole("button", { name: "بله" })).toBeVisible();
  await expect(badge(page, MODEL_NAME, "تأییدشده")).toBeVisible();
  const [model] = await api(page).models();
  expect(model.enabled).toBe(true);
});

test("block demands a reason, then disables and persists it", async ({ page }) => {
  await openModels(page);
  await row(page, MODEL_NAME).getByRole("button", { name: "مسدود" }).click();
  const modal = page.getByRole("dialog", { name: "مسدودکردن مدل" });
  await modal.getByRole("button", { name: "مسدود و غیرفعال کن" }).click();
  await expect(page.locator(".toasts")).toContainText("دلیل مسدودسازی لازم است");
  await expect(modal).toBeVisible();

  await modal.locator("label.field", { hasText: "دلیل مسدودسازی" }).locator("input")
    .fill("quota removed upstream");
  await modal.getByRole("button", { name: "مسدود و غیرفعال کن" }).click();
  await expect(modal).toBeHidden();
  await expect(badge(page, MODEL_NAME, "مسدود")).toBeVisible();
  await expect(row(page, MODEL_NAME)).toContainText("quota removed upstream");
  await expect(row(page, MODEL_NAME).getByRole("button", { name: "خیر" })).toBeVisible();

  const [model] = await api(page).models();
  expect(model).toMatchObject({
    free_status: "BLOCKED", enabled: false, free_blocked_reason: "quota removed upstream",
  });

  // the API key is memory-only, so log in again; the row must then come from the DB,
  // not from client state
  await page.reload();
  await openModels(page);
  await expect(badge(page, MODEL_NAME, "مسدود")).toBeVisible();
});

test("a BLOCKED model cannot be enabled from outside the UI", async ({ page }) => {
  await openModels(page);
  const [model] = await api(page).models();
  const tamper = await api(page).enable(model.id, true);
  expect(tamper.status()).toBe(422);
  expect(((await tamper.json()) as { detail: string }).detail).toContain("BLOCKED");
  const [after] = await api(page).models();
  expect(after.enabled).toBe(false);
});

test("an AI call through the real gateway is labelled as mock, never as real", async ({ page }) => {
  await signIn(page);
  const res = await page.request.post(`${BASE}/api/ai/chat`, {
    headers: { "X-API-Key": API_KEY },
    data: { provider: PROVIDER_NAME, model: MODEL_NAME, messages: [{ role: "user", content: "ping" }] },
  });
  expect(res.status()).toBe(200);
  const body = (await res.json()) as { is_mock: boolean; provider: string; text: string };
  expect(body.is_mock).toBe(true);
  expect(body.provider).toBe("mock");
  expect(body.text).toContain("[mock:");

  // Connection test goes through the same gateway and reports the mock honestly.
  await page.getByRole("tab", { name: "ارائه‌دهندگان AI" }).click();
  await row(page, PROVIDER_NAME).getByRole("button", { name: "تست اتصال" }).click();
  await expect(page.locator(".toasts")).toContainText("ناموفق");
  await expect(page.locator(".toasts")).toContainText("mock response");
  expect(await page.content()).not.toContain("SECRET9");
});

test("a policy error from /api/ai/chat reaches the chat form as a message, not a crash", async ({ page }) => {
  await signIn(page);
  await page.goto("#/chat");
  // Same body the real backend returns for an off-list model (backend/api/errors.py).
  await page.route("**/api/ai/chat", (route) =>
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        detail: "model is not verified for free use",
        kind: "model_not_allowed",
        provider: "groq",
        retryable: false,
      }),
    }),
  );

  await page.getByLabel("متن پیام").fill("سلام");
  await page.getByRole("button", { name: "ارسال" }).click();

  await expect(page.locator(".toasts")).toContainText("model is not verified for free use");
  await expect(page.getByText("سلام")).toBeVisible();       // پیام کاربر حفظ شد
  await page.getByLabel("متن پیام").fill("دوباره");
  await expect(page.getByRole("button", { name: "ارسال" })).toBeEnabled();  // فرم سالم است
});

test("no unexpected browser error and no unexplained failing response", async () => {
  // 1) Real JS exceptions. The suite provokes no intentional one, so this is strict.
  expect(AUDIT.pageErrors).toEqual([]);
  // 2) console.error that is not a resource-load echo (see the listener above).
  expect(AUDIT.consoleErrors).toEqual([]);

  // 3) Failing responses the suite provokes on purpose, with the EXACT status each
  //    test asserts — a different status (e.g. a 500) is NOT excused by this list.
  //      - /api/settings/*: 401 without a key (test 1) and 422 for policy refusals
  //        (tests 5, 6, 9)
  //      - /api/ai/status: 401 while the shell polls it without a key (test 1)
  //      - /api/ai/chat: 403 fulfilled by the policy-error test (test 12)
  const EXPECTED: Array<[RegExp, number[]]> = [
    [/\/api\/settings\//, [401, 403, 422]],
    [/\/api\/ai\/status$/, [401]],
    [/\/api\/ai\/chat$/, [403]],
  ];
  const unexpected = AUDIT.badResponses.filter(
    (entry) =>
      !EXPECTED.some(
        ([pattern, codes]) => pattern.test(entry) && codes.some((c) => entry.startsWith(`${c} `)),
      ),
  );
  expect(unexpected).toEqual([]);
  // Anti-vacuity: the audit must have actually seen the provoked failures above
  // (and the successful paths are asserted by status-sensitive UI checks in the
  // tests themselves, so an excused 401 cannot hide a broken happy path).
  expect(AUDIT.badResponses.length).toBeGreaterThan(0);
});

test("no request left localhost and the server sent nothing outbound", async () => {
  expect(AUDIT.blocked).toEqual([]);
  const apiCalls = AUDIT.urls.filter((u) => u.includes("/api/") || u.includes("/health"));
  expect(apiCalls.length).toBeGreaterThan(0);
  for (const url of apiCalls) {
    expect(new URL(url).host).toBe("127.0.0.1:8010");
  }
  const guard = existsSync(GUARD_LOG) ? readFileSync(GUARD_LOG, "utf-8") : "";
  expect(guard.trim()).toBe("");
});

test("cleanup removes every row this run created", async ({ page }) => {
  const [model] = await api(page).models();
  const [provider] = await api(page).providers();
  expect(await (await api(page).remove(`/api/settings/models/${model.id}`)).ok()).toBe(true);
  expect(await (await api(page).remove(`/api/settings/providers/${provider.id}`)).ok()).toBe(true);
  expect(await api(page).models()).toEqual([]);
  expect(await api(page).providers()).toEqual([]);
});
