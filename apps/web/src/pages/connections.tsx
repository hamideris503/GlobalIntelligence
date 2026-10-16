/** اتصالات و APIها: فقط وضعیت‌های واقعی (health، دیتابیس، ارائه‌دهندگان AI، منابع). */
import { getApiBase } from "../api";
import { faDateTime } from "../theme";
import type { AIProvider, Source } from "../types";
import { Badge, PageHeader, Section, Table, useApi, useApiKey } from "../ui";

export default function Connections() {
  const { keySet } = useApiKey();
  const health = useApi<{ status: string }>("/health", []);
  const db = useApi<{ status: string; database: { ok: boolean; detail: string } }>("/health/db", []);
  const providers = useApi<AIProvider[]>("/api/ai/providers", []);
  const sources = useApi<Source[]>("/api/sources?limit=200", []);

  const tone = (ok: boolean | undefined, err: string | null) => (err ? "warn" : ok ? "ok" : "bad");
  return (
    <div>
      <PageHeader title="اتصالات و APIها" subtitle="وضعیت اتصال رابط به Backend، دیتابیس، ارائه‌دهندگان هوش مصنوعی و منابع داده." />
      <Section title="Backend و دیتابیس" error={null}>
        <dl className="kv">
          <dt>نشانی API</dt><dd><span className="ltr">{getApiBase()}</span></dd>
          <dt>کلید داخلی</dt><dd><Badge tone={keySet ? "ok" : "warn"}>{keySet ? "ثبت‌شده (فقط حافظه)" : "ثبت‌نشده"}</Badge></dd>
          <dt>Backend</dt><dd>{health.loading ? "…" : <Badge tone={tone(health.data?.status === "ok", health.error)}>{health.error ? `نامشخص: ${health.error}` : health.data?.status === "ok" ? "فعال" : "مشکل"}</Badge>}</dd>
          <dt>دیتابیس</dt><dd>{db.loading ? "…" : <Badge tone={tone(db.data?.database.ok, db.error)}>{db.error ? `نامشخص: ${db.error}` : db.data?.database.ok ? "متصل" : `قطع: ${db.data?.database.detail}`}</Badge>}</dd>
        </dl>
      </Section>
      <Section title="ارائه‌دهندگان هوش مصنوعی" error={providers.error} loading={providers.loading}>
        {providers.data && (
          <Table
            columns={[
              { key: "provider", label: "ارائه‌دهنده" },
              { key: "healthy", label: "اتصال", render: (r) => <Badge tone={r.healthy ? "ok" : "bad"}>{r.healthy ? "سالم" : "ناسالم"}</Badge> },
              { key: "detail", label: "جزئیات" },
            ]}
            rows={providers.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.provider)}
          />
        )}
      </Section>
      <Section title="منابع داده" error={sources.error} loading={sources.loading}>
        {sources.data && (
          <Table
            columns={[
              { key: "name", label: "منبع" },
              { key: "type", label: "نوع" },
              { key: "active", label: "وضعیت", render: (r) => <Badge tone={r.active ? "ok" : "warn"}>{r.active ? "فعال" : "غیرفعال"}</Badge> },
              { key: "last_success", label: "آخرین موفقیت", render: (r) => faDateTime(r.last_success as string | null) },
              { key: "last_error", label: "خطا", render: (r) => (r.last_error ? <span className="err-text">{String(r.last_error).slice(0, 60)}</span> : "—") },
            ]}
            rows={sources.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
          />
        )}
      </Section>
    </div>
  );
}
