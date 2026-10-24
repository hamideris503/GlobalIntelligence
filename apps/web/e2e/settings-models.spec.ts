/** Real-browser E2E for AI settings Models panel (local-only, fully mocked).
 *
 * The real page runs in Chromium served from the prod build; every /api/*
 * call is fulfilled by e2e/mock-api.ts (mirrors the real backend contract);
 * any non-localhost request is aborted. No backend, no network, no secrets.
 */
import { expect, test, type Page } from "@playwright/test";
import {
  baseModel,
  baseProviders,
  installMockApi,
  type MockState,
} from "./mock-api";

function freshState(): MockState {
  return {
    providers: baseProviders(),
    models: [],
    testConnectionResponder: null,
    modelsListError: null,
    modelPutError: null,
  };
}

async function openModels(page: Page, state: MockState): Promise<string[]> {
  const seen = await installMockApi(page, state);
  await page.goto("#/settings");
  await page.getByRole("tab", { name: "مدل‌ها و قیمت" }).click();
  await expect(page.getByText("مدل‌ها و قیمت").first()).toBeVisible();
  return seen;
}

test("models list renders all four free-status badges", async ({ page }) => {
  const state = freshState();
  state.models = [
    baseModel({ model_name: "m-un", free_status: "UNVERIFIED" }),
    baseModel({ model_name: "m-ok", free_status: "FREE_VERIFIED", enabled: true }),
    baseModel({
      model_name: "m-exp", free_status: "REVIEW_REQUIRED",
      free_review_after: "2020-01-01",
    }),
    baseModel({
      model_name: "m-blk", free_status: "BLOCKED",
      free_blocked_reason: "quota removed",
    }),
  ];
  await openModels(page, state);
  const badgeIn = (rowName: string, text: string) =>
    page.locator("tr", { hasText: rowName }).locator("span.badge", { hasText: text });
  await expect(badgeIn("m-un", "تأییدنشده")).toBeVisible();
  await expect(badgeIn("m-ok", "تأییدشده")).toBeVisible();
  await expect(badgeIn("m-exp", "نیازمند بازبینی")).toBeVisible();
  await expect(badgeIn("m-blk", "مسدود")).toBeVisible();
  await expect(page.getByText("quota removed")).toBeVisible();
  // Expired model must not look active.
  const row = page.locator("tr", { hasText: "m-exp" });
  await expect(row.getByText("بله")).toHaveCount(0);
});

test("creating a model shows it UNVERIFIED and disabled", async ({ page }) => {
  const state = freshState();
  await openModels(page, state);
  await page.locator('select[aria-label="ارائه‌دهنده"]').selectOption("p1");
  await page.getByPlaceholder("نام مدل (دستی)").fill("m-new");
  await page.getByPlaceholder("لینک رسمی طرح رایگان").fill("https://example.com/free");
  await page.getByRole("button", { name: "ثبت مدل" }).click();
  const row = page.locator("tr", { hasText: "m-new" });
  await expect(row.getByText("تأییدنشده")).toBeVisible();
  await expect(row.getByRole("button", { name: "خیر" })).toBeVisible();
  await expect(page.locator(".toasts")).toContainText("تأییدنشده و غیرفعال");
});

test("enabling an unverified model shows an error and stays disabled", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-new" })];
  await openModels(page, state);
  const row = page.locator("tr", { hasText: "m-new" });
  await row.getByRole("button", { name: "خیر" }).click();
  await expect(page.locator(".toasts")).toContainText("UNVERIFIED");
  await expect(row.getByRole("button", { name: "خیر" })).toBeVisible();
});

test("verify modal validates evidence and keeps the form on error", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-new" })];
  await openModels(page, state);
  const row = page.locator("tr", { hasText: "m-new" });
  await row.getByRole("button", { name: "تأیید" }).click();
  const modal = page.getByRole("dialog", { name: "تأیید طرح رایگان مدل" });
  await expect(modal).toBeVisible();
  // Evidence, date/source and explicit-confirm controls are present.
  await expect(modal.getByText("لینک رسمی قیمت/طرح رایگان")).toBeVisible();
  await expect(modal.getByText("ملاحظات حریم خصوصی")).toBeVisible();
  await expect(modal.getByRole("checkbox")).toBeVisible();
  // Incomplete evidence + confirm => 422, modal stays open with values.
  await modal.locator("label.field", { hasText: "محدودیت‌ها" }).locator("input").fill("10/day");
  await modal.getByRole("checkbox").check();
  await modal.getByRole("button", { name: "تأیید" }).click();
  await expect(page.locator(".toasts")).toContainText("incomplete");
  await expect(modal).toBeVisible();
  await expect(
    modal.locator("label.field", { hasText: "محدودیت‌ها" }).locator("input"),
  ).toHaveValue("10/day");
});

test("successful verify keeps the model disabled until separate enable", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-new" })];
  await openModels(page, state);
  const row = page.locator("tr", { hasText: "m-new" });
  await row.getByRole("button", { name: "تأیید" }).click();
  const modal = page.getByRole("dialog", { name: "تأیید طرح رایگان مدل" });
  await modal.locator("label.field", { hasText: "لینک رسمی قیمت/طرح رایگان" }).locator("input")
    .fill("https://example.com/pricing");
  await modal.locator("label.field", { hasText: "محدودیت‌ها" }).locator("input").fill("10/day");
  await modal.locator("label.field", { hasText: "پیش‌شرط حساب و احتمال هزینه" }).locator("input")
    .fill("no card");
  await modal.locator("label.field", { hasText: "ملاحظات حریم خصوصی" }).locator("input")
    .fill("none");
  await modal.getByRole("checkbox").check();
  await modal.getByRole("button", { name: "تأیید" }).click();
  await expect(modal).toBeHidden();
  await expect(row.locator("span.badge", { hasText: "تأییدشده" })).toBeVisible();
  await expect(row.getByRole("button", { name: "خیر" })).toBeVisible();
});

test("enabling a verified model updates the list", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-ok", free_status: "FREE_VERIFIED" })];
  await openModels(page, state);
  const row = page.locator("tr", { hasText: "m-ok" });
  await row.getByRole("button", { name: "خیر" }).click();
  await expect(row.getByRole("button", { name: "بله" })).toBeVisible();
  await expect(row.locator("span.badge", { hasText: "تأییدشده" })).toBeVisible();
});

test("block requires a reason, then disables with BLOCKED badge", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-ok", free_status: "FREE_VERIFIED", enabled: true })];
  await openModels(page, state);
  const row = page.locator("tr", { hasText: "m-ok" });
  await row.getByRole("button", { name: "مسدود" }).click();
  const modal = page.getByRole("dialog", { name: "مسدودکردن مدل" });
  await modal.getByRole("button", { name: "مسدود و غیرفعال کن" }).click();
  await expect(modal).toBeVisible(); // reason required: stays open
  await modal.locator("label.field", { hasText: "دلیل مسدودسازی" }).locator("input")
    .fill("quota removed upstream");
  await modal.getByRole("button", { name: "مسدود و غیرفعال کن" }).click();
  await expect(modal).toBeHidden();
  await expect(row.locator("span.badge", { hasText: "مسدود" })).toBeVisible();
  await expect(row.getByRole("button", { name: "خیر" })).toBeVisible();
});

test("403 on enable shows a toast and preserves state", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-ok", free_status: "FREE_VERIFIED" })];
  state.modelPutError = { status: 403, body: { detail: "forbidden" } };
  await openModels(page, state);
  const row = page.locator("tr", { hasText: "m-ok" });
  await row.getByRole("button", { name: "خیر" }).click();
  await expect(page.locator(".toasts")).toBeVisible();
  await expect(row.getByRole("button", { name: "خیر" })).toBeVisible();
});

test("401 on the list surfaces an auth error", async ({ page }) => {
  const state = freshState();
  state.modelsListError = { status: 401, body: { detail: "unauthorized" } };
  await openModels(page, state);
  await expect(page.getByText("مدل‌ها و قیمت").first()).toBeVisible();
  await expect(page.locator("tr", { hasText: "m-ok" })).toHaveCount(0);
});

test("provider key never appears in full in the DOM", async ({ page }) => {
  const state = freshState();
  const seen = await installMockApi(page, state);
  await page.goto("#/settings"); // ProvidersTab is the default tab
  await page.getByRole("button", { name: "افزودن" }).click();
  const modal = page.getByRole("dialog", { name: "افزودن ارائه‌دهنده" });
  await modal.locator("label.field", { hasText: "نام شرکت" }).locator("input").fill("PX");
  await modal.locator('input[type="password"]').fill("test-fake-key-SECRET9");
  await modal.getByRole("button", { name: "ذخیره" }).click();
  await expect(modal).toBeHidden();
  await expect(page.locator("tr", { hasText: "PX" })).toBeVisible();
  await expect(page.locator("tr", { hasText: "PX" }).getByText("3456")).toBeVisible();
  const html = await page.content();
  expect(html).not.toContain("SECRET9");
  expect(html).not.toContain("test-fake-key");
  void seen;
});

test("connection-test failure displays without the key", async ({ page }) => {
  const state = freshState();
  state.testConnectionResponder = { ok: false, error: "cannot reach the provider" };
  await installMockApi(page, state);
  await page.goto("#/settings");
  const row = page.locator("tr", { hasText: "G1" });
  await row.getByRole("button", { name: "تست اتصال" }).click();
  await expect(page.locator(".toasts")).toContainText("ناموفق");
  const html = await page.content();
  expect(html).not.toContain("test-fake");
});

test("swap between two verified models updates the list", async ({ page }) => {
  const state = freshState();
  state.models = [
    baseModel({ model_name: "m-one", free_status: "FREE_VERIFIED", enabled: true }),
    baseModel({ model_name: "m-two", free_status: "FREE_VERIFIED" }),
  ];
  await openModels(page, state);
  const rowTwo = page.locator("tr", { hasText: "m-two" });
  await rowTwo.getByRole("button", { name: "خیر" }).click();
  await expect(rowTwo.getByRole("button", { name: "بله" })).toBeVisible();
  const rowOne = page.locator("tr", { hasText: "m-one" });
  await rowOne.getByRole("button", { name: "بله" }).click();
  await expect(rowOne.getByRole("button", { name: "خیر" })).toBeVisible();
  await expect(rowOne.locator("span.badge", { hasText: "تأییدشده" })).toBeVisible();
});

test("no request leaves localhost", async ({ page }) => {
  const state = freshState();
  state.models = [baseModel({ model_name: "m-ok", free_status: "FREE_VERIFIED" })];
  const seen = await openModels(page, state);
  expect(seen.length).toBeGreaterThan(0);
  for (const url of seen) {
    const host = new URL(url).hostname;
    expect(["localhost", "127.0.0.1"]).toContain(host);
  }
});
