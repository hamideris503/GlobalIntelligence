/**
 * F03.UX.0 — read-only baseline capture.
 *
 * Captures key routes at desktop/tablet/mobile viewports and records layout +
 * font + error-state facts next to the screenshots. It never writes to the app
 * or the backend; it only reads the already-running local dev servers.
 *
 *   node docs/audit-baseline/capture.mjs
 */
import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import path from "node:path";

// Resolve Playwright from the frontend workspace (already a devDependency).
const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:5173";
const OUT = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));

const VIEWPORTS = [
  { name: "1440", width: 1440, height: 900 },
  { name: "768", width: 768, height: 1024 },
  { name: "390", width: 390, height: 844 },
];

const ROUTES = ["dashboard", "news", "sources", "ai", "settings", "ops", "archive"];

const browser = await chromium.launch();
const report = [];

for (const vp of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: vp.width, height: vp.height },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();
  let consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });

  for (const route of ROUTES) {
    const started = Date.now();
    await page.goto(`${WEB}/#/${route}`, { waitUntil: "networkidle" }).catch(() => {});
    await page.waitForTimeout(600);

    const facts = await page.evaluate(() => {
      const body = getComputedStyle(document.body);
      const main = document.querySelector("main");
      const sidebar = document.querySelector("aside.sidebar");
      const topbar = document.querySelector(".topbar");
      const clipped = [];
      for (const el of document.querySelectorAll(".card, .panel, table, .stat")) {
        const r = el.getBoundingClientRect();
        if (r.right > innerWidth + 2 || r.left < -2) {
          clipped.push((el.className || el.tagName).toString().slice(0, 40));
        }
      }
      const smallTargets = [...document.querySelectorAll("button, a, input, select")]
        .map((el) => el.getBoundingClientRect())
        .filter((r) => r.width > 0 && (r.height < 32 || r.width < 32)).length;
      return {
        title: document.title,
        dir: document.documentElement.dir,
        theme: document.documentElement.dataset.theme,
        fontFamily: body.fontFamily,
        fontSize: body.fontSize,
        viewport: { w: innerWidth, h: innerHeight },
        docScrollWidth: document.documentElement.scrollWidth,
        horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        mainScrollWidth: main ? main.scrollWidth : null,
        sidebarWidth: sidebar ? Math.round(sidebar.getBoundingClientRect().width) : null,
        sidebarVisible: sidebar ? sidebar.getBoundingClientRect().height > 0 : false,
        topbarHeight: topbar ? Math.round(topbar.getBoundingClientRect().height) : null,
        clippedElements: clipped.slice(0, 8),
        smallTargets,
        alertCount: document.querySelectorAll('[role="alert"]').length,
        skeletonCount: document.querySelectorAll(".skeleton").length,
        h1: document.querySelector("main h1")?.textContent ?? null,
        headingCount: document.querySelectorAll("main h1").length,
        panels: document.querySelectorAll("main .panel, main .card").length,
        apiKeyMissingNotice: document.body.innerText.includes("کلید API داخلی"),
      };
    });

    const file = path.join(OUT, `${String(ROUTES.indexOf(route) + 1).padStart(2, "0")}-${route}-${vp.name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    // `facts` contains a `viewport: {w,h}` object; keep the viewport name separately so
    // records stay filterable by name (regression of the first audit run).
    report.push({
      route,
      viewportName: vp.name,
      ms: Date.now() - started,
      consoleErrors: [...new Set(consoleErrors)],
      ...facts,
    });
    consoleErrors = [];
  }
  await context.close();
}

await browser.close();
await writeFile(path.join(OUT, "baseline.json"), JSON.stringify(report, null, 2), "utf8");
console.log(`captured ${report.length} baselines`);
