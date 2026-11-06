/**
 * F03.UX.1 — runtime check for the shared Tabs primitive (keyboard + ARIA).
 * Read-only: drives the built app, asserts DOM state, prints JSON.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-tabs.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await page.goto(`${WEB}/#/news`, { waitUntil: "networkidle" });
await page.waitForSelector('[role="tablist"]');

const initial = await page.evaluate(() => {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  return {
    count: tabs.length,
    selected: tabs.map((t) => t.getAttribute("aria-selected")),
    tabIndexes: tabs.map((t) => t.getAttribute("tabindex")),
    controls: tabs.map((t) => t.getAttribute("aria-controls")),
    panels: tabs.map((t) => !!document.getElementById(t.getAttribute("aria-controls") ?? "")),
  };
});

// RTL: ArrowLeft must move to the next tab (visual direction, not DOM order).
await page.focus('[role="tab"]:first-child');
await page.keyboard.press("ArrowLeft");
const afterArrow = await page.evaluate(() => {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  return {
    selected: tabs.map((t) => t.getAttribute("aria-selected")),
    focused: document.activeElement?.getAttribute("role") === "tab"
      ? document.activeElement.id
      : null,
    visiblePanel: [...document.querySelectorAll('[role="tabpanel"]')].map((p) => p.id),
  };
});

// Home returns to the first tab.
await page.keyboard.press("Home");
const afterHome = await page.evaluate(() => {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  return { selected: tabs.map((t) => t.getAttribute("aria-selected")), focused: document.activeElement?.id ?? null };
});

await browser.close();
console.log(JSON.stringify({ initial, afterArrow, afterHome }, null, 2));
