/** Unified Backend API layer (UI redesign).
 *
 * - Base URL: VITE_API_BASE_URL (build-time) with optional in-memory override.
 * - Internal API key: held ONLY in memory (React state), never persisted to
 *   localStorage / URL / logs (per security spec).
 * - Timeouts via AbortController; network/API errors mapped to Persian messages.
 */

const BAKED_BASE: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

let baseOverride = "";
let apiKey = "";

export function getApiBase(): string {
  return baseOverride || BAKED_BASE;
}

export function setApiBase(url: string): void {
  baseOverride = url.trim().replace(/\/+$/, "");
}

export function getApiKey(): string {
  return apiKey;
}

export function setApiKey(key: string): void {
  apiKey = key;
}

export function hasApiKey(): boolean {
  return apiKey.length > 0;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function faError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) return "کلید API نامعتبر است یا وارد نشده است.";
    if (e.status === 403) return "دسترسی مجاز نیست.";
    if (e.status === 404) return "موردی یافت نشد.";
    if (e.status === 409) return "رکورد تکراری است.";
    if (e.status === 422) return "ورودی نامعتبر است.";
    if (e.status === 429) return "درخواست‌ها بیش از حد مجاز است؛ کمی صبر کنید.";
    if (e.status >= 500) return "خطای سرور؛ بعداً تلاش کنید.";
    return `خطا: ${e.status}`;
  }
  if (e instanceof DOMException && e.name === "AbortError")
    return "مهلت درخواست تمام شد.";
  if (e instanceof TypeError) return "ارتباط با سرور برقرار نشد.";
  return "خطای ناشناخته.";
}

export async function fetchJson<T>(
  path: string,
  init?: RequestInit,
  timeoutMs = 30000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
      ...((init?.headers as Record<string, string> | undefined) ?? {}),
    };
    const res = await fetch(`${getApiBase()}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
    if (!res.ok) {
      let message = res.statusText;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === "string") message = body.detail;
        else if (Array.isArray(body.detail))
          message = body.detail
            .map((d) => (typeof d === "object" && d !== null && "msg" in d ? String((d as { msg: unknown }).msg) : "ورودی نامعتبر"))
            .join("؛ ");
      } catch {
        /* keep statusText */
      }
      // هرگز کلید یا جزئیات حساس را در پیام نگه ندار
      throw new ApiError(res.status, message);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: <T>(path: string, timeoutMs?: number) =>
    fetchJson<T>(path, undefined, timeoutMs),
  post: <T>(path: string, body?: unknown, timeoutMs = 60000) =>
    fetchJson<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }, timeoutMs),
  patch: <T>(path: string, body?: unknown) =>
    fetchJson<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    fetchJson<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  remove: <T>(path: string) => fetchJson<T>(path, { method: "DELETE" }),
};
