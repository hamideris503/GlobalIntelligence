/** API client (Phase 40).
 *
 * بیشتر endpointها به X-API-Key نیاز دارند؛ کلید در localStorage می‌ماند
 * و از جعبه‌ی بالای داشبورد قابل تنظیم است. بدون کلید فقط health عمومی است.
 */

const API_BASE: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const KEY_NAME = "gi_api_key";

export function getApiKey(): string {
  try {
    return localStorage.getItem(KEY_NAME) ?? "";
  } catch {
    return "";
  }
}

export function setApiKey(key: string): void {
  try {
    localStorage.setItem(KEY_NAME, key);
  } catch {
    /* ignore */
  }
}

export async function fetchJson<T>(path: string): Promise<T> {
  const headers: Record<string, string> = {};
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}
