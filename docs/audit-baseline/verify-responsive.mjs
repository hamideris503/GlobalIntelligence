/**
 * F03.UX.6 — responsive / RTL / keyboard sweep.
 *
 * Measures real layout facts at 360 / 768 / 1024 for the primary routes:
 * document overflow, clipped panels, squeezed key-value grids, table scroll
 * containers (and whether they are keyboard reachable), tab-strip clipping,
 * tap-target size and RTL direction.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-responsive.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";
const VIEWPORTS = [
  { name: "360", width: 360, height: 800 },
  { name: "768", width: 768, height: 1024 },
  { name: "1024", width: 1024, height: 768 },
];
const ROUTES = ["dashboard", "news", "sources", "screening", "settings", "ops", "archive"];

const browser = await chromium.launch();
const rows = [];

for (const vp of VIEWPORTS) {
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  const page = await context.newPage();
  for (const route of ROUTES) {
    await page.goto(`${WEB}/#/${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);
    const facts = await page.evaluate(() => {
      const de = document.documentElement;
      const rect = (el) => el.getBoundingClientRect();
      const overflowing = [];
      for (const el of document.querySelectorAll("main .card, main .panel, main .kpi, main table")) {
        const r = rect(el);
        if (r.right > window.innerWidth + 2 || r.left < -2) {
          overflowing.push((el.className || el.tagName).toString().slice(0, 32));
        }
      }
      const kv = [...document.querySelectorAll(".kv")].map((dl) => {
        const dt = dl.querySelector("dt");
        const dd = dl.querySelector("dd");
        return {
          dtWidth: dt ? Math.round(rect(dt).width) : 0,
          ddWidth: dd ? Math.round(rect(dd).width) : 0,
        };
      });
      const tables = [...document.querySelectorAll(".tablewrap")].map((w) => ({
        scrollable: w.scrollWidth > w.clientWidth + 1,
        keyboardReachable: w.getAttribute("tabindex") !== null,
        role: w.getAttribute("role"),
        hint: !!w.parentElement?.querySelector(".tablehint"),
      }));
      const tabs = [...document.querySelectorAll(".tabs")].map((t) => ({
        clipped: t.scrollWidth > t.clientWidth + 1,
        scrollableX: getComputedStyle(t).overflowX,
      }));
      const smallTargets = [...document.querySelectorAll("button, a[href], input, select")]
        .map((el) => rect(el))
        .filter((r) => r.width > 0 && (r.height < 36 || r.width < 36)).length;
      return {
        dir: de.dir,
        docOverflow: de.scrollWidth > window.innerWidth + 1,
        overflowing,
        kv,
        tables,
        tabs,
        smallTargets,
        h1: document.querySelector("main h1")?.textContent ?? null,
      };
    });
    rows.push({ viewport: vp.name, route, ...facts });
  }
  await context.close();
}

await browser.close();

const issues = [];
for (const r of rows) {
  if (r.docOverflow) issues.push(`${r.viewport}/${r.route}: document overflow (${r.docOverflow})`);
  if (r.overflowing.length) issues.push(`${r.viewport}/${r.route}: clipped elements ${r.overflowing.join(",")}`);
  if (r.kv.some((k) => k.ddWidth > 0 && k.ddWidth < 120)) issues.push(`${r.viewport}/${r.route}: squeezed kv value (<120px)`);
  if (r.tables.some((t) => t.scrollable && !t.keyboardReachable)) issues.push(`${r.viewport}/${r.route}: table scroll not keyboard reachable`);
  if (r.tables.some((t) => t.scrollable && !t.hint)) issues.push(`${r.viewport}/${r.route}: table scroll without hint`);
  if (r.dir !== "rtl") issues.push(`${r.viewport}/${r.route}: dir=${r.dir}`);
}

console.log(JSON.stringify({ rows, issues }, null, 2));
if (issues.length) {
  console.error(`ISSUES ${issues.length}`);
  process.exitCode = 1;
}
