/** Forecasts + scenarios + risk + decisions (all real endpoints). */
import { useMemo, useState } from "react";
import { api } from "../api";
import { fa, faDateTime } from "../theme";
import { Badge, Empty, RunButton, Section, Table, useApi } from "../ui";

interface Forecast { id?: string; target: string; model: string | null; expected_value: number | null; confidence: number | null; horizon?: string | null; status?: string | null; scenario?: string | null }
interface Scenario { id?: string; name: string; probability: number | null; description?: string | null }
interface Decision { asset: string; decision: string | null; score: number | null; confidence: number | null; rank: number | null; main_drivers?: string | null; main_risks?: string | null }
interface Risk { category: string; score: number | null; level: string | null }

export function ForecastPage() {
  const [tick, setTick] = useState(0);
  const list = useApi<Forecast[]>("/api/forecasts?limit=100", [tick]);
  const asOf = useMemo(() => encodeURIComponent(new Date().toISOString()), [tick]);
  const active = useApi<Forecast[]>(`/api/forecasts/ledger/active?as_of=${asOf}&limit=50`, [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>پیش‌بینی‌ها</h1>
        <RunButton label="اجرای پیش‌بینی" path="/api/forecasts/run" onDone={() => setTick((t) => t + 1)} />
      </div>
      <Section title="فعال" error={active.error} loading={active.loading}>
        {active.data && active.data.length > 0 ? (
          <Table
            columns={[
              { key: "target", label: "هدف" },
              { key: "model", label: "مدل" },
              { key: "expected_value", label: "مقدار", numeric: true },
              { key: "confidence", label: "اطمینان", numeric: true, render: (r) => fa(r.confidence as number | null) },
            ]}
            rows={active.data as unknown as Record<string, unknown>[]}
            rowKey={(_, i) => `a-${i}`}
          />
        ) : (!active.loading && <Empty text="پیش‌بینی فعالی نیست." />)}
      </Section>
      <Section title="همه" error={list.error} loading={list.loading}>
        {list.data && (
          <Table
            columns={[
              { key: "target", label: "هدف" },
              { key: "model", label: "مدل" },
              { key: "expected_value", label: "مقدار", numeric: true },
              { key: "status", label: "وضعیت" },
            ]}
            rows={list.data as unknown as Record<string, unknown>[]}
            rowKey={(_, i) => String(i)}
            emptyText="پیش‌بینی ثبت نشده است."
          />
        )}
      </Section>
    </div>
  );
}

export function ScenariosPage() {
  const [tick, setTick] = useState(0);
  const list = useApi<Scenario[]>("/api/scenarios?limit=50", [tick]);
  const risks = useApi<Risk[]>("/api/risk/overview", [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>سناریوها و ریسک</h1>
        <div className="row">
          <RunButton label="ساخت سناریو" path="/api/scenarios/run" onDone={() => setTick((t) => t + 1)} />
          <RunButton label="تحلیل ریسک" path="/api/risk/analyze" onDone={() => setTick((t) => t + 1)} />
        </div>
      </div>
      <Section title="سناریوها" error={list.error} loading={list.loading}>
        {list.data && (
          <Table
            columns={[
              { key: "name", label: "نام" },
              { key: "probability", label: "احتمال", numeric: true, render: (r) => fa(r.probability as number | null) },
              { key: "description", label: "شرح", render: (r) => String(r.description ?? "—").slice(0, 150) },
            ]}
            rows={list.data as unknown as Record<string, unknown>[]}
            rowKey={(_, i) => String(i)}
            emptyText="سناریویی ثبت نشده است."
          />
        )}
      </Section>
      <Section title="نمای ریسک" error={risks.error} loading={risks.loading}>
        {risks.data && (
          <Table
            columns={[
              { key: "category", label: "دسته" },
              { key: "score", label: "امتیاز", numeric: true },
              { key: "level", label: "سطح" },
            ]}
            rows={risks.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.category)}
            emptyText="ارزیابی ریسکی نیست."
          />
        )}
      </Section>
      <p className="hint">احتمال‌ها فقط وقتی نمایش داده می‌شوند که موتور واقعاً محاسبه کرده باشد.</p>
    </div>
  );
}

export function DecisionsPage() {
  const [tick, setTick] = useState(0);
  const list = useApi<Decision[]>("/api/decisions?limit=50", [tick]);
  const [msg, setMsg] = useState<string | null>(null);
  const decideClass = (d: string | null) => {
    if (!d) return "info" as const;
    const t = d.toLowerCase();
    if (t.includes("avoid") || t.includes("sell")) return "bad" as const;
    if (t.includes("opportunity") || t.includes("buy")) return "ok" as const;
    return "info" as const;
  };
  const acknowledge = async (idx: number) => {
    const d = list.data?.[idx];
    if (!d) return;
    try {
      await api.post("/api/audit/log", { action: "decision_ack", detail: d.asset, meta: { decision: d.decision } });
      setMsg(`تصمیم «${d.asset}» در گزارش حسابرسی ثبت شد.`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "خطا");
    }
  };
  return (
    <div>
      <div className="page-head">
        <h1>تصمیم‌ها و پیشنهادها</h1>
        <RunButton label="اجرای موتور تصمیم" path="/api/decisions/run" onDone={() => setTick((t) => t + 1)} />
      </div>
      <p className="hint">سامانه تصمیم‌یار است، نه تضمین سود. پیش‌بینی احتمالی با محاسبهٔ قطعی متفاوت است.</p>
      {msg && <p className="hint">{msg}</p>}
      <Section title="پیشنهادها" error={list.error} loading={list.loading}>
        {list.data && (
          <Table
            columns={[
              { key: "asset", label: "دارایی" },
              { key: "decision", label: "تصمیم", render: (r) => <Badge tone={decideClass(r.decision as string | null)}>{String(r.decision ?? "—")}</Badge> },
              { key: "score", label: "امتیاز", numeric: true },
              { key: "confidence", label: "اطمینان", numeric: true, render: (r) => fa(r.confidence as number | null) },
              { key: "rank", label: "رتبه", numeric: true },
              { key: "ack", label: "تأیید", render: () => <span /> },
            ]}
            rows={list.data as unknown as Record<string, unknown>[]}
            rowKey={(_, i) => String(i)}
            emptyText="پیشنهادی ثبت نشده است."
          />
        )}
      </Section>
      {list.data && list.data.length > 0 && (
        <Section title="جزئیات" error={null}>
          <ul className="list">
            {list.data.map((d, i) => (
              <li key={i}>
                <strong>{d.asset}</strong> — محرک: {d.main_drivers ?? "—"} · ریسک: {d.main_risks ?? "—"}{" "}
                <button className="linkbtn" onClick={() => acknowledge(i)}>ثبت تأیید در حسابرسی</button>
                <br /><span className="hint">ایجاد: {faDateTime(null)} — جزئیات کامل در API (cond/value per decision endpoint).</span>
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}
