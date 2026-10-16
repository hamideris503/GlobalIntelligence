/** Debate page: run list, per-round transcript, agent probs, consensus, proposal. */
import { useState } from "react";
import { api } from "../api";
import { nav } from "../router";
import { faDateTime } from "../theme";
import { Badge, Empty, PageHeader, Section, Table, useApi, useToast } from "../ui";

interface DebateMsg {
  id: string;
  round_no: number;
  agent: string;
  provider: string | null;
  model: string | null;
  probability_up: number | null;
  confidence: number | null;
  quality_score: number | null;
  total_tokens: number | null;
  error: string | null;
}

interface DebateRun {
  id: string;
  target: string;
  target_date: string | null;
  status: string;
  reference_price: number | null;
  consensus_probability: number | null;
  disagreement: number | null;
  messages: DebateMsg[];
}

function RunDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const run = useApi<DebateRun>(`/api/debate/runs/${id}`, []);
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const propose = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ decision: string; experimental: boolean }>(
        `/api/decisions/from-debate?run_id=${id}`,
      );
      toast(
        r.experimental
          ? `پیشنهاد آزمایشی ثبت شد (${r.decision}) — توصیه نیست.`
          : `پیشنهاد ثبت شد (${r.decision}).`,
        "ok",
      );
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "خطا", "bad");
    } finally {
      setBusy(false);
    }
  };

  const rounds = (run.data?.messages ?? []).reduce<Record<number, DebateMsg[]>>((acc, m) => {
    (acc[m.round_no] = acc[m.round_no] || []).push(m);
    return acc;
  }, {});

  return (
    <div>
      <button className="secondary" onClick={onBack}>→ بازگشت به فهرست</button>
      <Section title="جزئیات debate" error={run.error} loading={run.loading}>
        {run.data && (
          <div>
            <dl className="kv">
              <dt>هدف</dt><dd>{run.data.target}</dd>
              <dt>سررسید</dt><dd>{faDateTime(run.data.target_date)}</dd>
              <dt>وضعیت</dt><dd><Badge tone={run.data.status === "done" ? "ok" : "warn"}>{run.data.status}</Badge></dd>
              <dt>قیمت مرجع</dt><dd>{run.data.reference_price ?? "—"}</dd>
              <dt>اجماع P(up)</dt><dd>{run.data.consensus_probability ?? "—"}</dd>
              <dt>اختلاف</dt><dd>{run.data.disagreement ?? "—"}</dd>
            </dl>
            <div className="row" style={{ marginTop: 12 }}>
              <button onClick={propose} disabled={busy || run.data.status !== "done"}>
                {busy ? "…" : "ساخت پیشنهاد تصمیم‌یار"}
              </button>
              <button className="secondary" onClick={() => nav("decisions")}>مشاهدهٔ تصمیم‌ها</button>
            </div>
            <p className="hint">هشدار: خروجی تصمیم‌یار است، توصیه‌ی مالی نیست.</p>
            {Object.entries(rounds).map(([r, msgs]) => (
              <div key={r}>
                <h3>دور {r}</h3>
                <Table
                  columns={[
                    { key: "agent", label: "عامل" },
                    { key: "model", label: "مدل", render: (x) => `${x.provider ?? "—"}/${x.model ?? "—"}` },
                    { key: "probability_up", label: "P(up)", numeric: true, render: (x) => String(x.probability_up ?? "—") },
                    { key: "confidence", label: "اطمینان", numeric: true, render: (x) => String(x.confidence ?? "—") },
                    { key: "quality_score", label: "کیفیت", numeric: true, render: (x) => String(x.quality_score ?? "—") },
                    { key: "error", label: "خطا", render: (x) => String(x.error ?? "—").slice(0, 80) },
                  ]}
                  rows={msgs as unknown as Record<string, unknown>[]}
                  rowKey={(x) => String(x.id)}
                />
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

export default function Debate({ param }: { param?: string }) {
  const [tick, setTick] = useState(0);
  const runs = useApi<DebateRun[]>("/api/debate/runs?limit=50", [tick]);
  const [openId, setOpenId] = useState<string | null>(param ?? null);

  if (openId) return <RunDetail id={openId} onBack={() => { setOpenId(null); setTick((t) => t + 1); }} />;

  return (
    <div>
      <PageHeader
        title="بحث مدل‌ها"
        subtitle="هر debate چند مدل را روی داده‌ی واقعی به بحث می‌گذارد؛ اجماع قطعی محاسبه می‌شود."
        actions={<button className="secondary" onClick={() => setTick((t) => t + 1)}>به‌روزرسانی</button>}
      />
      <Section title="اجراها" error={runs.error} loading={runs.loading}>
        {runs.data && runs.data.length > 0 ? (
          <Table
            columns={[
              { key: "target", label: "هدف", render: (r) => (
                <button className="linkbtn" onClick={() => setOpenId(String(r.id))}>{String(r.target)}</button>
              ) },
              { key: "status", label: "وضعیت", render: (r) => (
                <Badge tone={r.status === "done" ? "ok" : "warn"}>{String(r.status)}</Badge>
              ) },
              { key: "consensus_probability", label: "اجماع", numeric: true, render: (r) => String(r.consensus_probability ?? "—") },
              { key: "disagreement", label: "اختلاف", numeric: true, render: (r) => String(r.disagreement ?? "—") },
            ]}
            rows={runs.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
          />
        ) : (!runs.loading && <Empty text="هنوز debateای اجرا نشده است." />)}
      </Section>
      <p className="hint">اجرای جدید فقط از CLI یا n8n (با تأیید انسانی) انجام می‌شود؛ دکمه‌ی اجرای مستقیم در رابط نیست.</p>
    </div>
  );
}
