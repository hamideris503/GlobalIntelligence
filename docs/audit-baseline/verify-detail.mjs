/**
 * F03.UX.4 — runtime verification of the article detail decision surface.
 * Test-only interception; the app ships no mock data.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-detail.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";
const failures = [];
const check = (name, cond, detail) => {
  if (!cond) failures.push(`${name}${detail ? ` → ${detail}` : ""}`);
};

const fixtures = {
  "/api/classify/articles/a1": {
    id: "a1",
    title: "خبر نمونه برای بازبینی",
    topics: ["economy", "markets"],
    entities: [{ name: "بانک مرکزی", type: "ORG" }],
    sentiment: -0.2,
    stance: "critical",
    importance: 2,
    decided_by: "rules",
    confidence: 0.73,
    priority: "P1",
    summary: "خلاصهٔ نمونه",
    language: "fa",
    country: "IR",
    source_name: "منبع نمونه",
    url: "https://example.com/a1",
    published_at: "2026-10-31T10:00:00Z",
    retrieved_at: "2026-11-01T09:00:00Z",
    event_id: null,
    classification_status: "done",
    classification_error: null,
    provider: "mock",
    is_mock: true,
  },
  "/api/dispatch/articles/a1": {
    article_id: "a1",
    screening: { status: "relevant", probability: 0.81, review_reasons: "LOW_MARGIN" },
    domains: null,
    dispatches: [
      { task: "classification", status: "completed", attempts: 1, last_error: null, next_retry_at: null },
      { task: "claim_extraction", status: "retryable", attempts: 2, last_error: "timeout", next_retry_at: "2026-11-01T12:00:00Z" },
    ],
  },
  "/api/dedup/clusters": [
    { article_id: "a1", document_id: "d1", source_id: "s1", cluster: "cl-1" },
    { article_id: "a2", document_id: "d2", source_id: "s2", cluster: "cl-1" },
    { article_id: "a3", document_id: "d3", source_id: "s3", cluster: "cl-2" },
  ],
};

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
await page.route("**/localhost:8000/**", async (route) => {
  const url = new URL(route.request().url());
  const body = fixtures[url.pathname];
  if (body === undefined) {
    return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  }
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
});

await page.goto(`${WEB}/#/news/article-a1`, { waitUntil: "networkidle" });
await page.waitForSelector(".detail");

const facts = await page.evaluate(() => {
  const panel = (title) =>
    [...document.querySelectorAll(".panel")].find((p) => p.querySelector("h2")?.textContent === title);
  const priorityBadges = [...document.querySelectorAll(".badge-prio")].map((b) => ({
    text: b.textContent?.trim(),
    level: b.getAttribute("data-priority"),
  }));
  const provenanceKeys = [...(panel("جزئیات مقاله")?.querySelectorAll(".kv dt") ?? [])].map((d) => d.textContent?.trim());
  const procRows = [...(panel("وضعیت پردازش")?.querySelectorAll("tbody tr") ?? [])].map((tr) =>
    [...tr.querySelectorAll("td")].map((td) => td.textContent?.trim()),
  );
  const clusterButtons = [...(panel("خوشهٔ تکراری")?.querySelectorAll(".list button") ?? [])].map((b) => b.textContent?.trim());
  const screeningDts = [...(panel("وضعیت پردازش")?.querySelectorAll(".subhead") ?? [])].map((h) => h.textContent?.trim());
  return {
    h2: document.querySelector(".detail h2")?.textContent ?? null,
    priorityBadges,
    provenanceKeys,
    procRows,
    clusterButtons,
    screeningHeadings: screeningDts,
    hasBack: [...document.querySelectorAll("button")].some((b) => b.textContent?.includes("بازگشت به فهرست")),
    urlLink: document.querySelector(".detail a")?.getAttribute("href") ?? null,
    pageAlerts: document.querySelectorAll('[role="alert"]').length,
  };
});

check("عنوان مقاله نمایش داده می‌شود", facts.h2 === "خبر نمونه برای بازبینی", facts.h2);
check("اولویت P1 با متن رندر می‌شود", facts.priorityBadges.some((b) => b.text === "P1" && b.level === "P1"), JSON.stringify(facts.priorityBadges));
check("provenance شامل منبع/پیوند/زمان است",
  ["منبع", "پیوند اصلی", "انتشار", "دریافت", "شناسهٔ داخلی"].every((k) => facts.provenanceKeys.includes(k)),
  JSON.stringify(facts.provenanceKeys));
check("لینک اصلی به URL واقعی اشاره می‌کند", facts.urlLink === "https://example.com/a1", String(facts.urlLink));
check("timeline هر دو وظیفه را نشان می‌دهد", facts.procRows.length === 2, `rows=${facts.procRows.length}`);
check("خطای وظیفهٔ retryable دیده می‌شود", JSON.stringify(facts.procRows).includes("timeout"));
check("وضعیت وظیفه به فارسی برچسب می‌خورد", JSON.stringify(facts.procRows).includes("قابل تلاش مجدد"));
check("غربالگری خام نمایش داده می‌شود", facts.screeningHeadings.some((h) => h?.includes("غربالگری")), JSON.stringify(facts.screeningHeadings));
check("خوشهٔ تکراری فقط مقالهٔ دیگر (a2) را نشان می‌دهد", facts.clusterButtons.length === 1 && facts.clusterButtons[0] === "a2", JSON.stringify(facts.clusterButtons));
check("هیچ خطای صفحه‌ای وجود ندارد", facts.pageAlerts === 0, `alerts=${facts.pageAlerts}`);
check("بازگشت به فهرست موجود است", facts.hasBack);

// sibling link navigates to the other article
await page.getByRole("button", { name: "a2" }).click();
await page.waitForTimeout(400);
const nav = await page.evaluate(() => location.hash);
check("لینک خوشه به مقالهٔ دیگر می‌رود", nav === "#/news/article-a2", nav);

await context.close();
await browser.close();
console.log(JSON.stringify({ facts, failures }, null, 2));
if (failures.length) {
  console.error(`FAILED ${failures.length} check(s)`);
  process.exitCode = 1;
}
