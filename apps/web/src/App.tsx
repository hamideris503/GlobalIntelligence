import { useEffect, useState } from "react";
import { fetchJson, getApiKey, setApiKey } from "./api";

type Health = { status: string };
type DbHealth = { status: string; database: { ok: boolean; detail: string } };
type WorldState = {
  macro_regime: string | null;
  market_regime: string | null;
  confidence: number | null;
};
type Quote = { symbol: string; value: number | null; source_name: string | null };
type Decision = {
  asset: string;
  decision: string | null;
  score: number | null;
  rank: number | null;
};
type Risk = { category: string; score: number | null; level: string | null };
type Forecast = {
  target: string;
  model: string | null;
  expected_value: number | null;
};
type SelfEval = { score: number | null; grade: string | null };
type IranBrief = { counts: Record<string, number> };

function useData<T>(path: string, needsKey: boolean, keyVersion: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    fetchJson<T>(path)
      .then((r) => live && setData(r))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [path, keyVersion]);
  void needsKey;
  return { data, error };
}

function Section(props: {
  title: string;
  error: string | null;
  children: React.ReactNode;
}) {
  return (
    <section className="panel">
      <h2>{props.title}</h2>
      {props.error ? (
        <p className="hint">
          {props.error.includes("401")
            ? "کلید API لازم است (بالا وارد کنید)."
            : `خطا: ${props.error}`}
        </p>
      ) : (
        props.children
      )}
    </section>
  );
}

export default function App() {
  const [api, setApi] = useState<string>("…");
  const [db, setDb] = useState<string>("…");
  const [key, setKey] = useState<string>(getApiKey());
  const [keyVersion, setKeyVersion] = useState<number>(0);

  useEffect(() => {
    fetchJson<Health>("/health")
      .then((r) => setApi(r.status))
      .catch((e: Error) => setApi(`خطا: ${e.message}`));
    fetchJson<DbHealth>("/health/db")
      .then((r) => setDb(r.database.ok ? "متصل" : `قطع: ${r.database.detail}`))
      .catch((e: Error) => setDb(`خطا: ${e.message}`));
  }, []);

  const saveKey = () => {
    setApiKey(key);
    setKeyVersion((v) => v + 1);
  };

  const ws = useData<WorldState>("/api/world-state/current", true, keyVersion);
  const markets = useData<Quote[]>("/api/markets/latest", true, keyVersion);
  const decisions = useData<Decision[]>("/api/decisions?limit=5", true, keyVersion);
  const risks = useData<Risk[]>("/api/risk/overview", true, keyVersion);
  const forecasts = useData<Forecast[]>("/api/forecasts?limit=5", true, keyVersion);
  const selfeval = useData<SelfEval>("/api/self-eval/latest", true, keyVersion);
  const iran = useData<IranBrief>("/api/iran/brief?limit=5", true, keyVersion);

  return (
    <main className="app" dir="rtl">
      <header>
        <h1>GlobalIntelligence</h1>
        <p className="subtitle">داشبورد هوش اطلاعاتی، اقتصادی و پیش‌بینی</p>
        <div className="keybox">
          <input
            type="password"
            placeholder="کلید API (X-API-Key)"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          <button onClick={saveKey}>ذخیره</button>
        </div>
      </header>

      <section className="cards">
        <div className="card">
          <span className="card-label">Backend API</span>
          <span className={`badge ${api === "ok" ? "badge-ok" : "badge-warn"}`}>
            {api}
          </span>
        </div>
        <div className="card">
          <span className="card-label">Database</span>
          <span className={`badge ${db === "متصل" ? "badge-ok" : "badge-warn"}`}>
            {db}
          </span>
        </div>
        <div className="card">
          <span className="card-label">وضعیت جهان</span>
          <span className="badge badge-ok">
            {ws.data
              ? `${ws.data.macro_regime} / ${ws.data.market_regime}`
              : ws.error
                ? "—"
                : "…"}
          </span>
        </div>
        <div className="card">
          <span className="card-label">خودارزیابی</span>
          <span className="badge badge-ok">
            {selfeval.data
              ? `${selfeval.data.grade} (${selfeval.data.score})`
              : selfeval.error
                ? "—"
                : "…"}
          </span>
        </div>
      </section>

      <Section title="بازارها" error={markets.error}>
        <table>
          <thead>
            <tr>
              <th>نماد</th>
              <th>مقدار</th>
              <th>منبع</th>
            </tr>
          </thead>
          <tbody>
            {(markets.data ?? []).slice(0, 8).map((q) => (
              <tr key={q.symbol}>
                <td>{q.symbol}</td>
                <td>{q.value ?? "—"}</td>
                <td>{q.source_name ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="تصمیم‌ها" error={decisions.error}>
        <table>
          <thead>
            <tr>
              <th>دارایی</th>
              <th>تصمیم</th>
              <th>امتیاز</th>
            </tr>
          </thead>
          <tbody>
            {(decisions.data ?? []).map((d, i) => (
              <tr key={i}>
                <td>{d.asset}</td>
                <td>{d.decision ?? "—"}</td>
                <td>{d.score ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="ریسک‌ها" error={risks.error}>
        <table>
          <thead>
            <tr>
              <th>دسته</th>
              <th>امتیاز</th>
              <th>سطح</th>
            </tr>
          </thead>
          <tbody>
            {(risks.data ?? []).map((r) => (
              <tr key={r.category}>
                <td>{r.category}</td>
                <td>{r.score ?? "—"}</td>
                <td>{r.level ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="پیش‌بینی‌ها" error={forecasts.error}>
        <table>
          <thead>
            <tr>
              <th>هدف</th>
              <th>مدل</th>
              <th>مقدار</th>
            </tr>
          </thead>
          <tbody>
            {(forecasts.data ?? []).map((f, i) => (
              <tr key={i}>
                <td>{f.target}</td>
                <td>{f.model ?? "—"}</td>
                <td>{f.expected_value ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="ایران" error={iran.error}>
        <p>
          {iran.data
            ? Object.entries(iran.data.counts ?? {})
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ")
            : "…"}
        </p>
      </Section>
    </main>
  );
}
