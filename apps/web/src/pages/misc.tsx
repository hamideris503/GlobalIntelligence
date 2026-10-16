/** History/reports + ops/jobs/alerts + settings + help + global search. */
import { useState } from "react";
import { api } from "../api";
import { nav } from "../router";
import { faDateTime } from "../theme";
import { Badge, Empty, RunButton, Section, Table, useApi } from "../ui";

interface Briefing { id: string; kind: string; period: string; title: string | null; created_at?: string | null }
interface JobRun { id: string; job_name: string; source: string | null; status: string; message: string | null; started_at: string }
interface AlertItem { id: string; metric: string; value: number | null; message: string | null; severity: string | null; status: string }

export function HistoryPage() {
  const [tick, setTick] = useState(0);
  const list = useApi<Briefing[]>("/api/briefings?limit=50", [tick]);
  const [openId, setOpenId] = useState<string | null>(null);
  const detail = useApi<{ id: string; title: string | null; body: string | null }>(openId ? `/api/briefings/${openId}` : null, [openId]);
  return (
    <div>
      <div className="page-head">
        <h1>تاریخچه و گزارش‌ها</h1>
        <div className="row">
          <RunButton label="گزارش روزانه" path="/api/briefings/daily" onDone={() => setTick((t) => t + 1)} />
          <RunButton label="گزارش هفتگی" path="/api/briefings/weekly" onDone={() => setTick((t) => t + 1)} />
        </div>
      </div>
      <Section title="گزارش‌ها" error={list.error} loading={list.loading}>
        {list.data && (
          <Table
            columns={[
              { key: "title", label: "عنوان", render: (r) => <button className="linkbtn" onClick={() => setOpenId(String(r.id))}>{String(r.title ?? `${r.kind} ${r.period}`)}</button> },
              { key: "kind", label: "نوع" },
              { key: "period", label: "دوره" },
            ]}
            rows={list.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
            emptyText="گزارشی ثبت نشده است."
          />
        )}
      </Section>
      {openId && (
        <Section title="متن گزارش" error={detail.error} loading={detail.loading}>
          {detail.data && (<div><h3>{detail.data.title ?? "—"}</h3><p style={{ whiteSpace: "pre-wrap" }}>{detail.data.body ?? "—"}</p><button onClick={() => setOpenId(null)}>بستن</button></div>)}
        </Section>
      )}
      <p className="hint">نسخهٔ داده/مدل/تنظیمات هر گزارش در جزئیات API ثبت است (قابلیت بازسازی تحلیل).</p>
    </div>
  );
}

export function OpsPage() {
  const [tick, setTick] = useState(0);
  const jobs = useApi<JobRun[]>("/api/jobs?limit=50", [tick]);
  const alerts = useApi<AlertItem[]>("/api/alerts?status=active&limit=50", [tick]);
  const monitoring = useApi<{ status: string; checks: { name: string; status: string; detail?: string }[] }>("/api/ops/monitoring", [tick]);
  const [ackMsg, setAckMsg] = useState<string | null>(null);
  const ack = async (id: string) => {
    try { await api.post(`/api/alerts/${id}/ack`); setAckMsg("هشدار تأیید شد."); setTick((t) => t + 1); }
    catch (e: unknown) { setAckMsg(e instanceof Error ? e.message : "خطا"); }
  };
  return (
    <div>
      <div className="page-head">
        <h1>کارهای خودکار و پردازش‌ها</h1>
        <div className="row">
          <RunButton label="ارزیابی هشدارها" path="/api/alerts/evaluate" onDone={() => setTick((t) => t + 1)} />
          <button onClick={() => setTick((t) => t + 1)}>به‌روزرسانی</button>
        </div>
      </div>
      {ackMsg && <p className="hint">{ackMsg}</p>}
      <Section title="پایش سلامت" error={monitoring.error} loading={monitoring.loading}>
        {monitoring.data && (
          <p>وضعیت کلی: <Badge tone={monitoring.data.status === "pass" ? "ok" : "bad"}>{monitoring.data.status}</Badge>
          {" "}{monitoring.data.checks.filter((c) => c.status !== "pass").map((c) => `${c.name} (${c.status})`).join(" · ")}</p>
        )}
      </Section>
      <Section title="اجراهای اخیر" error={jobs.error} loading={jobs.loading}>
        {jobs.data && (
          <Table
            columns={[
              { key: "job_name", label: "کار" },
              { key: "status", label: "وضعیت", render: (r) => <Badge tone={String(r.status) === "ok" ? "ok" : "bad"}>{String(r.status)}</Badge> },
              { key: "started_at", label: "شروع", render: (r) => faDateTime(String(r.started_at ?? "")) },
              { key: "message", label: "پیام", render: (r) => String(r.message ?? "—").slice(0, 100) },
            ]}
            rows={jobs.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
            emptyText="اجرایی ثبت نشده است."
          />
        )}
      </Section>
      <Section title="هشدارهای فعال" error={alerts.error} loading={alerts.loading}>
        {alerts.data && alerts.data.length > 0 ? (
          <Table
            columns={[
              { key: "metric", label: "متریک" },
              { key: "severity", label: "شدت" },
              { key: "message", label: "پیام", render: (r) => String(r.message ?? "—").slice(0, 120) },
              { key: "ack", label: "تأیید", render: (r) => <button className="linkbtn" onClick={() => ack(String(r.id))}>تأیید</button> },
            ]}
            rows={alerts.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
          />
        ) : (!alerts.loading && <Empty text="هشدار فعالی نیست." />)}
      </Section>
    </div>
  );
}

/** تنظیمات کامل در pages/settings.tsx (SettingsPanel) است؛ این فایل فقط بخش‌های دیگر را دارد. */
export function HelpPage() {
  return (
    <div>
      <div className="page-head"><h1>راهنمای سیستم</h1></div>
      <Section title="شروع سریع" error={null}>
        <ol className="list">
          <li>در «تنظیمات»، کلید API داخلی (همان <code dir="ltr">API_KEY</code> فایل <code dir="ltr">.env</code> سرور) را در حافظه ثبت کنید.</li>
          <li>در «منابع اطلاعاتی»، منبع RSS اضافه و «دریافت آزمایشی» بزنید.</li>
          <li>در «داشبورد»، دکمه‌های خط لوله (دریافت → طبقه‌بندی → رویداد → ادعا → شواهد) را به ترتیب اجرا کنید.</li>
          <li>در «هوش مصنوعی و مدل‌ها»، «آزمایش اتصال» بزنید؛ در حالت Mock خروجی نمونه است.</li>
        </ol>
      </Section>
      <Section title="برای اخبار واقعی و AI واقعی" error={null}>
        <ul className="list">
          <li>اخبار واقعی: منابع RSS واقعی فعال + اجرای <code dir="ltr">/api/ingest/all</code>. بدون کلید پولی کار می‌کند.</li>
          <li>AI واقعی: در <code dir="ltr">.env</code> سرور کلید ارائه‌دهنده (مثلاً <code dir="ltr">GEMINI_API_KEY</code>) + <code dir="ltr">MOCK_MODE=false</code>، سپس بیلد/ری‌استارت Backend.</li>
          <li>اهمیت خبر: ۱ بالاترین … ۱۰ کمترین (قرارداد Backend، همه‌جا یکسان).</li>
        </ul>
      </Section>
      <Section title="محدودیت‌های شناخته‌شده" error={null}>
        <ul className="list">
          <li>حذف منبع در API نیست → از غیرفعال‌سازی استفاده کنید.</li>
          <li>Ollama محلی آداپتور ندارد → «پیاده‌سازی نشده».</li>
          <li>تحویل هشدار (ایمیل/وب‌هوک) پیاده‌سازی نشده است.</li>
        </ul>
      </Section>
    </div>
  );
}

export function SearchPage({ param }: { param?: string }) {
  const initial = param ? decodeURIComponent(param) : "";
  const [q, setQ] = useState(initial);
  const [fired, setFired] = useState(initial);
  const articles = useApi<{ id: string; title: string | null }[]>(fired ? "/api/classify/articles?limit=200" : null, [fired]);
  const sources = useApi<{ id: string; name: string }[]>(fired ? "/api/sources?limit=200" : null, [fired]);
  const needle = fired.trim().toLowerCase();
  return (
    <div>
      <div className="page-head"><h1>جست‌وجوی سراسری</h1></div>
      <div className="filters">
        <input placeholder="عبارت جست‌وجو…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="جست‌وجو" />
        <button onClick={() => setFired(q)}>جست‌وجو</button>
      </div>
      {fired && (
        <div>
          <Section title="اخبار" error={articles.error} loading={articles.loading}>
            {articles.data && (
              <ul className="list">
                {articles.data.filter((a) => (a.title ?? "").toLowerCase().includes(needle)).slice(0, 20).map((a) => (
                  <li key={a.id}><button className="linkbtn" onClick={() => nav("news", `article-${a.id}`)}>{a.title ?? "—"}</button></li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="منابع" error={sources.error} loading={sources.loading}>
            {sources.data && (
              <ul className="list">
                {sources.data.filter((s) => s.name.toLowerCase().includes(needle)).slice(0, 20).map((s) => (
                  <li key={s.id}><button className="linkbtn" onClick={() => nav("sources")}>{s.name}</button></li>
                ))}
              </ul>
            )}
          </Section>
        </div>
      )}
    </div>
  );
}
