/**
 * F03.UX.2 — runtime verification for the app shell.
 * Read-only: drives the built app and asserts DOM/focus behaviour.
 *
 *   AUDIT_WEB_URL=http://localhost:4173 node docs/audit-baseline/verify-shell.mjs
 */
import { createRequire } from "node:module";

const require = createRequire(new URL("../../apps/web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

const WEB = process.env.AUDIT_WEB_URL ?? "http://localhost:4173";
const out = {};

const browser = await chromium.launch();

// ---------- desktop ----------
{
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`${WEB}/#/dashboard`, { waitUntil: "networkidle" });
  await page.waitForSelector(".topbar");

  out.desktop = await page.evaluate(() => {
    const nav = [...document.querySelectorAll("aside.sidebar .navitem")];
    const labels = nav.map((b) => (b.textContent ?? "").trim());
    const groups = [...document.querySelectorAll(".nav-title")].map((g) => g.textContent);
    const paths = [...document.querySelectorAll("aside.sidebar nav .navitem svg path")].map(
      (p) => p.getAttribute("d"),
    );
    const skip = document.querySelector(".skip-link");
    return {
      groups,
      itemCount: nav.length,
      untranslated: labels.filter((l) => /Settings|Archive/.test(l)),
      uniqueIcons: new Set(paths).size,
      iconCount: paths.length,
      skipLinkText: skip?.textContent ?? null,
      topbarTitleVisible: !!document.querySelector(".topbar-title")?.getClientRects().length,
      searchboxVisible: !!document.querySelector(".searchbox")?.getClientRects().length,
    };
  });

  // Focus must move into main after a route change.
  await page.getByRole("button", { name: "منابع اطلاعاتی" }).click();
  await page.waitForTimeout(400);
  out.focusAfterNav = await page.evaluate(() => ({
    activeId: document.activeElement?.id ?? null,
    activeTag: document.activeElement?.tagName ?? null,
    announcer: document.querySelector("[role='status'].sr-only")?.textContent ?? null,
  }));

  // Unknown hash must not silently render the dashboard.
  await page.goto(`${WEB}/#/does-not-exist`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  out.notFound = await page.evaluate(() => ({
    h1: document.querySelector("main h1")?.textContent ?? null,
    recoverButtons: [...document.querySelectorAll("main button")].map((b) => b.textContent?.trim()),
  }));
  await page.close();
}

// ---------- mobile ----------
{
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto(`${WEB}/#/dashboard`, { waitUntil: "networkidle" });
  await page.waitForSelector(".topbar");

  out.mobile = await page.evaluate(() => {
    const pill = document.querySelector(".statuspill .lbl");
    const cs = pill ? getComputedStyle(pill) : null;
    return {
      desktopSearchHidden: !document.querySelector(".searchbox")?.getClientRects().length,
      searchButtonVisible: [...document.querySelectorAll(".topbar .only-mobile")].some(
        (b) => b.getAttribute("aria-label") === "جست‌وجوی سراسری" && b.getClientRects().length > 0,
      ),
      // Visually hidden but still exposed to assistive tech (not display:none).
      statusLabelText: pill?.textContent ?? null,
      statusLabelVisuallyHidden: cs?.position === "absolute" && cs?.width === "1px",
    };
  });

  await page.getByRole("button", { name: "جست‌وجوی سراسری" }).click();
  await page.waitForSelector(".msearchrow", { timeout: 4000 });
  out.mobileSearch = await page.evaluate(() => ({
    rowVisible: !!document.querySelector(".msearchrow")?.getClientRects().length,
    focusedLabel: document.activeElement?.getAttribute("aria-label") ?? null,
  }));

  await page.keyboard.press("Escape");
  await page.waitForTimeout(150);

  // Drawer: focus moves inside, Escape closes and returns focus to the trigger.
  await page.getByRole("button", { name: "باز کردن منو" }).click();
  await page.waitForTimeout(200);
  const drawerFocus = await page.evaluate(() => ({
    insideSidebar: !!document.activeElement?.closest("aside.sidebar"),
    label: document.activeElement?.textContent?.trim() ?? null,
  }));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  out.drawer = {
    focusMovedInside: drawerFocus.insideSidebar,
    focusedItem: drawerFocus.label,
    focusReturnedTo: await page.evaluate(() => document.activeElement?.getAttribute("aria-label") ?? null),
    closed: await page.evaluate(() => !document.querySelector("aside.sidebar")?.classList.contains("open")),
  };
  await page.close();
}

await browser.close();
console.log(JSON.stringify(out, null, 2));
