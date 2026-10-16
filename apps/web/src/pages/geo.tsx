/** Geopolitics + society + Iran. */
import { useState } from "react";
import { RunButton, Section, Table, useApi } from "../ui";

interface Tension {
  actor: string;
  tension: number | null;
  period?: string | null;
}
interface Mood {
  scope_type: string;
  scope: string;
  avg_sentiment: number | null;
  unrest_share: number | null;
}
interface IranBrief {
  counts: Record<string, number>;
  events: { id: string; event_type: string | null; action: string | null }[];
  macro: { indicator: string; period: string | null; value: number | null }[];
  world_state: { macro_regime: string | null; market_regime: string | null };
}

export function GeoPage() {
  const [tick, setTick] = useState(0);
  const tensions = useApi<Tension[]>("/api/geopolitics/tensions?limit=50", [tick]);
  const moods = useApi<Mood[]>("/api/society/mood", [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>ژئوپلیتیک و سیاست</h1>
        <div className="row">
          <RunButton label="تحلیل تنش‌ها" path="/api/geopolitics/analyze" onDone={() => setTick((t) => t + 1)} />
          <RunButton label="تحلیل اجتماعی" path="/api/society/analyze" onDone={() => setTick((t) => t + 1)} />
        </div>
      </div>
      <Section title="تنش بازیگران" error={tensions.error} loading={tensions.loading}>
        {tensions.data && (
          <Table
            columns={[
              { key: "actor", label: "بازیگر" },
              { key: "tension", label: "تنش", numeric: true },
            ]}
            rows={tensions.data as unknown as Record<string, unknown>[]}
            rowKey={(r, i) => `${r.actor}-${i}`}
            emptyText="ارزیابی تنشی ثبت نشده است."
          />
        )}
      </Section>
      <Section title="حال‌وهوای اجتماعی" error={moods.error} loading={moods.loading}>
        {moods.data && (
          <Table
            columns={[
              { key: "scope", label: "قلمرو" },
              { key: "avg_sentiment", label: "میانگین احساس", numeric: true },
              { key: "unrest_share", label: "سهم ناآرامی", numeric: true },
            ]}
            rows={moods.data as unknown as Record<string, unknown>[]}
            rowKey={(r, i) => `${r.scope_type}-${r.scope}-${i}`}
            emptyText="داده‌ای موجود نیست."
          />
        )}
      </Section>
      <p className="hint">
        محدودیت داده: با دادهٔ نمونه، تنش‌ها و احساسات واقعی نیستند؛ سوگیری طبقه‌بندی منتقل می‌شود.
      </p>
    </div>
  );
}

export function IranPage() {
  const [tick, setTick] = useState(0);
  const brief = useApi<IranBrief>("/api/iran/brief?limit=20", [tick]);
  const transmission = useApi<{ channel: string; impact: number | null }[]>("/api/iran/transmission", [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>ایران</h1>
        <RunButton label="تحلیل انتقال" path="/api/iran/transmission/analyze" onDone={() => setTick((t) => t + 1)} />
      </div>
      <Section title="خلاصه" error={brief.error} loading={brief.loading}>
        {brief.data && (
          <div>
            <p>
              {Object.entries(brief.data.counts ?? {})
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ") || "داده‌ای موجود نیست."}
            </p>
            <p className="hint">
              رژیم جهان: {brief.data.world_state.macro_regime ?? "—"} /{" "}
              {brief.data.world_state.market_regime ?? "—"}
            </p>
            {brief.data.macro.length > 0 && (
              <Table
                columns={[
                  { key: "indicator", label: "شاخص" },
                  { key: "period", label: "دوره" },
                  { key: "value", label: "مقدار", numeric: true },
                ]}
                rows={brief.data.macro as unknown as Record<string, unknown>[]}
                rowKey={(r, i) => `${r.indicator}-${i}`}
              />
            )}
          </div>
        )}
      </Section>
      <Section title="کانال‌های انتقال" error={transmission.error} loading={transmission.loading}>
        {transmission.data && (
          <Table
            columns={[
              { key: "channel", label: "کانال" },
              { key: "impact", label: "اثر", numeric: true },
            ]}
            rows={transmission.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.channel)}
            emptyText="تحلیل انتقالی ثبت نشده است."
          />
        )}
      </Section>
      <p className="hint">
        اگر داده‌ای نیست، اتصال بانک جهانی/بازار یا رویداد مرتبط کم است؛ صفحه تحلیل قطعی تولید نمی‌کند.
      </p>
    </div>
  );
}
