/** Markets: symbols + latest quotes + observations history + fetch. */
import { useState } from "react";
import { faDateTime } from "../theme";
import { RunButton, Section, Sparkline, Table, useApi } from "../ui";

interface SymbolInfo { symbol: string; name?: string | null }
interface Quote { symbol: string; value: number | null; source_name: string | null; observed_at?: string | null }
interface Obs { symbol: string; value: number | null; observed_at: string | null; source_name: string | null }

export default function Markets() {
  const [tick, setTick] = useState(0);
  const [symbol, setSymbol] = useState("");
  const symbols = useApi<SymbolInfo[] | string[]>("/api/markets/symbols", [tick]);
  const latest = useApi<Quote[]>("/api/markets/latest", [tick]);
  const obs = useApi<Obs[]>(symbol ? `/api/markets/observations?symbol=${encodeURIComponent(symbol)}&limit=60` : null, [symbol, tick]);

  const symList: string[] = (symbols.data ?? []).map((s) => typeof s === "string" ? s : s.symbol);
  const values = (obs.data ?? []).map((o) => o.value).filter((v): v is number => v !== null).reverse();

  return (
    <div>
      <div className="page-head">
        <h1>بازارهای مالی</h1>
        <RunButton label="دریافت قیمت‌ها" path="/api/markets/fetch" onDone={() => setTick((t) => t + 1)} />
      </div>
      <Section title="آخرین قیمت‌ها" error={latest.error} loading={latest.loading}>
        {latest.data && (
          <Table
            columns={[
              { key: "symbol", label: "نماد" },
              { key: "value", label: "مقدار", numeric: true },
              { key: "source_name", label: "منبع" },
              { key: "observed_at", label: "زمان مشاهده", render: (r) => faDateTime(String(r.observed_at ?? "")) },
            ]}
            rows={latest.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.symbol)}
            emptyText="قیمتی ثبت نشده است."
          />
        )}
      </Section>
      <Section title="روند نماد" error={symbols.error ?? obs.error} loading={symbols.loading}>
        <div className="filters">
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)} aria-label="انتخاب نماد">
            <option value="">— نماد را انتخاب کنید —</option>
            {symList.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        {symbol && obs.loading && <p className="hint">در حال بارگذاری…</p>}
        {symbol && obs.data && obs.data.length > 0 && (
          <div>
            <Sparkline values={values} width={320} height={80} />
            <Table
              columns={[
                { key: "observed_at", label: "زمان", render: (r) => faDateTime(String(r.observed_at ?? "")) },
                { key: "value", label: "مقدار", numeric: true },
                { key: "source_name", label: "منبع" },
              ]}
              rows={obs.data as unknown as Record<string, unknown>[]}
              rowKey={(_, i) => String(i)}
            />
          </div>
        )}
        {symbol && obs.data && obs.data.length === 0 && !obs.loading && (
          <p className="hint">مشاهده‌ای برای این نماد نیست.</p>
        )}
      </Section>
      <p className="hint">قیمت‌ها واقعی‌اند (بدون لحظه‌ای‌نمایی جعلی)؛ تاریخ آخرین مشاهده همیشه نمایش داده می‌شود.</p>
    </div>
  );
}
