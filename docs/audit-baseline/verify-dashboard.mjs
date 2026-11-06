/**
 * F03.UX.3 — runtime verification of the dashboard KPI contract.
 *
 * Test-only fixtures are served through Playwright request interception so the
 * KPI states (fresh / stale / unknown / error) can be asserted deterministically.
 * The app itself never ships mock data.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-dashboard.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";
const H = 3600_000;
const D = 24 * H;
const now = Date.now();
const iso = (msAgo) => new Date(now - msAgo).toISOString();

const fixtures = {
  "/api/ops/status": {
    database_ok: true,
    counts: { sources: 2, documents: 30, articles: 12, events: 4, forecasts: 5 },
    last_jobs: [
      { job_name: "ingest", status: "ok", source: "a" },
      { job_name: "classify", status: "failed", source: "b" },
    ],
    latest_self_eval: { score: null, grade: null },
    active_alerts: 2,
    latest_world_state: { macro_regime: "neutral", market_regime: "risk_off" },
  },
  "/api/sources?limit=200": [
    { id: "s1", name: "A", active: true, last_error: null, last_success: iso(2 * H) },
    { id: "s2", name: "B", active: true, last_error: "timeout", last_success: iso(3 * D) },
  ],
  "/api/classify/articles?limit=200": [
    { id: "a1", title: "خبر تست", topics: ["economy"], importance: 2, sentiment: 0, priority: 1, retrieved_at: iso(H) },
  ],
  "/api/world-state/current": { macro_regime: "neutral", market_regime: "risk_off", confidence: 0.5, geopolitical_risk: 0.4 },
  "/api/risk/overview": [],
  "/api/markets/latest": [],
  "/api/briefings?limit=4": [],
};

const failures = [];
const check = (name, cond, detail) => {
  if (!cond) failures.push(`${name}${detail ? ` → ${detail}` : ""}`);
};

const browser = await chromium.launch();
const out = {};

// ---------- 1) populated dashboard (test fixtures) ----------
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await page.route("**/localhost:8000/**", async (route) => {
    const url = new URL(route.request().url());
    const key = url.pathname + (url.search || "");
    const body = fixtures[key];
    if (body === undefined) return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto(`${WEB}/#/dashboard`, { waitUntil: "networkidle" });
  await page.waitForSelector(".card.kpi");

  out.kpis = await page.evaluate(() => {
    const cards = [...document.querySelectorAll(".card.kpi")];
    return cards.map((c) => ({
      label: c.querySelector(".card-label")?.textContent?.trim() ?? null,
      value: c.querySelector(".kpi-value")?.textContent?.trim() ?? null,
      status: c.querySelector(".badge")?.textContent?.trim() ?? null,
      hasDefinition: !!c.querySelector(".kpi-def summary"),
      sourceText: c.querySelector(".kpi-def code")?.textContent?.trim() ?? null,
      asOfText: [...c.querySelectorAll(".kpi-meta")].map((m) => m.textContent?.trim()).join(" | "),
      hasLink: !!c.querySelector(".linkbtn"),
    }));
  });

  check("۶ کارت KPI", out.kpis.length === 6, `got ${out.kpis.length}`);
  check("همهٔ KPIها تعریف دارند", out.kpis.every((k) => k.hasDefinition));
  check("همهٔ KPIها منبع دارند", out.kpis.every((k) => (k.sourceText ?? "").startsWith("GET /api/")));
  check("هیچ KPI بدون مقدار نمایشی (mock) نیست", out.kpis.every((k) => k.value !== null));
  const active = out.kpis.find((k) => k.label === "منابع فعال");
  check("منابع فعال = 2", active?.value?.includes("۲") || active?.value?.includes("2"), active?.value);
  check("دادهٔ ۳ روزه «کهنه» برچسب می‌خورد", active?.status === "کهنه", active?.status);
  const events = out.kpis.find((k) => k.label === "رویدادهای شناسایی‌شده");
  check("KPI بدون مهر زمانی «بدون مهر زمانی» است", events?.status === "بدون مهر زمانی", events?.status);
  const failed = out.kpis.find((k) => k.label === "اجراهای ناموفق");
  check("پنجرهٔ last_jobs در پانویس KPI ذکر شده", (failed?.asOfText ?? "").includes("last_jobs"), failed?.asOfText);

  out.actions = await page.evaluate(() =>
    [...document.querySelectorAll(".panel")]
      .find((p) => p.querySelector("h2")?.textContent === "نیازمند اقدام")
      ?.querySelectorAll(".feed li").length ?? 0,
  );
  check("بخش «نیازمند اقدام» موارد واقعی دارد", out.actions >= 2, `items=${out.actions}`);
  check("بدون دادهٔ احراز، بنر خطا وجود ندارد", await page.evaluate(() => document.querySelectorAll('[role="alert"]').length === 0));

  // KPI deep link → filtered dataset
  await page.getByRole("button", { name: "دیدن منابع دارای خطا" }).click();
  await page.waitForTimeout(400);
  out.deepLink = await page.evaluate(() => ({
    hash: location.hash,
    errorsOnlyChecked: [...document.querySelectorAll("label")].some(
      (l) => l.textContent?.includes("فقط دارای خطا") && l.querySelector("input")?.checked,
    ),
  }));
  check("لینک KPI به فیلتر منبع هدایت می‌کند", out.deepLink.hash === "#/sources/error", out.deepLink.hash);
  check("فیلتر «فقط دارای خطا» فعال است", out.deepLink.errorsOnlyChecked === true);

  // events KPI → events tab
  await page.goto(`${WEB}/#/news/events`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  out.newsEvents = await page.evaluate(() => ({
    selected: document.querySelector('[role="tab"][aria-selected="true"]')?.textContent?.trim() ?? null,
  }));
  check("KPI رویدادها تب رویداد را باز می‌کند", out.newsEvents.selected === "رویدادها", out.newsEvents.selected);

  await context.close();
}

// ---------- 2) signed-out dashboard (real 401s) ----------
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await page.goto(`${WEB}/#/dashboard`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  out.signedOut = await page.evaluate(() => ({
    alerts: document.querySelectorAll('[role="alert"]').length,
    bannerText: document.querySelector(".banner[role='alert']")?.textContent?.slice(0, 60) ?? null,
    panelErrors: [...document.querySelectorAll(".errbox")].length,
  }));
  check("یک خطای احراز = یک بنر (نه هشت)", out.signedOut.alerts === 1, `alerts=${out.signedOut.alerts}`);
  check("پنل‌ها خطای تکراری نشان نمی‌دهند", out.signedOut.panelErrors === 0, `errbox=${out.signedOut.panelErrors}`);
  await context.close();
}

await browser.close();
console.log(JSON.stringify({ out, failures }, null, 2));
if (failures.length) {
  console.error(`FAILED ${failures.length} check(s)`);
  process.exitCode = 1;
}
