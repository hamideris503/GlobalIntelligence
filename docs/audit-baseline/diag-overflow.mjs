/**
 * F03.UX.6 — overflow diagnostic: names the elements that exceed the viewport,
 * so the cause is fixed instead of hidden with `overflow: hidden`.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/diag-overflow.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";
const browser = await chromium.launch();
const out = {};

for (const width of [360, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 800 } });
  for (const route of ["dashboard", "settings", "news"]) {
    await page.goto(`${WEB}/#/${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(400);
    out[`${width}/${route}`] = await page.evaluate(() => {
      const offenders = [];
      for (const el of document.querySelectorAll("body *")) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        if (r.right > window.innerWidth + 1) {
          offenders.push({
            tag: el.tagName.toLowerCase(),
            cls: (el.className || "").toString().slice(0, 40),
            width: Math.round(r.width),
            right: Math.round(r.right),
          });
        }
      }
      // عناصری که با overflow مشهود، عرض را به والد منتقل می‌کنند (منشأ واقعی overflow)
      const propagators = [];
      for (const el of document.querySelectorAll("body *")) {
        const cs = getComputedStyle(el);
        if (cs.overflowX !== "visible") continue;
        if (el.scrollWidth > el.clientWidth + 1) {
          propagators.push({
            tag: el.tagName.toLowerCase(),
            cls: (el.className || "").toString().slice(0, 36),
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
          });
        }
      }
      return {
        bodyScrollWidth: document.body.scrollWidth,
        htmlClientWidth: document.documentElement.clientWidth,
        htmlMinWidth: getComputedStyle(document.documentElement).minWidth,
        bodyMinWidth: getComputedStyle(document.body).minWidth,
        propagators: propagators.slice(0, 8),
        docScrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth,
        offenders: offenders.slice(0, 15),
        topbarScroll: document.querySelector(".topbar")?.scrollWidth ?? null,
        topbarClient: document.querySelector(".topbar")?.clientWidth ?? null,
      };
    });
  }
  await page.close();
}
await browser.close();
console.log(JSON.stringify(out, null, 2));
