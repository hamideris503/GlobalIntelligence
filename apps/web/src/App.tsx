import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Health = { status: string };
type DbHealth = { status: string; database: { ok: boolean; detail: string } };

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export default function App() {
  const [api, setApi] = useState<string>("…");
  const [db, setDb] = useState<string>("…");

  useEffect(() => {
    fetchJson<Health>("/health")
      .then((r) => setApi(r.status))
      .catch((e) => setApi(`خطا: ${e.message}`));

    fetchJson<DbHealth>("/health/db")
      .then((r) => setDb(r.database.ok ? "متصل" : `قطع: ${r.database.detail}`))
      .catch((e) => setDb(`خطا: ${e.message}`));
  }, []);

  return (
    <main className="app">
      <header>
        <h1>GlobalIntelligence</h1>
        <p className="subtitle">
          پلتفرم هوش اطلاعاتی، اقتصادی و پیش‌بینی
        </p>
      </header>

      <section className="cards">
        <div className="card">
          <span className="card-label">Backend API</span>
          <span
            className={`badge ${api === "ok" ? "badge-ok" : "badge-warn"}`}
          >
            {api}
          </span>
        </div>
        <div className="card">
          <span className="card-label">Database</span>
          <span className={`badge ${db === "متصل" ? "badge-ok" : "badge-warn"}`}>
            {db}
          </span>
        </div>
      </section>
    </main>
  );
}
