/** Real-browser E2E for the screening / dispatch operations page (local-only).
 *
 * The real prod build runs in Chromium; every /api/* call is fulfilled by
 * e2e/screening-mock.ts and non-localhost requests are aborted. No backend,
 * no network, no secrets.
 */
import { expect, test, type Page } from "@playwright/test";
import { baseState, installScreeningMock, type ScreeningMockState } from "./screening-mock";

async function open(page: Page): Promise<ScreeningMockState> {
  const state = await installScreeningMock(page, baseState());
  await page.goto("#/screening");
  await expect(page.getByRole("heading", { name: "غربالگری و صف پردازش" })).toBeVisible();
  return state;
}

test("nav entry exists and the review queue is driven by reasons, not priority", async ({ page }) => {
  const state = await open(page);
  await expect(page.getByRole("button", { name: /غربالگری و صف پردازش/ })).toHaveCount(1);

  const flagged = page.locator("tr", { hasText: "مرور کم‌حاشیه" });
  await expect(flagged).toBeVisible();
  await expect(flagged.getByText("حاشیه اطمینان کم")).toBeVisible();
  await expect(page.locator("tr", { hasText: "محافظ اولویت" })).toBeVisible();
  // P0 with a usable decision is a priority, not a review item.
  await expect(page.locator("tr", { hasText: "اولویت بالا بدون بازبینی" })).toHaveCount(0);

  await page.getByLabel("فقط P0/P1").check();
  await expect.poll(() => state.seen.some((u) => u.includes("p0_p1=true"))).toBe(true);
  await expect(page.locator("tr", { hasText: "مرور کم‌اهمیت" })).toHaveCount(0);
  await expect(page.locator("tr", { hasText: "مرور کم‌حاشیه" })).toBeVisible();
  await expect(page.locator("tr", { hasText: "محافظ اولویت" })).toBeVisible();
});

test("acknowledging is durable, stays flagged, and never hides the automated result", async ({ page }) => {
  const state = await open(page);
  const row = page.locator("tr", { hasText: "مرور کم‌حاشیه" });
  await row.getByRole("button", { name: "تأیید بازبینی" }).click();

  // default filter is "only unacknowledged": the row leaves the list
  await expect(page.locator("tr", { hasText: "مرور کم‌حاشیه" })).toHaveCount(0);
  expect(state.items.find((i) => i.article_id === "rev-1")?.review_acknowledged).toBe(true);
  expect(state.seen.some((u) => u.includes("/api/screening/review/rev-1/ack"))).toBe(true);

  // without the filter it is still present, still review-required, now acknowledged
  await page.getByLabel("فقط تأییدنشده").uncheck();
  const again = page.locator("tr", { hasText: "مرور کم‌حاشیه" });
  await expect(again).toBeVisible();
  await expect(again.getByText("تأیید شده")).toBeVisible();
  await expect(again.getByText("حاشیه اطمینان کم")).toBeVisible();
});

test("domain routing surfaces in outcomes and the dispatch task filter accepts new tasks", async ({ page }) => {
  const state = await open(page);
  await page.getByRole("tab", { name: "نتایج غربالگری" }).click();
  // Relevant article carries persisted domain signals; not-relevant has none.
  const routed = page.locator("tr", { hasText: "اولویت بالا بدون بازبینی" });
  await expect(routed).toBeVisible();
  await expect(routed.getByText("macro، markets")).toBeVisible();
  const unrouted = page.locator("tr", { hasText: "نتیجه نامرتبط" });
  await expect(unrouted).toBeVisible();

  await page.getByRole("tab", { name: "وظایف پردازش" }).click();
  await page.getByLabel("نوع وظیفه").selectOption("domain_routing");
  await expect.poll(() => state.seen.some((u) => u.includes("task=domain_routing"))).toBe(true);
});

test("dispatch statuses are truthful and retry is limited to retryable rows", async ({ page }) => {
  const state = await open(page);
  await page.getByRole("tab", { name: "وظایف پردازش" }).click();

  const completed = page.locator("tr", { hasText: "مقاله job-complete" });
  await expect(completed.getByText("تکمیل‌شده (اجرا اثبات شده)")).toBeVisible();
  await expect(completed.getByRole("button", { name: "تلاش مجدد" })).toHaveCount(0);

  const terminal = page.locator("tr", { hasText: "مقاله job-terminal" });
  await expect(terminal.getByText("خطای پایانی")).toBeVisible();
  await expect(terminal.getByRole("button", { name: "تلاش مجدد" })).toHaveCount(0);

  const retryable = page.locator("tr", { hasText: "مقاله job-retry" });
  await expect(retryable.getByText("قابل تلاش مجدد")).toBeVisible();
  await retryable.getByRole("button", { name: "تلاش مجدد" }).click();
  await expect(retryable.getByText("در صف")).toBeVisible();
  expect(state.seen.some((u) => u.includes("/api/dispatch/job-retry/retry"))).toBe(true);
});

test("runtime tab separates the saved toggle from actual readiness", async ({ page }) => {
  await open(page);
  await page.getByRole("tab", { name: "وضعیت Kev و Laya" }).click();

  const kev = page.locator("tr", { hasText: "Kev" });
  await expect(kev.getByText("فعال", { exact: true })).toBeVisible();
  await expect(kev.getByText("ENABLED_NOT_LOADED")).toBeVisible();

  const laya = page.locator("tr", { hasText: "Laya" });
  await expect(laya.getByText("غیرفعال", { exact: true })).toBeVisible();
  await expect(laya.getByText("DISABLED", { exact: true })).toBeVisible();
});

test("polling never overlaps and stops on unmount", async ({ page }) => {
  test.setTimeout(45000);
  const state = await open(page);
  await page.getByRole("tab", { name: "وضعیت Kev و Laya" }).click();
  await expect(page.getByText("ENABLED_NOT_LOADED")).toBeVisible();

  await page.waitForTimeout(6500);
  expect(state.runtimeCount).toBeGreaterThanOrEqual(2);
  expect(state.maxConcurrent).toBe(1); // no overlapping requests

  await expect.poll(() => state.inflight).toBe(0);
  const before = state.runtimeCount;
  await page.goto("#/dashboard");
  await page.waitForTimeout(6500);
  expect(state.runtimeCount).toBe(before); // interval cleared on unmount
});

test("no request leaves localhost and the flows raise no browser error", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (err) => problems.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") problems.push(`console.error: ${msg.text()}`);
  });

  const state = await open(page);
  await page.getByRole("tab", { name: "نتایج غربالگری" }).click();
  await expect(page.locator("tr", { hasText: "نتیجه نامرتبط" })).toBeVisible();
  await page.getByRole("tab", { name: "وظایف پردازش" }).click();
  await expect(page.locator("tr", { hasText: "مقاله job-complete" })).toBeVisible();
  await page.getByRole("tab", { name: "وضعیت Kev و Laya" }).click();
  await expect(page.getByText("ENABLED_NOT_LOADED")).toBeVisible();

  expect(problems).toEqual([]);
  expect(state.seen.length).toBeGreaterThan(0);
  for (const url of state.seen) {
    expect(["localhost", "127.0.0.1"]).toContain(new URL(url).hostname);
  }
});
