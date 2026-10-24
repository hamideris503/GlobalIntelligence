/** Local E2E mock backend for AI settings (no network, no secrets).
 *
 * Mirrors the REAL backend contract (verified in tests/test_settings.py):
 * - created models are UNVERIFIED + disabled, regardless of the payload;
 * - enabling requires fresh FREE_VERIFIED, else 422;
 * - verify needs complete evidence + explicit confirm, and never auto-enables;
 * - block needs a reason and disables at once.
 * Handlers below return canned responses per scenario; they do NOT recompute
 * policy. Anything under /api not explicitly mocked returns 404.
 */
import type { Page, Route } from "@playwright/test";

export interface MockModel {
  id: string;
  provider_id: string;
  provider_name: string;
  model_name: string;
  price_in_per_mtok: number | null;
  price_out_per_mtok: number | null;
  enabled: boolean;
  free_status: "UNVERIFIED" | "FREE_VERIFIED" | "REVIEW_REQUIRED" | "BLOCKED";
  free_source_url: string | null;
  free_verified_on: string | null;
  free_review_after: string | null;
  free_limits: string | null;
  free_account_prereqs: string | null;
  free_privacy_notes: string | null;
  free_verified_by: string | null;
  free_blocked_reason: string | null;
}

export interface MockState {
  providers: Array<{
    id: string; name: string; kind: string; base_url: string | null;
    key_set: boolean; key_hint: string; key_source: string; enabled: boolean;
    last_test_status: string | null; last_tested_at: string | null;
  }>;
  models: MockModel[];
  testConnectionResponder:
    | { ok: true }
    | { ok: false; error: string }
    | null;
  /** Optional forced failures (default: follow the contract above). */
  modelsListError: { status: number; body: unknown } | null;
  modelPutError: { status: number; body: unknown } | null;
}

let seq = 0;

export function baseModel(over: Partial<MockModel> & { model_name: string }): MockModel {
  seq += 1;
  return {
    id: `m${seq}`,
    provider_id: "p1",
    provider_name: "G1",
    price_in_per_mtok: null,
    price_out_per_mtok: null,
    enabled: false,
    free_status: "UNVERIFIED",
    free_source_url: null,
    free_verified_on: null,
    free_review_after: null,
    free_limits: null,
    free_account_prereqs: null,
    free_privacy_notes: null,
    free_verified_by: null,
    free_blocked_reason: null,
    ...over,
  };
}

export function baseProviders() {
  return [{
    id: "p1", name: "G1", kind: "groq", base_url: null,
    key_set: true, key_hint: "••••3456", key_source: "db", enabled: true,
    last_test_status: null, last_tested_at: null,
  }];
}

const FRESH_STATUSES = new Set(["FREE_VERIFIED"]);

function fresh(m: MockModel): boolean {
  return FRESH_STATUSES.has(m.free_status);
}

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

/** Install route mocks. Returns the list of requested URLs (locality audit). */
export async function installMockApi(page: Page, state: MockState): Promise<string[]> {
  const seen: string[] = [];
  // 1) block everything external first (specific localhost handlers below win).
  await page.route(/^(https?:\/\/)(?!127\.0\.0\.1|localhost)/, async (route) => {
    seen.push(route.request().url());
    await route.abort();
  });
  // 2) record + serve the API surface used by the settings page.
  await page.route(/http:\/\/localhost:8000\/api\/.*/, async (route) => {
    const req = route.request();
    seen.push(req.url());
    const method = req.method();
    const path = new URL(req.url()).pathname;

    if (method === "GET" && path === "/api/settings/providers") {
      return json(route, 200, state.providers);
    }
    if (method === "POST" && path === "/api/settings/providers") {
      const body = req.postDataJSON() as Record<string, unknown>;
      const p = {
        id: `p${state.providers.length + 1}`,
        name: String(body["name"] ?? "").trim(),
        kind: String(body["kind"] ?? "groq"),
        base_url: (body["base_url"] as string) || null,
        key_set: Boolean(body["api_key"]),
        key_hint: body["api_key"] ? "••••3456" : "not set",
        key_source: "db", enabled: body["enabled"] !== false,
        last_test_status: null, last_tested_at: null,
      };
      state.providers.push(p); // key never echoed back
      return json(route, 200, p);
    }
    const putProvMatch = path.match(/^\/api\/settings\/providers\/([^/]+)$/);
    if (method === "PUT" && putProvMatch) {
      const p = state.providers.find((x) => x.id === putProvMatch[1]);
      if (!p) return json(route, 404, { detail: "provider not found" });
      const body = (req.postDataJSON() ?? {}) as Record<string, unknown>;
      if (typeof body["enabled"] === "boolean") p.enabled = body["enabled"];
      return json(route, 200, p);
    }
    if (method === "GET" && path === "/api/settings/models") {
      if (state.modelsListError) {
        return json(route, state.modelsListError.status, state.modelsListError.body);
      }
      return json(route, 200, state.models);
    }
    if (method === "POST" && path === "/api/settings/models") {
      const body = req.postDataJSON() as Record<string, unknown>;
      const m = baseModel({
        model_name: String(body["model_name"] ?? "").trim(),
        free_source_url: (body["free_source_url"] as string) || null,
        free_limits: (body["free_limits"] as string) || null,
        free_account_prereqs: (body["free_account_prereqs"] as string) || null,
        free_privacy_notes: (body["free_privacy_notes"] as string) || null,
      });
      state.models.push(m); // new models: always UNVERIFIED + disabled
      return json(route, 200, m);
    }
    const putMatch = path.match(/^\/api\/settings\/models\/([^/]+)$/);
    if (method === "PUT" && putMatch) {
      if (state.modelPutError) {
        return json(route, state.modelPutError.status, state.modelPutError.body);
      }
      const m = state.models.find((x) => x.id === putMatch[1]);
      if (!m) return json(route, 404, { detail: "model not found" });
      const body = (req.postDataJSON() ?? {}) as Record<string, unknown>;
      if (body["enabled"] === true && !fresh(m)) {
        return json(route, 422, {
          detail: `cannot enable: model is ${m.free_status}`,
        });
      }
      if (typeof body["enabled"] === "boolean") m.enabled = body["enabled"];
      return json(route, 200, m);
    }
    const verifyMatch = path.match(/^\/api\/settings\/models\/([^/]+)\/verify$/);
    if (method === "POST" && verifyMatch) {
      const m = state.models.find((x) => x.id === verifyMatch[1]);
      if (!m) return json(route, 404, { detail: "model not found" });
      const body = (req.postDataJSON() ?? {}) as Record<string, unknown>;
      const need = ["source_url", "limits", "account_prereqs", "privacy_notes"];
      const missing = need.filter((k) => !String(body[k] ?? "").trim());
      if (body["confirm"] !== true) {
        return json(route, 422, { detail: "explicit confirm=true required" });
      }
      if (missing.length > 0) {
        return json(route, 422, { detail: `incomplete free-tier evidence: ${missing.join(", ")}` });
      }
      m.free_status = "FREE_VERIFIED";
      m.free_source_url = String(body["source_url"]);
      m.free_limits = String(body["limits"]);
      m.free_account_prereqs = String(body["account_prereqs"]);
      m.free_privacy_notes = String(body["privacy_notes"]);
      m.free_verified_on = new Date().toISOString().slice(0, 10);
      m.free_verified_by = "settings";
      m.free_blocked_reason = null;
      return json(route, 200, m); // verified, still disabled
    }
    const blockMatch = path.match(/^\/api\/settings\/models\/([^/]+)\/block$/);
    if (method === "POST" && blockMatch) {
      const m = state.models.find((x) => x.id === blockMatch[1]);
      if (!m) return json(route, 404, { detail: "model not found" });
      const body = (req.postDataJSON() ?? {}) as Record<string, unknown>;
      if (String(body["reason"] ?? "").trim().length < 3) {
        return json(route, 422, { detail: "reason too short" });
      }
      m.free_status = "BLOCKED";
      m.free_blocked_reason = String(body["reason"]).trim();
      m.enabled = false;
      return json(route, 200, m);
    }
    const testMatch = path.match(/^\/api\/settings\/providers\/([^/]+)\/test$/);
    if (method === "POST" && testMatch) {
      const r = state.testConnectionResponder ?? { ok: true };
      if (r.ok) {
        return json(route, 200, {
          ok: true, provider: "G1", model: "m-test",
          prompt_tokens: 10, completion_tokens: 5, total_tokens: 15,
          latency_ms: 12.5, error: null,
        });
      }
      return json(route, 200, {
        ok: false, provider: "G1", model: null,
        prompt_tokens: null, completion_tokens: null, total_tokens: null,
        latency_ms: null, error: r.error,
      });
    }
    return json(route, 404, {});
  });
  return seen;
}
