/** World state + macro economy. */
import { useState } from "react";
import { fa, faDateTime } from "../theme";
import type { WorldState } from "../types";
import { Bars, RunButton, Section, Table, useApi } from "../ui";

interface MacroObs {
  indicator: string;
  country: string | null;
  period: string | null;
  value: number | null;
  unit: string | null;
  source_name: string | null;
}

const SIGNALS: { key: keyof WorldState; label: string }[] = [
  { key: "growth_pressure", label: "رشد" },
  { key: "inflation_pressure", label: "تورم" },
  { key: "liquidity", label: "نقدینگی" },
  { key: "financial_stress", label: "تنش مالی" },
  { key: "geopolitical_risk", label: "ریسک ژئوپلیتیک" },
  { key: "energy_risk", label: "ریسک انرژی" },
  { key: "trade_risk", label: "ریسک تجارت" },
  { key: "political_risk", label: "ریسک سیاسی" },
  { key: "social_pressure", label: "فشار اجتماعی" },
];

export function WorldPage() {
  const [tick, setTick] = useState(0);
  const current = useApi<WorldState>("/api/world-state/current", [tick]);
  const history = useApi<WorldState[]>("/api/world-state/history?limit=30", [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>وضعیت جهان</h1>
        <RunButton label="ساخت تصویر جدید" path="/api/world-state/build" onDone={() => setTick((t) => t + 1)} />
      </div>
      <Section title="تصویر فعلی" error={current.error} loading={current.loading}>
        {current.data && (
          <div>
            <p>
              رژیم کلان: <strong>{current.data.macro_regime ?? "—"}</strong> · رژیم بازار:{" "}
              <strong>{current.data.market_regime ?? "—"}</strong> · اطمینان:{" "}
              {fa(current.data.confidence)}
            </p>
            <Bars
              items={SIGNALS.map((s) => ({
                label: s.label,
                value: Number(current.data![s.key] ?? 0),
              }))}
            />
            <p className="hint">هر مقدار بین ۰ تا ۱ است؛ منبع و روش هر مقدار در API ثبت است.</p>
          </div>
        )}
      </Section>
      <Section title="تاریخچه" error={history.error} loading={history.loading}>
        {history.data && (
          <Table
            columns={[
              { key: "captured_at", label: "زمان", render: (r) => faDateTime(String(r.captured_at ?? "")) },
              { key: "macro_regime", label: "کلان" },
              { key: "market_regime", label: "بازار" },
              { key: "confidence", label: "اطمینان", numeric: true },
            ]}
            rows={history.data as unknown as Record<string, unknown>[]}
            rowKey={(_, i) => String(i)}
            emptyText="تصویری ثبت نشده است."
          />
        )}
      </Section>
    </div>
  );
}

export function MacroPage() {
  const [tick, setTick] = useState(0);
  const indicators = useApi<Record<string, { code: string; unit: string }>>("/api/economic/indicators", [tick]);
  const latest = useApi<MacroObs[]>("/api/economic/latest?limit=100", [tick]);
  const overview = useApi<MacroObs[]>("/api/macro/overview?country=USA", [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>اقتصاد کلان</h1>
        <div className="row">
          <RunButton label="دریافت داده" path="/api/economic/fetch" onDone={() => setTick((t) => t + 1)} />
          <RunButton label="تحلیل" path="/api/macro/analyze" onDone={() => setTick((t) => t + 1)} />
        </div>
      </div>
      <Section title="شاخص‌های پشتیبانی‌شده" error={indicators.error} loading={indicators.loading}>
        {indicators.data && (
          <ul className="list">
            {Object.entries(indicators.data).map(([k, v]) => (
              <li key={k}>{k} — کد {v.code} ({v.unit})</li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="آخرین مقادیر" error={latest.error} loading={latest.loading}>
        {latest.data && (
          <Table
            columns={[
              { key: "indicator", label: "شاخص" },
              { key: "country", label: "کشور" },
              { key: "period", label: "دوره" },
              { key: "value", label: "مقدار", numeric: true },
              { key: "unit", label: "واحد" },
              { key: "source_name", label: "منبع" },
            ]}
            rows={latest.data as unknown as Record<string, unknown>[]}
            rowKey={(r, i) => `${r.indicator}-${r.country}-${r.period}-${i}`}
            emptyText="داده‌ای موجود نیست."
          />
        )}
      </Section>
      <Section title="نمای آمریکا" error={overview.error} loading={overview.loading}>
        {overview.data && (
          <Table
            columns={[
              { key: "indicator", label: "شاخص" },
              { key: "period", label: "دوره" },
              { key: "value", label: "مقدار", numeric: true },
            ]}
            rows={overview.data as unknown as Record<string, unknown>[]}
            rowKey={(r, i) => `${r.indicator}-${i}`}
            emptyText="داده‌ای موجود نیست."
          />
        )}
      </Section>
    </div>
  );
}
