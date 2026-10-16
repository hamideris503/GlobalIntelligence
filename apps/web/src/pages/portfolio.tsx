/** Portfolio + evaluation (real endpoints; portfolio CRUD wired). */
import { useState } from "react";
import { api } from "../api";
import { fa } from "../theme";
import { Field, Modal, RunButton, Section, Table, useApi } from "../ui";

interface Portfolio { id: string; name: string; currency?: string | null }
interface Snapshot { id?: string; total_value: number | null; created_at?: string | null }

export function PortfolioPage() {
  const [tick, setTick] = useState(0);
  const [sel, setSel] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [error, setError] = useState<string | null>(null);
  const list = useApi<Portfolio[]>("/api/portfolios", [tick]);
  const snaps = useApi<Snapshot[]>(sel ? `/api/portfolios/${sel}/snapshots` : null, [sel, tick]);

  const create = async () => {
    if (!name.trim()) { setError("نام سبد لازم است."); return; }
    setError(null);
    try {
      const p = await api.post<Portfolio>("/api/portfolios", { name: name.trim(), currency });
      setShowCreate(false); setName("");
      setSel(p.id); setTick((t) => t + 1);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "خطا"); }
  };

  return (
    <div>
      <div className="page-head">
        <h1>سبد دارایی</h1>
        <button onClick={() => setShowCreate(true)}>سبد جدید</button>
      </div>
      <Section title="سبدها" error={list.error} loading={list.loading}>
        {list.data && list.data.length > 0 ? (
          <div className="filters">
            <select value={sel} onChange={(e) => setSel(e.target.value)} aria-label="انتخاب سبد">
              <option value="">— انتخاب —</option>
              {list.data.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.currency ?? "—"})</option>)}
            </select>
          </div>
        ) : (!list.loading && <p className="hint">سبدی ثبت نشده است. «سبد جدید» را بزنید.</p>)}
      </Section>
      {sel && (
        <Section title="اسنپ‌شات‌ها" error={snaps.error} loading={snaps.loading}>
          <RunButton label="ثبت اسنپ‌شات" path={`/api/portfolios/${sel}/snapshot`} onDone={() => setTick((t) => t + 1)} />
          {snaps.data && (
            <Table
              columns={[
                { key: "created_at", label: "زمان" },
                { key: "total_value", label: "ارزش کل", numeric: true, render: (r) => fa(r.total_value as number | null) },
              ]}
              rows={snaps.data as unknown as Record<string, unknown>[]}
              rowKey={(_, i) => String(i)}
              emptyText="اسنپ‌شاتی نیست."
            />
          )}
        </Section>
      )}
      <p className="hint">ثبت معامله/ارزش بازار فقط اگر Backend پشتیبانی کند؛ در غیر این صورت همین‌جا «پیاده‌سازی نشده» می‌ماند.</p>
      {showCreate && (
        <Modal title="سبد جدید" onClose={() => setShowCreate(false)}>
          <Field label="نام سبد"><input value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="واحد پول"><input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="USD" /></Field>
          {error && <p className="err-text">{error}</p>}
          <div className="row"><button onClick={create}>ایجاد</button><button onClick={() => setShowCreate(false)}>لغو</button></div>
        </Modal>
      )}
    </div>
  );
}

export function EvaluationPage() {
  const [tick, setTick] = useState(0);
  const summary = useApi<Record<string, unknown>>("/api/evaluation/summary", [tick]);
  const scores = useApi<{ model: string; brier: number | null; log_loss: number | null; mae: number | null; rmse: number | null }[]>("/api/evaluation/scores?limit=50", [tick]);
  const selfeval = useApi<{ score: number | null; grade: string | null }[]>("/api/self-eval/history?limit=10", [tick]);
  const scorecard = useApi<{ verdict: string; message: string; n_resolved: number; sufficient: boolean; cards: { model: string; n: number; mean_brier: number | null; hit_rate: number | null }[] }>("/api/debate/scorecard", [tick]);
  return (
    <div>
      <div className="page-head">
        <h1>ارزیابی عملکرد</h1>
        <div className="row">
          <RunButton label="اجرای ارزیابی" path="/api/evaluation/run" onDone={() => setTick((t) => t + 1)} />
          <RunButton label="خودارزیابی" path="/api/self-eval/run" onDone={() => setTick((t) => t + 1)} />
        </div>
      </div>
      <Section title="کارنامه debate" error={scorecard.error} loading={scorecard.loading}>
        {scorecard.data && (
          <div>
            <p>
              {scorecard.data.sufficient ? null : <strong>نمونه ناکافی؛ نتیجه‌گیری ممنوع. </strong>}
              {scorecard.data.message} (resolveشده: {scorecard.data.n_resolved})
            </p>
            {scorecard.data.cards.length > 0 && (
              <Table
                columns={[
                  { key: "model", label: "مدل" },
                  { key: "n", label: "نمونه", numeric: true },
                  { key: "mean_brier", label: "Brier", numeric: true, render: (r) => String(r.mean_brier ?? "—") },
                  { key: "hit_rate", label: "Hit rate", numeric: true, render: (r) => String(r.hit_rate ?? "—") },
                ]}
                rows={scorecard.data.cards as unknown as Record<string, unknown>[]}
                rowKey={(r) => String(r.model)}
                emptyText="کارنامه‌ای ثبت نشده است."
              />
            )}
          </div>
        )}
      </Section>
      <Section title="خلاصه" error={summary.error} loading={summary.loading}>
        {summary.data && (
          <p>{Object.entries(summary.data).filter(([, v]) => typeof v === "number" || typeof v === "string").map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"}</p>
        )}
      </Section>
      <Section title="امتیاز مدل‌ها (Brier / LogLoss / MAE / RMSE)" error={scores.error} loading={scores.loading}>
        {scores.data && (
          <Table
            columns={[
              { key: "model", label: "مدل" },
              { key: "brier", label: "Brier", numeric: true },
              { key: "log_loss", label: "LogLoss", numeric: true },
              { key: "mae", label: "MAE", numeric: true },
              { key: "rmse", label: "RMSE", numeric: true },
            ]}
            rows={scores.data as unknown as Record<string, unknown>[]}
            rowKey={(r, i) => `${r.model}-${i}`}
            emptyText="ارزیابی ثبت نشده است."
          />
        )}
      </Section>
      <Section title="تاریخچهٔ خودارزیابی" error={selfeval.error} loading={selfeval.loading}>
        {selfeval.data && (
          <ul className="list">
            {selfeval.data.map((s, i) => <li key={i}>نمره {fa(s.score)} — گرید {s.grade ?? "—"}</li>)}
          </ul>
        )}
      </Section>
      <p className="hint">معیارها از API محاسبه می‌شوند؛ هیچ عددی با متن مدل زبانی جایگزین نشده است.</p>
    </div>
  );
}
