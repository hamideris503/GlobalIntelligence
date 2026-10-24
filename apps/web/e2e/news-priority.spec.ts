/** Real-browser E2E for the news page's ingest-priority display (local-only).
 *
 * Runs the real page from the prod build in Chromium; every /api/* call is
 * fulfilled by e2e/news-mock.ts and any non-localhost request is aborted.
 * No backend, no network, no secrets.
 *
 * Regression guard for the Phase 12 fix: the document's P0..P4 priority must
 * reach the UI verbatim (list column + article detail) and a missing/null
 * priority must render as a dash instead of crashing.
 */
import { expect, test, type Page } from "@playwright/test";
import { installNewsMock, mockArticle, type MockArticle } from "./news-mock";

const LEVELS = ["P0", "P1", "P2", "P3", "P4"] as const;

/** Column order on the news table; anchors the priority cell index below. */
const PRIORITY_COL = 2;

async function openNews(page: Page, articles: MockArticle[]): Promise<string[]> {
  const seen = await installNewsMock(page, articles);
  await page.goto("#/news");
  await expect(page.getByRole("heading", { name: "اخبار و رویدادها" })).toBeVisible();
  return seen;
}

/** Guards PRIORITY_COL: the header at that index must really be اولویت. */
async function expectPriorityHeader(page: Page): Promise<void> {
  await expect(page.locator("thead th").nth(PRIORITY_COL)).toHaveText("اولویت");
}

test("every stored P-level is shown verbatim in the priority column", async ({ page }) => {
  const articles = LEVELS.map((level, i) =>
    mockArticle({ id: `a${i}`, title: `خبر شماره ${i}`, priority: level }),
  );
  await openNews(page, articles);
  await expectPriorityHeader(page);

  for (let i = 0; i < LEVELS.length; i += 1) {
    const cell = page.locator("tr", { hasText: `خبر شماره ${i}` }).locator("td").nth(PRIORITY_COL);
    // exact text: no mapping, no reordering, no "P0" -> "۰" conversion
    await expect(cell).toHaveText(LEVELS[i]);
  }
});

test("a missing priority renders as a dash and does not break the page", async ({ page }) => {
  await openNews(page, [
    mockArticle({ id: "a-null", title: "خبر بدون اولویت", priority: null }),
  ]);
  await expectPriorityHeader(page);
  const cell = page.locator("tr", { hasText: "خبر بدون اولویت" }).locator("td").nth(PRIORITY_COL);
  await expect(cell).toHaveText("—");
  // the rest of the row still renders (no crash)
  await expect(page.getByText("خبر بدون اولویت")).toBeVisible();
});

test("article detail shows the same priority as the list", async ({ page }) => {
  const articles = LEVELS.map((level, i) =>
    mockArticle({ id: `d${i}`, title: `جزئیات ${i}`, priority: level }),
  );
  await openNews(page, articles);

  for (let i = 0; i < LEVELS.length; i += 1) {
    await page.goto(`#/news/article-d${i}`);
    await expect(page.getByRole("heading", { name: `جزئیات ${i}` })).toBeVisible();
    const value = page.locator("dt", { hasText: "اولویت دریافت" }).locator("+ dd");
    await expect(value).toHaveText(LEVELS[i]);
  }
});

test("article detail with a null priority shows a dash, not a crash", async ({ page }) => {
  await openNews(page, [mockArticle({ id: "d-null", title: "جزئیات بدون اولویت", priority: null })]);
  await page.goto("#/news/article-d-null");
  await expect(page.getByRole("heading", { name: "جزئیات بدون اولویت" })).toBeVisible();
  const value = page.locator("dt", { hasText: "اولویت دریافت" }).locator("+ dd");
  await expect(value).toHaveText("—");
});

test("no request leaves localhost", async ({ page }) => {
  const seen = await openNews(page, [mockArticle({ id: "a0", priority: "P1" })]);
  expect(seen.length).toBeGreaterThan(0);
  for (const url of seen) {
    expect(["localhost", "127.0.0.1"]).toContain(new URL(url).hostname);
  }
});

test("the news flows raise no browser error", async ({ page }) => {
  const problems: string[] = [];
  const bad: string[] = [];
  page.on("pageerror", (err) => problems.push(`pageerror: ${err.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") problems.push(`console.error: ${msg.text()}`);
  });
  page.on("response", (res) => {
    if (res.status() >= 400) bad.push(`${res.status()} ${res.url()}`);
  });

  await openNews(page, [
    mockArticle({ id: "e0", priority: "P0" }),
    mockArticle({ id: "e-null", priority: null }),
  ]);
  await page.goto("#/news/article-e0");
  await expect(page.getByRole("heading", { name: "خبر e0" })).toBeVisible();

  expect({ problems, bad }).toEqual({ problems: [], bad: [] });
});
