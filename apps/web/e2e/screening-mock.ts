/** Local E2E mock backend for the screening / dispatch operations page.
 *
 * Mirrors the real contracts verified in tests/test_screening_ops.py:
 * - the review queue is derived from persisted reasons, never from priority;
 * - an acknowledgement is additive and the item stays review-required;
 * - dispatch status is read verbatim and only a retryable row can be retried.
 * Every /api path that is not mocked returns 404; non-local requests abort.
 */
import type { Page, Route } from "@playwright/test";

export interface ReviewItem {
  article_id: string;
  title: string;
  article_url: string | null;
  source_name: string | null;
  priority: string | null;
  priority_source: string | null;
  classification_status: string | null;
  classification_error: string | null;
  retrieved_at: string | null;
  screening: Record<string, unknown> | null;
  domains?: string[] | null;
  domain_state?: string | null;
  screening_status: string;
  review_required: boolean;
  review_reasons: string[];
  review_acknowledged: boolean;
  acknowledged_at: string | null;
}

export interface DispatchJob {
  dispatch_id: string;
  article_id: string;
  title: string;
  article_url: string | null;
  priority: string | null;
  task: string;
  task_version: string;
  status: string;
  attempts: number;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
  next_retry_at: string | null;
  can_retry: boolean;
  screening_status: string;
  review_required: boolean;
  review_reasons: string[];
  review_acknowledged: boolean;
}

export interface ScreeningMockState {
  items: ReviewItem[];
  jobs: DispatchJob[];
  runtime: Record<string, unknown>;
  saved: Record<string, string>;
  runtimeCount: number;
  inflight: number;
  maxConcurrent: number;
  seen: string[];
}

function reviewItem(over: Partial<ReviewItem> & { article_id: string; title: string }): ReviewItem {
  return {
    article_url: `https://example.test/${over.article_id}`,
    source_name: "MockSrc",
    priority: "P2",
    priority_source: "rules",
    classification_status: "done",
    classification_error: null,
    retrieved_at: "2026-10-24T10:00:00+00:00",
    screening: {
      scope_rule_version: "relevance_scope_v2",
      route: "KEV_LAYA",
      decision: null,
      reason_codes: ["LOW_MARGIN"],
      fallback_used: true,
      p0_p1_safeguard: false,
    },
    domains: null,
    domain_state: null,
    screening_status: "pending",
    review_required: false,
    review_reasons: [],
    review_acknowledged: false,
    acknowledged_at: null,
    ...over,
  };
}

function job(over: Partial<DispatchJob> & { dispatch_id: string; status: string }): DispatchJob {
  return {
    article_id: "art-1",
    title: `مقاله ${over.dispatch_id}`,
    article_url: null,
    priority: "P1",
    task: "event_extraction",
    task_version: "1",
    attempts: 0,
    last_error: null,
    created_at: "2026-10-24T09:00:00+00:00",
    updated_at: "2026-10-24T09:10:00+00:00",
    next_retry_at: null,
    can_retry: false,
    screening_status: "relevant",
    review_required: false,
    review_reasons: [],
    review_acknowledged: false,
    ...over,
  };
}

export function baseState(): ScreeningMockState {
  return {
    items: [
      reviewItem({
        article_id: "rev-1",
        title: "مرور کم‌حاشیه",
        priority: "P1",
        review_required: true,
        review_reasons: ["LOW_MARGIN", "AI_ABSTAINED"],
        screening: {
          scope_rule_version: "relevance_scope_v2",
          route: "KEV_LAYA",
          decision: null,
          reason_codes: ["LOW_MARGIN", "AI_ABSTAINED"],
          fallback_used: true,
          p0_p1_safeguard: false,
        },
      }),
      reviewItem({
        article_id: "rev-guard",
        title: "محافظ اولویت",
        priority: "P0",
        review_required: true,
        review_reasons: ["P0_P1_SAFEGUARD", "PRIORITY_REVIEW"],
        screening: {
          scope_rule_version: "relevance_scope_v2",
          route: "KEV_LAYA",
          decision: null,
          reason_codes: ["P0_P1_SAFEGUARD", "PRIORITY_REVIEW"],
          fallback_used: true,
          p0_p1_safeguard: true,
        },
      }),
      reviewItem({
        article_id: "rev-p2",
        title: "مرور کم‌اهمیت",
        priority: "P2",
        review_required: true,
        review_reasons: ["DISAGREEMENT"],
      }),
      reviewItem({
        article_id: "p0-clean",
        title: "اولویت بالا بدون بازبینی",
        priority: "P0",
        screening_status: "relevant",
        review_required: false,
        review_reasons: [],
        domains: ["macro", "markets"],
        domain_state: "pending",
        screening: {
          scope_rule_version: "relevance_scope_v2",
          route: "KEV_LAYA",
          decision: true,
          reason_codes: ["BOTH_RELEVANT"],
          fallback_used: false,
          p0_p1_safeguard: false,
        },
      }),
      reviewItem({
        article_id: "out-2",
        title: "نتیجه نامرتبط",
        priority: "P3",
        screening_status: "not_relevant",
        review_required: false,
        review_reasons: [],
        screening: {
          scope_rule_version: "relevance_scope_v2",
          route: "KEV",
          decision: false,
          reason_codes: ["KEV_NOT_RELEVANT"],
          fallback_used: false,
          p0_p1_safeguard: false,
        },
      }),
    ],
    jobs: [
      job({ dispatch_id: "job-complete", status: "completed", attempts: 1, task: "classification" }),
      job({
        dispatch_id: "job-retry",
        status: "retryable",
        attempts: 2,
        last_error: "temporary upstream timeout",
        next_retry_at: "2026-10-24T10:30:00+00:00",
        can_retry: true,
        screening_status: "pending",
        review_required: true,
        review_reasons: ["LOW_MARGIN"],
      }),
      job({
        dispatch_id: "job-terminal",
        status: "terminal",
        attempts: 3,
        last_error: "max attempts reached: timeout",
      }),
    ],
    runtime: {
      kev: {
        name: "kev",
        enabled: true,
        state: "ENABLED_NOT_LOADED",
        pid: null,
        last_error: null,
        load_time_ms: null,
        last_inference_ms: null,
      },
      laya: {
        name: "laya",
        enabled: false,
        state: "DISABLED",
        pid: null,
        last_error: null,
        load_time_ms: null,
        last_inference_ms: null,
      },
    },
    saved: {
      kev_local_screening_enabled: "true",
      laya_local_screening_enabled: "false",
      local_screening_idle_unload_seconds: "300",
    },
    runtimeCount: 0,
    inflight: 0,
    maxConcurrent: 0,
    seen: [],
  };
}

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "access-control-allow-origin": "*" },
    body: JSON.stringify(body),
  });
}

export async function installScreeningMock(
  page: Page, state: ScreeningMockState,
): Promise<ScreeningMockState> {
  await page.route(/^(https?:\/\/)(?!127\.0\.0\.1|localhost)/, async (route) => {
    state.seen.push(route.request().url());
    await route.abort();
  });
  await page.route(/http:\/\/localhost:8000\/health$/, async (route) => {
    state.seen.push(route.request().url());
    return json(route, 200, { status: "ok" });
  });
  await page.route(/http:\/\/localhost:8000\/api\/.*/, async (route) => {
    const req = route.request();
    state.seen.push(req.url());
    const path = new URL(req.url()).pathname;
    const query = new URL(req.url()).searchParams;

    if (req.method() === "OPTIONS") {
      await route.fulfill({
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-headers": "*",
          "access-control-allow-methods": "*",
        },
      });
      return;
    }

    if (req.method() === "GET" && path === "/api/ai/status") {
      return json(route, 200, { mock_mode: true, default_provider: "mock" });
    }
    if (req.method() === "GET" && path === "/api/alerts") {
      return json(route, 200, []);
    }
    if (req.method() === "GET" && path === "/api/ops/monitoring") {
      return json(route, 200, { status: "ok", checks: [] });
    }

    if (req.method() === "GET" && path === "/api/screening/queue") {
      const wantsReview = query.get("review_required") !== "false";
      const acknowledged = query.get("acknowledged");
      const p0p1 = query.get("p0_p1") === "true";
      const screening = query.get("screening");
      let rows = state.items.filter((i) => i.review_required === wantsReview);
      if (acknowledged === "false") rows = rows.filter((i) => !i.review_acknowledged);
      if (p0p1) rows = rows.filter((i) => i.priority === "P0" || i.priority === "P1");
      if (screening) rows = rows.filter((i) => i.screening_status === screening);
      const pageNo = Number(query.get("page") ?? 1);
      const pageSize = Number(query.get("page_size") ?? 20);
      const start = (pageNo - 1) * pageSize;
      return json(route, 200, {
        items: rows.slice(start, start + pageSize),
        page: pageNo,
        page_size: pageSize,
        has_more: rows.length > start + pageSize,
      });
    }

    const ack = path.match(/^\/api\/screening\/review\/([^/]+)\/ack$/);
    if (req.method() === "POST" && ack) {
      const item = state.items.find((i) => i.article_id === ack[1]);
      if (!item) return json(route, 404, { detail: "article not found" });
      const already = item.review_acknowledged;
      item.review_acknowledged = true;
      item.acknowledged_at = "2026-10-24T10:02:00+00:00";
      return json(route, 200, { ...item, already_acknowledged: already, human_review: {} });
    }

    if (req.method() === "GET" && path === "/api/dispatch/jobs") {
      const status = query.get("status");
      const task = query.get("task");
      const review = query.get("review_required");
      const p0p1 = query.get("p0_p1") === "true";
      let rows = [...state.jobs];
      if (status) rows = rows.filter((j) => j.status === status);
      if (task) rows = rows.filter((j) => j.task === task);
      if (review === "true") rows = rows.filter((j) => j.review_required);
      if (p0p1) rows = rows.filter((j) => j.priority === "P0" || j.priority === "P1");
      return json(route, 200, { items: rows, page: 1, page_size: 20, has_more: false });
    }

    const retry = path.match(/^\/api\/dispatch\/([^/]+)\/retry$/);
    if (req.method() === "POST" && retry) {
      const item = state.jobs.find((j) => j.dispatch_id === retry[1]);
      if (!item) return json(route, 404, { detail: "dispatch not found" });
      if (item.status !== "retryable" && item.status !== "pending") {
        return json(route, 409, { detail: `dispatch is ${item.status}` });
      }
      item.status = "pending";
      item.can_retry = false;
      item.next_retry_at = "2026-10-24T10:05:00+00:00";
      return json(route, 200, item);
    }

    if (req.method() === "GET" && path === "/api/local-runtimes/status") {
      state.runtimeCount += 1;
      state.inflight += 1;
      state.maxConcurrent = Math.max(state.maxConcurrent, state.inflight);
      // Slow response makes overlapping polls observable.
      await new Promise((resolve) => setTimeout(resolve, 1200));
      await json(route, 200, state.runtime);
      state.inflight -= 1;
      return;
    }

    if (req.method() === "GET" && path === "/api/settings/app") {
      return json(route, 200, state.saved);
    }

    return json(route, 404, {});
  });
  return state;
}
