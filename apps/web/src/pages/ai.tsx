/** AI & models: real provider list, connection test, roles, adaptive routes. */
import { useState } from "react";
import { api } from "../api";
import { fa } from "../theme";
import type { AIProvider, AIStatus } from "../types";
import { Badge, Empty, Field, MockTag, RunButton, Section, Table, useApi } from "../ui";

interface GenerateResponse {
  text: string;
  provider: string;
  model: string;
  latency_ms: number | null;
  is_mock: boolean;
}

const ROLE_FA: Record<string, string> = {
  fast_extraction: "استخراج سریع (طبقه‌بندی، موجودیت، برچسب)",
  deep_analysis: "تحلیل عمیق (کلان، ژئوپلیتیک، چندمنبعی)",
  critic: "منتقد (شواهد مخالف و تناقض)",
  report: "گزارش‌نویس (روزانه/هفتگی/مدیریتی)",
  default: "پیش‌فرض",
};

function ConnectionTest() {
  const [prompt, setPrompt] = useState("سلام؛ یک جملهٔ آزمایشی بنویس.");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setResult(null);
    setError(null);
    const started = performance.now();
    try {
      const r = await api.post<GenerateResponse>(
        "/api/ai/generate",
        { messages: [{ role: "user", content: prompt }], temperature: 0.2 },
        90000,
      );
      setResult({ ...r, latency_ms: r.latency_ms ?? Math.round(performance.now() - started) });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "خطا");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <Field label="متن آزمایشی (از طریق Backend ارسال می‌شود؛ کلید روی سرور است)">
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} />
      </Field>
      <button onClick={run} disabled={busy || !prompt.trim()}>
        {busy ? "در حال آزمایش…" : "آزمایش اتصال"}
      </button>
      {error && <p className="err-text">{error}</p>}
      {result && (
        <dl className="kv">
          <dt>ارائه‌دهنده / مدل</dt>
          <dd>
            {result.provider} / {result.model} <MockTag isMock={result.is_mock} />
          </dd>
          <dt>زمان پاسخ</dt>
          <dd>{fa(result.latency_ms, 0)} ms</dd>
          <dt>پاسخ</dt>
          <dd>{result.text.slice(0, 500)}</dd>
        </dl>
      )}
      <p className="hint">
        اگر خطای احراز هویت دیدید، کلید ارائه‌دهنده در فایل `.env` سرور تنظیم نشده است.
        اگر مدل نامعتبر بود، نام مدل سرور (`GEMINI_MODEL` و…) را بررسی کنید.
        اگر اتصال قطع بود، شبکهٔ سرور و آدرس پایه را بررسی کنید.
      </p>
    </div>
  );
}

export default function AI() {
  const [tick, setTick] = useState(0);
  const status = useApi<AIStatus>("/api/ai/status", [tick]);
  const providers = useApi<AIProvider[]>("/api/ai/providers", [tick]);
  const routes = useApi<Record<string, { providers: string[] }>>("/api/ai-routing/routes", [tick]);

  return (
    <div>
      <div className="page-head">
        <h1>هوش مصنوعی و مدل‌ها</h1>
        <button onClick={() => setTick((t) => t + 1)}>به‌روزرسانی</button>
      </div>

      <Section title="حالت اجرا" error={status.error} loading={status.loading}>
        {status.data && (
          <p>
            حالت:{" "}
            <Badge tone={status.data.mock_mode ? "warn" : "ok"}>
              {status.data.mock_mode ? "آزمایشی (Mock)" : "واقعی"}
            </Badge>{" "}
            ارائه‌دهندهٔ پیش‌فرض: <strong>{status.data.default_provider}</strong>
          </p>
        )}
        <p className="hint">
          در حالت آزمایشی همهٔ خروجی‌ها نمونه‌اند و با «نمونه (Mock)» مشخص می‌شوند؛
          بدون کلید پولی هم قابل استفاده است ولی تحلیل واقعی نیست.
        </p>
      </Section>

      <Section title="ارائه‌دهندگان پشتیبانی‌شده" error={providers.error} loading={providers.loading}>
        {providers.data && providers.data.length > 0 ? (
          <Table
            columns={[
              { key: "provider", label: "نام" },
              {
                key: "healthy", label: "اتصال",
                render: (r) => <Badge tone={r.healthy ? "ok" : "bad"}>{r.healthy ? "سالم" : "قطع"}</Badge>,
              },
              { key: "detail", label: "جزئیات", render: (r) => String(r.detail || "—").slice(0, 120) },
            ]}
            rows={providers.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.provider)}
            emptyText="ارائه‌دهنده‌ای گزارش نشد."
          />
        ) : (
          !providers.loading && <Empty text="ارائه‌دهنده‌ای گزارش نشد." />
        )}
        <p className="hint">
          فقط ارائه‌دهنده‌هایی که آداپتور واقعی در Backend دارند اینجا می‌آیند.
          کلیدهای API فقط در فایل `.env` سرور تنظیم می‌شوند و هرگز در مرورگر ذخیره یا نمایش داده نمی‌شوند.
        </p>
      </Section>

      <Section title="آزمایش اتصال" error={null}>
        <ConnectionTest />
      </Section>

      <Section title="نقش‌های مدل" error={status.error} loading={status.loading}>
        {status.data ? (
          <ul className="list">
            {status.data.roles.map((r) => (
              <li key={r}>
                <strong>{r}</strong> — {ROLE_FA[r] ?? "نقش داخلی"}
              </li>
            ))}
          </ul>
        ) : (
          !status.loading && <Empty />
        )}
        <p className="hint">
          تخصیص نقش‌ها در سمت سرور ثابت است؛ زنجیرهٔ تطبیقی زیر بر اساس عملکرد ثبت‌شده پیشنهاد می‌دهد.
        </p>
      </Section>

      <Section title="زنجیرهٔ تطبیقی" error={routes.error} loading={routes.loading}>
        {routes.data && Object.keys(routes.data).length > 0 ? (
          <ul className="list">
            {Object.entries(routes.data).map(([task, info]) => (
              <li key={task}>
                {task}: {(info.providers ?? []).join(" ← ") || "—"}
              </li>
            ))}
          </ul>
        ) : (
          !routes.loading && <Empty text="زنجیره‌ای ثبت نشده است." />
        )}
        <RunButton label="اعمال زنجیرهٔ تطبیقی" path="/api/ai-routing/apply" />
      </Section>
    </div>
  );
}
