/** Local E2E mock backend for the news page (no network, no secrets).
 *
 * Mirrors the real read model verified in tests/test_classification.py: the
 * article list/detail carry `priority` (the document's ingest P0..P4) next to
 * the analytic `importance`. Handlers return canned rows only; any path under
 * /api that is not mocked returns 404.
 */
import type { Page, Route } from "@playwright/test";

export interface MockArticle {
  id: string;
  title: string | null;
  topics: string[];
  entities: { name: string; type: string }[];
  sentiment: number | null;
  stance: string | null;
  importance: number | null;
  confidence: number | null;
  priority: string | null;
}

/** A complete article row; override only what a scenario cares about. */
export function mockArticle(over: Partial<MockArticle> & { id: string }): MockArticle {
  return {
    title: `خبر ${over.id}`,
    topics: ["economy"],
    entities: [],
    sentiment: 0,
    stance: null,
    importance: 4,
    confidence: 0.9,
    priority: "P2",
    ...over,
  };
}

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/** Install news-page route mocks. Returns requested URLs (locality audit). */
export async function installNewsMock(page: Page, articles: MockArticle[]): Promise<string[]> {
  const seen: string[] = [];
  // Block anything non-local first; the localhost handler below wins for /api.
  await page.route(/^(https?:\/\/)(?!127\.0\.0\.1|localhost)/, async (route) => {
    seen.push(route.request().url());
    await route.abort();
  });
  // The app shell polls /health on every page (`ui.tsx`); it lives outside /api,
  // so it needs its own route or it reaches the real port unmocked.
  await page.route(/http:\/\/localhost:8000\/health$/, async (route) => {
    seen.push(route.request().url());
    return json(route, 200, { status: "ok" });
  });
  await page.route(/http:\/\/localhost:8000\/api\/.*/, async (route) => {
    const req = route.request();
    seen.push(req.url());
    const path = new URL(req.url()).pathname;

    if (req.method() === "GET" && path === "/api/ai/status") {
      // shell status pill reads `mock_mode`; a 404 here used to log a console error
      return json(route, 200, { mock_mode: true, default_provider: "mock" });
    }
    const detail = path.match(/^\/api\/classify\/articles\/([^/]+)$/);
    if (req.method() === "GET" && detail) {
      const found = articles.find((a) => a.id === detail[1]);
      if (!found) return json(route, 404, { detail: "article not found" });
      return json(route, 200, {
        ...found,
        summary: "خلاصه‌ی ساختگی",
        language: "en",
        country: null,
        source_name: "MockSrc",
        url: null,
        published_at: null,
        retrieved_at: null,
        event_id: null,
        classification_status: "done",
        classification_error: null,
        provider: "mock",
        is_mock: true,
      });
    }
    if (req.method() === "GET" && path === "/api/classify/articles") {
      return json(route, 200, articles);
    }
    if (req.method() === "GET" && path === "/api/events") {
      return json(route, 200, []);
    }
    return json(route, 404, {});
  });
  return seen;
}
