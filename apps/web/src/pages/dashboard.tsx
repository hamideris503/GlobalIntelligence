/** داشبورد: همهٔ اعداد و نمودارها از APIهای واقعی؛ اگر API خطا بدهد خطا نمایش داده می‌شود، نه عدد ساختگی. */
import { useMemo, useState } from "react";
import { nav } from "../router";
import { fa, faDateTime, faInt } from "../theme";
import type { ArticleItem, Forecast, Quote, Risk, Source, WorldState } from "../types";
import { Badge, Bars, Donut, Empty, LineChart, RunButton, Section, StatCard, Spinner, useApi } from "../ui";

interface OpsStatus {
  database_ok: boolean;
  counts: Record<string, number>;
  last_jobs: { job_name: string; status: string; source: string | null }[];
  latest_self_eval: { score: number | null; grade: string | null };
  active_alerts: number;
  latest_world_state: { macro_regime: string | null; market_regime: string | null };
}
interface Briefing { id: string; kind: string; period: string; title: string | null }
interface Obs { value: number | null; observed_at: string | null }

const count = (n: number | undefined) => (n === undefined || n < 0 ? "نامشخص" : faInt(n));

export default function Dashboard() {
  const [tick, setTick] = useState(0);
  const refresh = () => setTick((t) => t + 1);
  const ops = useApi<OpsStatus>("/api/ops/status", [tick]);
  const sources = useApi<Source[]>("/api/sources?limit=200", [tick]);
  const articles = useApi<ArticleItem[]>("/api/classify/articles?limit=200", [tick]);
  const forecasts = useApi<Forecast[]>("/api/forecasts?limit=200", [tick]);
  const world = useApi<WorldState>("/api/world-state/current", [tick]);
  const risks = useApi<Risk[]>("/api/risk/overview", [tick]);
  const quotes = useApi<Quote[]>("/api/markets/latest", [tick]);
  const firstSym = quotes.data?.[0]?.symbol ?? null;
  const obs = useApi<Obs[]>(firstSym ? `/api/markets/observations?symbol=${encodeURIComponent(firstSym)}&limit=60` : null, [firstSym, tick]);
  const briefings = useApi<Briefing[]>("/api/briefings?limit=4", [tick]);

  const srcActive = sources.data?.filter((s) => s.active).length;
  const srcErr = sources.data?.filter((s) => s.active && s.last_error).length;
  const lastFetch = useMemo(() => {
    const t = (sources.data ?? []).map((s) => s.last_success).filter((x): x is string => !!x).sort().pop();
    return t ?? null;
  }, [sources.data]);

  const topics = useMemo(() => {
    const m = new Map<string, number>();
    for (const a of articles.data ?? []) for (const t of a.topics ?? []) m.set(t, (m.get(t) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([label, value]) => ({ label, value }));
  }, [articles.data]);

  const marketSeries = useMemo(() => (obs.data ?? []).filter((o) => o.value !== null).reverse(), [obs.data]);
  const topNews = useMemo(
    () => [...(articles.data ?? [])].filter((a) => a.title).sort((a, b) => (a.importance ?? 99) - (b.importance ?? 99)).slice(0, 5),
    [articles.data],
  );
  const riskItems = (risks.data ?? []).filter((r) => r.score !== null).map((r) => ({ label: r.category, value: Number(r.score) }));

  return (
    <div>
      <div className="hero">
        <h1>مرکز هوش اقتصادی و ژئوپلیتیک</h1>
        <p>تصویر یک‌نگاه از اخبار، رویدادها، بازار، ریسک و پیش‌بینی‌ها. همهٔ اعداد از Backend واقعی می‌آیند و اگر چیزی در دسترس نباشد «نامشخص» نمایش داده می‌شود.</p>
        <div className="hero-chips">
          <span className="chip">رژیم کلان: <b>{world.data?.macro_regime ?? "—"}</b></span>
          <span className="chip">رژیم بازار: <b>{world.data?.market_regime ?? "—"}</b></span>
          <span className="chip">آخرین دریافت: <b>{faDateTime(lastFetch)}</b></span>
        </div>
        <div className="hero-actions">
          <button onClick={() => nav("news")}>مشاهدهٔ اخبار</button>
          <button className="secondary" onClick={() => nav("keys")}>کلیدها و سرویس‌ها</button>
          <button className="secondary" onClick={refresh}>به‌روزرسانی</button>
        </div>
      </div>

      {ops.error ? (
        <Section title="وضعیت سامانه" error={ops.error}><></></Section>
      ) : (
        <div className="cards six">
          <StatCard icon="news" label="اخبار دریافت‌شده" value={ops.loading ? "…" : count(ops.data?.counts.articles)} unit="خبر" foot={`سند خام: ${count(ops.data?.counts.documents)}`} />
          <StatCard icon="pulse" label="رویدادهای شناسایی‌شده" value={ops.loading ? "…" : count(ops.data?.counts.events)} unit="رویداد" />
          <StatCard icon="sources" label="منابع فعال" value={sources.loading ? "…" : sources.error ? "نامشخص" : faInt(srcActive)} unit={sources.data ? `از ${faInt(sources.data.length)}` : undefined} foot={`آخرین دریافت: ${faDateTime(lastFetch)}`} />
          <StatCard icon="alert" tone={srcErr ? "bad" : "ok"} label="منابع دارای خطا" value={sources.loading ? "…" : sources.error ? "نامشخص" : faInt(srcErr)} unit="منبع" />
          <StatCard icon="forecast" label="پیش‌بینی‌های ثبت‌شده" value={forecasts.loading ? "…" : forecasts.error ? "نامشخص" : faInt(forecasts.data?.length)} foot={forecasts.data && forecasts.data.length >= 200 ? "حداقل ۲۰۰ (سقف دریافت)" : undefined} />
          <StatCard icon="db" tone={ops.data?.database_ok ? "ok" : "bad"} label="دیتابیس" value={ops.loading ? "…" : ops.data?.database_ok ? "متصل" : "قطع"} foot={`هشدار فعال: ${count(ops.data?.active_alerts)}`} />
        </div>
      )}

      <div className="grid-3">
        <Section title={`روند بازار${firstSym ? ` — ${firstSym}` : ""}`} error={quotes.error ?? obs.error} loading={quotes.loading || obs.loading}>
          {marketSeries.length >= 2 ? (
            <LineChart labels={marketSeries.map((o) => faDateTime(o.observed_at, false))} series={[{ name: firstSym ?? "", values: marketSeries.map((o) => Number(o.value)) }]} />
          ) : (
            <Empty text="دادهٔ بازار کافی نیست. در صفحهٔ «بازارهای مالی» قیمت‌ها را دریافت کنید." />
          )}
        </Section>
        <Section title="توزیع موضوعی خبرها" error={articles.error} loading={articles.loading}>
          {topics.length ? <Donut items={topics} /> : <Empty text="خبر طبقه‌بندی‌شده‌ای وجود ندارد." />}
        </Section>
      </div>

      <div className="grid-2">
        <Section title="هشدارهای ریسک" error={risks.error} loading={risks.loading} actions={<button className="ghost" onClick={() => nav("scenarios")}>جزئیات</button>}>
          {riskItems.length ? <Bars items={riskItems} /> : <Empty text="ارزیابی ریسکی ثبت نشده است." />}
        </Section>
        <Section title="مهم‌ترین اخبار" error={articles.error} loading={articles.loading} actions={<button className="ghost" onClick={() => nav("news")}>همه</button>}>
          {topNews.length ? (
            <ul className="feed">
              {topNews.map((a) => (
                <li key={a.id}>
                  <button className="linkbtn" onClick={() => nav("news", `article-${a.id}`)}>{a.title}</button>
                  <span className="t">اهمیت {faInt(a.importance)}</span>
                </li>
              ))}
            </ul>
          ) : <Empty text="خبری ثبت نشده است." />}
        </Section>
      </div>

      <div className="grid-2">
        <Section title="وضعیت جهان و ایران" error={world.error} loading={world.loading} actions={<button className="ghost" onClick={() => nav("world")}>جزئیات</button>}>
          {world.data ? (
            <dl className="kv">
              <dt>رژیم کلان</dt><dd>{world.data.macro_regime ?? "—"}</dd>
              <dt>رژیم بازار</dt><dd>{world.data.market_regime ?? "—"}</dd>
              <dt>اطمینان</dt><dd>{fa(world.data.confidence)}</dd>
              <dt>ریسک ژئوپلیتیک</dt><dd>{fa(world.data.geopolitical_risk)}</dd>
            </dl>
          ) : <Empty text="تصویر جهان هنوز ساخته نشده است." />}
        </Section>
        <Section title="آخرین فعالیت‌های سیستم" error={ops.error} loading={ops.loading} actions={<button className="ghost" onClick={() => nav("ops")}>همه</button>}>
          {ops.data && ops.data.last_jobs.length ? (
            <ul className="feed">
              {ops.data.last_jobs.map((j, i) => (
                <li key={i}><span>{j.job_name}</span><Badge tone={j.status === "ok" ? "ok" : "bad"}>{j.status}</Badge></li>
              ))}
            </ul>
          ) : <Empty text="کاری ثبت نشده است." />}
        </Section>
      </div>

      <Section title="اقدامات سریع" error={null}>
        <p className="hint">این دکمه‌ها مستقیم به عملیات واقعی Backend وصل‌اند و نتیجهٔ همان پاسخ را نشان می‌دهند. زنجیرهٔ سراسری فقط از n8n زمان‌بندی می‌شود.</p>
        <div className="row" style={{ marginBottom: 12 }}>
          <button onClick={() => nav("sources")}>افزودن منبع خبری</button>
          <button className="secondary" onClick={() => nav("ai")}>تنظیم و آزمایش هوش مصنوعی</button>
          <button className="secondary" onClick={() => nav("news")}>مشاهدهٔ اخبار</button>
        </div>
        <div className="rungrid">
          <RunButton label="دریافت اخبار" path="/api/ingest/all?limit=20" onDone={refresh} />
          <RunButton label="حذف تکراری‌ها" path="/api/dedup/run?limit=200" onDone={refresh} />
          <RunButton label="طبقه‌بندی" path="/api/classify/run?limit=50" onDone={refresh} />
          <RunButton label="استخراج رویداد" path="/api/events/extract?limit=50" onDone={refresh} />
          <RunButton label="استخراج ادعا" path="/api/claims/extract?limit=50" onDone={refresh} />
          <RunButton label="شواهد" path="/api/claims/evidence?limit=50" onDone={refresh} />
          <RunButton label="بازارها" path="/api/markets/fetch" onDone={refresh} />
          <RunButton label="وضعیت جهان" path="/api/world-state/build" onDone={refresh} />
        </div>
      </Section>

      <Section title="آخرین گزارش‌ها" error={briefings.error} loading={briefings.loading}>
        {briefings.loading ? <Spinner /> : briefings.data && briefings.data.length ? (
          <ul className="feed">
            {briefings.data.map((b) => (
              <li key={b.id}><button className="linkbtn" onClick={() => nav("history")}>{b.title ?? `${b.kind} ${b.period}`}</button></li>
            ))}
          </ul>
        ) : <Empty text="گزارشی ثبت نشده است." />}
      </Section>
    </div>
  );
}
