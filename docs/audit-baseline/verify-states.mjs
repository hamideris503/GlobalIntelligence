/**
 * F03.UX.5 — verification of the unified state contract.
 *
 * Asserts that one global failure produces exactly one banner across pages,
 * that per-panel error boxes are suppressed, and that empty / no-results states
 * carry a real next action. Test-only interception; the app ships no mock data.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-states.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";
const failures = [];
const check = (name, cond, detail) => {
  if (!cond) failures.push(`${name}${detail ? ` → ${detail}` : ""}`);
};

const ROUTES = ["dashboard", "news", "sources", "ops", "archive"];
const KINDS = [
  { kind: "auth", status: 401, expect: "کلید API" },
  { kind: "server", status: 500, expect: "خطای سرور" },
  { kind: "offline", abort: true, expect: "ارتباط با سرور" },
];

const browser = await chromium.launch();
const results = [];

// ---------- 1) one global banner per page, no duplicated panels ----------
for (const k of KINDS) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.route("**/localhost:8000/**", async (route) => {
    if (k.abort) return route.abort("failed");
    return route.fulfill({
      status: k.status,
      contentType: "application/json",
      body: JSON.stringify({ detail: k.kind }),
    });
  });

  for (const r of ROUTES) {
    await page.goto(`${WEB}/#/${r}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(700);
    const fact = await page.evaluate(() => ({
      banners: document.querySelectorAll(".gnotice").length,
      alerts: document.querySelectorAll('[role="alert"]').length,
      errboxes: document.querySelectorAll(".errbox").length,
      text: document.querySelector(".gnotice")?.textContent ?? "",
      hasRetry: [...document.querySelectorAll(".gnotice button")].some((b) =>
        b.textContent?.includes("تلاش مجدد"),
      ),
      hasRef: !!document.querySelector(".gnotice code"),
    }));
    results.push({ kind: k.kind, route: r, ...fact });
    check(`${k.kind}/${r}: دقیقاً یک بنر`, fact.banners === 1, `banners=${fact.banners}`);
    check(`${k.kind}/${r}: خطای تکراری در پنل‌ها نیست`, fact.errboxes === 0, `errbox=${fact.errboxes}`);
    check(`${k.kind}/${r}: حداکثر یک alert`, fact.alerts <= 1, `alerts=${fact.alerts}`);
    check(`${k.kind}/${r}: پیام مناسب`, fact.text.includes(k.expect), fact.text.slice(0, 60));
    check(`${k.kind}/${r}: دکمهٔ تلاش مجدد`, fact.hasRetry);
    check(`${k.kind}/${r}: شناسهٔ پیگیری`, fact.hasRef);
  }
  await context.close();
}

// ---------- 2) no-results and empty-with-action ----------
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.route("**/localhost:8000/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/classify/articles") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { id: "a1", title: "خبر تست", topics: ["economy"], importance: 2, priority: 1, sentiment: 0 },
        ]),
      });
    }
    if (url.pathname === "/api/sources") {
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });

  await page.goto(`${WEB}/#/news`, { waitUntil: "networkidle" });
  await page.waitForSelector("table");
  await page.fill('input[aria-label="جست‌وجوی اخبار"]', "zzz-no-match");
  await page.waitForTimeout(300);
  const noResults = await page.evaluate(() => ({
    text: document.querySelector(".empty")?.textContent ?? "",
    hasClear: [...document.querySelectorAll(".empty button")].some((b) =>
      b.textContent?.includes("پاک کردن فیلترها"),
    ),
    rows: document.querySelectorAll("tbody tr").length,
  }));
  check("no-results نمایش داده می‌شود", noResults.text.includes("نتیجه‌ای با این فیلترها"), noResults.text.slice(0, 40));
  check("no-results دکمهٔ پاک‌کردن فیلتر دارد", noResults.hasClear);

  await page.getByRole("button", { name: "پاک کردن فیلترها" }).click();
  await page.waitForTimeout(400);
  const afterClear = await page.evaluate(() => ({
    rows: document.querySelectorAll("tbody tr").length,
    inputValue: document.querySelector('input[aria-label="جست‌وجوی اخبار"]')?.value ?? null,
  }));
  check("پاک کردن فیلترها فهرست را برمی‌گرداند", afterClear.rows >= 1, `rows=${afterClear.rows}`);
  check("ورودی جست‌وجو پاک می‌شود", afterClear.inputValue === "", `value=${afterClear.inputValue}`);

  await page.goto(`${WEB}/#/sources`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  const emptySources = await page.evaluate(() => ({
    text: document.querySelector(".empty")?.textContent ?? "",
    hasAction: [...document.querySelectorAll(".empty button")].some((b) =>
      b.textContent?.includes("افزودن اولین منبع"),
    ),
  }));
  check("empty state علت و اقدام بعدی دارد", emptySources.text.includes("هنوز منبعی ثبت نشده"), emptySources.text.slice(0, 40));
  check("دکمهٔ اقدام در empty state", emptySources.hasAction);
  await context.close();
}

await browser.close();
console.log(JSON.stringify({ results, failures }, null, 2));
if (failures.length) {
  console.error(`FAILED ${failures.length} check(s)`);
  process.exitCode = 1;
}
