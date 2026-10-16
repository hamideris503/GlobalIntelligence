/** Settings panel — providers/models/agents/budget/debate runs (Step 8-B).
 * فارسی RTL. کلید write-only است و بعد از ذخیره از state پاک می‌شود. */
import { useState } from "react";
import { api, getApiBase, setApiBase } from "../api";
import { fa } from "../theme";
import {
  Badge, ConfirmDialog, Field, Modal, PageHeader, Section, StateBanner,
  Table, useApi, useApiKey, useToast,
} from "../ui";

interface Provider {
  id: string; name: string; kind: string; base_url: string | null;
  key_set: boolean; key_hint: string; key_source: string; enabled: boolean;
  last_test_status: string | null; last_tested_at: string | null;
}
interface Model {
  id: string; provider_id: string; provider_name: string; model_name: string;
  price_in_per_mtok: number | null; price_out_per_mtok: number | null; enabled: boolean;
}
interface Assignment {
  agent: string; provider_id: string | null; provider_name: string | null;
  model_id: string | null; model_name: string | null; enabled: boolean;
}
interface DebateRun {
  id: string; target: string; status: string;
  consensus_probability: number | null; disagreement: number | null;
}

const KINDS = [
  { v: "gemini", label: "Gemini" },
  { v: "openrouter", label: "OpenRouter" },
  { v: "groq", label: "Groq" },
  { v: "cloudflare", label: "Cloudflare Workers AI" },
  { v: "openai_compatible", label: "سازگار با OpenAI (سفارشی)" },
];
const AGENTS = ["bull", "bear", "macro", "geopolitical", "risk_critic", "report"];

function err(e: unknown): string {
  return e instanceof Error ? e.message : "خطا";
}

function useRefresh() {
  const [tick, setTick] = useState(0);
  return { tick, refresh: () => setTick((t) => t + 1) };
}

// ---------- تب ۱: ارائه‌دهندگان ----------
function ProvidersTab({ goInternal }: { goInternal: () => void }) {
  const { tick, refresh } = useRefresh();
  const toast = useToast();
  const list = useApi<Provider[]>("/api/settings/providers", [tick]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", kind: "groq", base_url: "", api_key: "", account_id: "", default_model: "", enabled: true });
  const [testing, setTesting] = useState<string | null>(null);
  const [confirmDel, setConfirmDel] = useState<Provider | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const needsKey = (list.error ?? "").includes("کلید API");

  const clearSecrets = () => setForm((f) => ({ ...f, api_key: "", account_id: "" }));

  const submit = async () => {
    if (!form.name.trim()) { setMsg("نام شرکت لازم است."); return; }
    setMsg(null);
    try {
      await api.post("/api/settings/providers", {
        name: form.name.trim(), kind: form.kind,
        base_url: form.kind === "openai_compatible" ? form.base_url.trim() || undefined : undefined,
        api_key: form.api_key || undefined,
        extra: form.kind === "cloudflare" && form.account_id ? { account_id: form.account_id.trim() } : undefined,
        default_model: form.default_model.trim() || undefined,
        enabled: form.enabled,
      });
      clearSecrets();
      setShowAdd(false);
      toast("ارائه‌دهنده ذخیره شد.", "ok");
      refresh();
    } catch (e) {
      const m = err(e);
      setMsg(m);
      if (m.includes("کلید API")) toast("اول کلید API داخلی را در تب «اتصال داخلی» وارد کنید.", "bad");
    }
  };

  const test = async (p: Provider) => {
    setTesting(p.id);
    try {
      const r = await api.post<{ ok: boolean; model: string | null; total_tokens: number | null; latency_ms: number | null; error: string | null }>(
        `/api/settings/providers/${p.id}/test`, {}, 90000);
      toast(r.ok ? `اتصال موفق (${r.model ?? "—"}، ${r.total_tokens ?? "—"} توکن)` : `ناموفق: ${r.error ?? "—"}`, r.ok ? "ok" : "bad");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
    finally { setTesting(null); }
  };

  const testAll = async () => {
    for (const p of list.data ?? []) {
      await test(p);
    }
  };

  const toggle = async (p: Provider) => {
    try {
      await api.put(`/api/settings/providers/${p.id}`, { enabled: !p.enabled });
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  const remove = async () => {
    if (!confirmDel) return;
    try {
      await api.remove(`/api/settings/providers/${confirmDel.id}`);
      toast("حذف شد.", "ok");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
    finally { setConfirmDel(null); }
  };

  const importEnv = async () => {
    try {
      const r = await api.post<{ moved: string[]; skipped: string[]; needs_encryption_key: boolean }>("/api/settings/import-from-env");
      if (r.needs_encryption_key) {
        toast("اول APP_ENCRYPTION_KEY را در .env سرور بگذارید (راهنما پایین).", "bad");
      } else {
        toast(`منتقل شد: ${r.moved.join("، ") || "—"}؛ رد شد: ${r.skipped.join("، ") || "—"}`, "ok");
      }
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  return (
    <div>
      {needsKey && (
        <Section title="اتصال لازم است" error={null}>
          <p>برای مدیریت ارائه‌دهندگان، اول <strong>کلید API داخلی</strong> را وارد کنید (همان API_KEY فایل .env سرور؛ فقط در حافظهٔ همین زبانه می‌ماند).</p>
          <button onClick={goInternal}>رفتن به تب اتصال داخلی</button>
        </Section>
      )}
      <Section title="ارائه‌دهندگان AI" error={list.error} loading={list.loading}
        actions={<span className="row"><button onClick={() => setShowAdd(true)}>افزودن</button><button className="secondary" onClick={testAll}>تست همه</button><button className="secondary" onClick={importEnv}>انتقال کلیدهای .env به اینجا</button></span>}>
        <p className="hint">موارد «از .env» همان کلیدهای فایل .env سرورند (فقط‌خواندنی؛ ویرایش/حذف ندارند). ستون «آخرین تست» نشان می‌دهد کدام وصل و کار می‌کند.</p>
        {list.data && (
          <Table
            columns={[
              { key: "name", label: "شرکت" },
              { key: "kind", label: "نوع" },
              { key: "key_hint", label: "کلید", render: (r) => (
                <Badge tone={r.key_set ? "ok" : "warn"}>{r.key_source === "env" ? "از .env" : (r.key_set ? `تنظیم‌شده ${r.key_hint}` : "نشده")}</Badge>
              ) },
              { key: "last_test_status", label: "وضعیت اتصال", render: (r) => (
                <Badge tone={r.last_test_status === "ok" ? "ok" : (r.last_test_status === "fail" ? "bad" : "info")}>{r.last_test_status === "ok" ? "کار می‌کند" : (r.last_test_status === "fail" ? "خراب" : "تست‌نشده")}</Badge>
              ) },
              { key: "enabled", label: "فعال", render: (r) => (
                <button className="linkbtn" onClick={() => toggle(r as unknown as Provider)}>{r.enabled ? "بله" : "خیر"}</button>
              ) },
              { key: "ops", label: "اقدامات", render: (r) => {
                const p = r as unknown as Provider;
                const envRow = p.key_source === "env";
                return (<span className="row">
                  <button className="linkbtn" onClick={() => test(p)} disabled={testing === p.id}>{testing === p.id ? "…" : "تست اتصال"}</button>
                  {!envRow && <button className="linkbtn" onClick={() => setConfirmDel(p)}>حذف</button>}
                  {envRow && <span className="hint">مدیریت در .env</span>}
                </span>);
              } },
            ]}
            rows={(list.data ?? []) as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
            emptyText="ارائه‌دهنده‌ای ثبت نشده است."
          />
        )}
      </Section>
      <Section title="رمزنگاری" error={null}>
        <p className="hint">کلیدها با APP_ENCRYPTION_KEY سرور رمزنگاری می‌شوند. اگر تنظیم نباشد، ذخیره با خطای واضح رد می‌شود. ساخت کلید (روی سرور): <code dir="ltr">python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"</code> سپس در <code dir="ltr">.env</code> با نام <code dir="ltr">APP_ENCRYPTION_KEY=</code> بگذارید و بکاپ جدا بگیرید.</p>
      </Section>
      {showAdd && (
        <Modal title="افزودن ارائه‌دهنده" onClose={() => { setShowAdd(false); clearSecrets(); }}>
          <Field label="نام شرکت / نمایشی"><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="نوع">
            <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {KINDS.map((k) => <option key={k.v} value={k.v}>{k.label}</option>)}
            </select>
          </Field>
          {form.kind === "openai_compatible" && (
            <Field label="base_url (فقط https؛ هاست خصوصی مسدود است)" hint="مثلاً https://api.example.com/v1">
              <input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} dir="ltr" />
            </Field>
          )}
          {form.kind === "cloudflare" && (
            <Field label="Account ID (جدا از توکن؛ از داشبورد Cloudflare)" hint="الزامی برای Cloudflare">
              <input value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} dir="ltr" autoComplete="off" />
            </Field>
          )}
          <Field label="کلید API (write-only؛ هرگز بازگردانده نمی‌شود)" hint="بعد از ذخیره از حافظهٔ مرورگر پاک می‌شود.">
            <input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} dir="ltr" autoComplete="new-password" />
          </Field>
          <Field label="مدل پیش‌فرض (اختیاری؛ قیمتش را بعداً در تب مدل‌ها ثبت کنید)" hint="مثلاً llama-3.3-70b-versatile">
            <input value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} dir="ltr" />
          </Field>
          {msg && <p className="err-text">{msg}</p>}
          <div className="row">
            <button onClick={submit}>ذخیره</button>
            <button className="secondary" onClick={() => { setShowAdd(false); clearSecrets(); }}>لغو</button>
          </div>
        </Modal>
      )}
      {confirmDel && (
        <ConfirmDialog title="حذف ارائه‌دهنده" danger confirmLabel="حذف"
          message={`«${confirmDel.name}» حذف شود؟ (فقط اعتبارنامه؛ هیچ ردیف تحلیلی حذف نمی‌شود. اگر به agent یا مدلی نگاشت شده باشد، حذف مسدود است.)`}
          onConfirm={remove} onCancel={() => setConfirmDel(null)} />
      )}
    </div>
  );
}

// ---------- تب ۲: مدل‌ها و قیمت ----------
function ModelsTab() {
  const { tick, refresh } = useRefresh();
  const toast = useToast();
  const providers = useApi<Provider[]>("/api/settings/providers", [tick]);
  const models = useApi<Model[]>("/api/settings/models", [tick]);
  const [pid, setPid] = useState("");
  const [discovered, setDiscovered] = useState<string[]>([]);
  const [form, setForm] = useState({ model_name: "", pin: "", pout: "" });
  const [msg, setMsg] = useState<string | null>(null);

  const discover = async () => {
    if (!pid) return;
    try {
      const names = await api.get<string[]>(`/api/settings/providers/${pid}/models`);
      setDiscovered(names);
      if (!names.length) toast("لیست خودکار پشتیبانی نمی‌شود؛ دستی وارد کنید.", "info");
    } catch (e) { toast(err(e), "bad"); }
  };

  const add = async (name?: string) => {
    const modelName = (name ?? form.model_name).trim();
    if (!pid || !modelName) { setMsg("Provider و نام مدل لازم است."); return; }
    try {
      await api.post("/api/settings/models", {
        provider_id: pid, model_name: modelName,
        price_in_per_mtok: form.pin ? Number(form.pin) : undefined,
        price_out_per_mtok: form.pout ? Number(form.pout) : undefined,
      });
      setForm({ model_name: "", pin: "", pout: "" });
      setMsg(null);
      toast("مدل ثبت شد.", "ok");
      refresh();
    } catch (e) { setMsg(err(e)); }
  };

  const remove = async (id: string) => {
    try { await api.remove(`/api/settings/models/${id}`); refresh(); }
    catch (e) { toast(err(e), "bad"); }
  };

  return (
    <div>
      <Section title="مدل‌ها و قیمت" error={models.error} loading={models.loading}>
        <div className="filters">
          <select value={pid} onChange={(e) => setPid(e.target.value)} aria-label="ارائه‌دهنده">
            <option value="">— ارائه‌دهنده —</option>
            {(providers.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>)}
          </select>
          <button className="secondary" onClick={discover}>دریافت لیست مدل‌ها</button>
        </div>
        {discovered.length > 0 && (
          <ul className="list">
            {discovered.slice(0, 30).map((n) => (
              <li key={n}>{n} <button className="linkbtn" onClick={() => add(n)}>+ ثبت</button></li>
            ))}
          </ul>
        )}
        <div className="filters">
          <input placeholder="نام مدل (دستی)" value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} dir="ltr" />
          <input placeholder="قیمت ورودی $/MTok" value={form.pin} onChange={(e) => setForm({ ...form, pin: e.target.value })} dir="ltr" inputMode="decimal" />
          <input placeholder="قیمت خروجی $/MTok" value={form.pout} onChange={(e) => setForm({ ...form, pout: e.target.value })} dir="ltr" inputMode="decimal" />
          <button onClick={() => add()}>ثبت مدل</button>
        </div>
        {msg && <p className="err-text">{msg}</p>}
        <p className="hint">قیمت هر میلیون توکن را از صفحه‌ی رسمی همان مدل بخوانید و وارد کنید؛ قیمت‌ها تغییر می‌کنند و debate بدون قیمت ثبت‌شده متوقف می‌شود.</p>
        {models.data && (
          <Table
            columns={[
              { key: "provider_name", label: "شرکت" },
              { key: "model_name", label: "مدل" },
              { key: "price_in_per_mtok", label: "$ورودی", numeric: true, render: (r) => String(r.price_in_per_mtok ?? "—") },
              { key: "price_out_per_mtok", label: "$خروجی", numeric: true, render: (r) => String(r.price_out_per_mtok ?? "—") },
              { key: "ops", label: "حذف", render: (r) => <button className="linkbtn" onClick={() => remove(String(r.id))}>حذف</button> },
            ]}
            rows={models.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
            emptyText="مدلی ثبت نشده است."
          />
        )}
      </Section>
    </div>
  );
}

// ---------- تب ۳: نگاشت agentها ----------
function AgentsTab() {
  const { tick, refresh } = useRefresh();
  const toast = useToast();
  const providers = useApi<Provider[]>("/api/settings/providers", [tick]);
  const models = useApi<Model[]>("/api/settings/models", [tick]);
  const assigns = useApi<Assignment[]>("/api/settings/agent-assignments", [tick]);
  const diversity = useApi<{ distinct_models: number; distinct_providers: number; warning: string | null }>("/api/settings/diversity", [tick]);
  const [sel, setSel] = useState<Record<string, { p: string; m: string }>>({});

  const save = async () => {
    try {
      const items = AGENTS.map((a) => ({
        agent: a,
        provider_id: sel[a]?.p || assigns.data?.find((x) => x.agent === a)?.provider_id || null,
        model_id: sel[a]?.m || assigns.data?.find((x) => x.agent === a)?.model_id || null,
      }));
      await api.put("/api/settings/agent-assignments", items);
      toast("نگاشت ذخیره شد.", "ok");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  return (
    <div>
      {diversity.data?.warning && <StateBanner state="demo" text={diversity.data.warning} />}
      <Section title="نگاشت agentها" error={assigns.error} loading={assigns.loading}
        actions={<button onClick={save}>ذخیره</button>}>
        <p className="hint">مدل‌های مجزا: {diversity.data?.distinct_models ?? "—"} · شرکت‌های مجزا: {diversity.data?.distinct_providers ?? "—"}</p>
        {AGENTS.map((a) => {
          const cur = assigns.data?.find((x) => x.agent === a);
          const p = sel[a]?.p ?? cur?.provider_id ?? "";
          const modelsOf = (models.data ?? []).filter((m) => !p || m.provider_id === p);
          return (
            <div className="filters" key={a}>
              <strong style={{ minWidth: 110 }}>{a}</strong>
              <select value={p} onChange={(e) => setSel({ ...sel, [a]: { p: e.target.value, m: "" } })} aria-label={`provider ${a}`}>
                <option value="">—</option>
                {(providers.data ?? []).filter((x) => x.enabled).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
              </select>
              <select value={sel[a]?.m ?? cur?.model_id ?? ""} onChange={(e) => setSel({ ...sel, [a]: { p, m: e.target.value } })} aria-label={`model ${a}`}>
                <option value="">— پیش‌فرض —</option>
                {modelsOf.filter((x) => x.enabled).map((x) => <option key={x.id} value={x.id}>{x.model_name}</option>)}
              </select>
            </div>
          );
        })}
      </Section>
    </div>
  );
}

// ---------- تب ۴: بودجه و سقف‌ها ----------
function BudgetTab() {
  const { tick, refresh } = useRefresh();
  const toast = useToast();
  const app = useApi<Record<string, string>>("/api/settings/app", [tick]);
  const spend = useApi<{ tokens_today: number; usd_today: number }>("/api/settings/spend-today", [tick]);
  const mock = useApi<{ mock_mode: boolean; default_provider: string }>("/api/ai/status", [tick]);
  const providers = useApi<{ id: string; name: string; kind: string }[]>("/api/settings/providers", [tick]);
  const [form, setForm] = useState({ debate_daily_budget_usd: "", debate_max_tokens_per_run: "", debate_max_rounds: "" });
  const [provider, setProvider] = useState("");

  const setMode = async (real: boolean) => {
    try {
      await api.put("/api/settings/app", { settings: { mock_mode: real ? "false" : "true" } });
      toast(real ? "حالت واقعی فعال شد — پاسخ‌ها واقعی‌اند." : "حالت آزمایشی فعال شد.", real ? "ok" : "info");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  const setDefaultProvider = async () => {
    if (!provider) return;
    try {
      await api.put("/api/settings/app", { settings: { ai_default_provider: provider } });
      toast("ارائه‌دهندهٔ پیش‌فرض ذخیره شد.", "ok");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  const save = async () => {
    try {
      const settings: Record<string, string> = {};
      for (const [k, v] of Object.entries(form)) if (v.trim()) settings[k] = v.trim();
      if (!Object.keys(settings).length) { toast("مقداری وارد نشده است.", "bad"); return; }
      await api.put("/api/settings/app", { settings });
      toast("ذخیره شد.", "ok");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  const budget = Number(app.data?.debate_daily_budget_usd ?? NaN);
  const spent = spend.data?.usd_today ?? 0;
  const left = Number.isFinite(budget) ? budget - spent : NaN;

  return (
    <div>
      {mock.data?.mock_mode && <StateBanner state="demo" text="حالت آزمایشی (Mock) روشن است؛ خروجی‌ها واقعی نیستند." />}
      <Section title="حالت اجرا" error={mock.error} loading={mock.loading}>
        <p>
          وضعیت فعلی: <Badge tone={mock.data?.mock_mode ? "warn" : "ok"}>{mock.data?.mock_mode ? "آزمایشی (Mock)" : "واقعی"}</Badge>
          {" "}· پیش‌فرض: <strong>{mock.data?.default_provider ?? "—"}</strong>
        </p>
        <div className="row">
          <button onClick={() => setMode(true)} disabled={!mock.data?.mock_mode}>فعال‌سازی حالت واقعی</button>
          <button className="secondary" onClick={() => setMode(false)} disabled={mock.data?.mock_mode !== false}>برگرداندن به آزمایشی</button>
        </div>
        <div className="filters" style={{ marginTop: 8 }}>
          <select value={provider} onChange={(e) => setProvider(e.target.value)} aria-label="ارائه‌دهنده پیش‌فرض">
            <option value="">— ارائه‌دهندهٔ پیش‌فرض —</option>
            {(providers.data ?? []).map((p) => <option key={p.id} value={p.kind}>{p.name} ({p.kind})</option>)}
          </select>
          <button className="secondary" onClick={setDefaultProvider}>ذخیره پیش‌فرض</button>
        </div>
        <p className="hint">بدون ری‌استارت اعمال می‌شود. در حالت واقعی، هر درخواست به ارائه‌دهندهٔ واقعی می‌رود و هزینه/سهمیه مصرف می‌کند.</p>
      </Section>
      <Section title="بودجه و سقف‌ها" error={app.error} loading={app.loading}>
        <p className="hint">فعلی: بودجه روزانه {app.data?.debate_daily_budget_usd ?? "—"}$ · سقف توکن {app.data?.debate_max_tokens_per_run ?? "—"} · حداکثر دور {app.data?.debate_max_rounds ?? "—"}</p>
        <div className="filters">
          <input placeholder="بودجه روزانه ($)" value={form.debate_daily_budget_usd} onChange={(e) => setForm({ ...form, debate_daily_budget_usd: e.target.value })} dir="ltr" inputMode="decimal" />
          <input placeholder="سقف توکن هر اجرا" value={form.debate_max_tokens_per_run} onChange={(e) => setForm({ ...form, debate_max_tokens_per_run: e.target.value })} dir="ltr" inputMode="numeric" />
          <input placeholder="حداکثر دور" value={form.debate_max_rounds} onChange={(e) => setForm({ ...form, debate_max_rounds: e.target.value })} dir="ltr" inputMode="numeric" />
          <button onClick={save}>ذخیره</button>
        </div>
      </Section>
      <Section title="مصرف امروز" error={spend.error} loading={spend.loading}>
        {spend.data && <p>توکن: {fa(spend.data.tokens_today, 0)} · دلار: {fa(spend.data.usd_today, 4)} · باقیمانده: {Number.isFinite(left) ? fa(left, 4) + "$" : "—"}</p>}
      </Section>
    </div>
  );
}

// ---------- تب ۵: اجرای debate ----------
function RunsTab() {
  const { tick, refresh } = useRefresh();
  const toast = useToast();
  const runs = useApi<DebateRun[]>("/api/debate/runs?limit=30", [tick]);
  const [target, setTarget] = useState("market:WTI");
  const [est, setEst] = useState<string | null>(null);
  const [confirmRun, setConfirmRun] = useState(false);
  const [voidId, setVoidId] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");

  const estimate = async () => {
    setEst("در حال تخمین…");
    try {
      const r = await api.post<{ status: string; total_tokens: number; errors: string[] }>(
        "/api/debate/run", { target, dry_run: true });
      setEst(`وضعیت: ${r.status} · توکن تخمینی: ${fa(r.total_tokens, 0)} · ${r.errors.join("؛ ")}`);
    } catch (e) { setEst(err(e)); }
  };

  const run = async () => {
    try {
      const r = await api.post<{ status: string; consensus: number | null; run_id: string | null; errors: string[] }>(
        "/api/debate/run", { target, live: true }, 600000);
      toast(`نتیجه: ${r.status} (اجماع ${r.consensus ?? "—"})`, r.status === "done" ? "ok" : "bad");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
    finally { setConfirmRun(false); }
  };

  const voidRun = async () => {
    if (!voidId || voidReason.trim().length < 3) { toast("دلیل باطل‌کردن لازم است.", "bad"); return; }
    try {
      await api.post(`/api/settings/debate-runs/${voidId}/void`, { reason: voidReason.trim() });
      toast("باطل شد (حذف نشد).", "ok");
      setVoidId(null); setVoidReason("");
      refresh();
    } catch (e) { toast(err(e), "bad"); }
  };

  return (
    <div>
      <Section title="اجرای debate" error={null}>
        <div className="filters">
          <input placeholder="target (مثل market:WTI)" value={target} onChange={(e) => setTarget(e.target.value)} dir="ltr" />
          <button className="secondary" onClick={estimate}>تخمین هزینه</button>
          <button onClick={() => setConfirmRun(true)}>اجرا</button>
        </div>
        {est && <p className="hint">{est}</p>}
        <p className="hint">اجرا با تأیید انجام می‌شود و هزینه‌ی واقعی از قیمت‌های ثبت‌شده حساب می‌شود. اگر قیمت مدلی ثبت نشده باشد، با price_missing متوقف می‌شود.</p>
      </Section>
      <Section title="اجراها" error={runs.error} loading={runs.loading}>
        {runs.data && (
          <Table
            columns={[
              { key: "target", label: "هدف" },
              { key: "status", label: "وضعیت", render: (r) => <Badge tone={r.status === "done" ? "ok" : "warn"}>{String(r.status)}</Badge> },
              { key: "consensus_probability", label: "اجماع", numeric: true, render: (r) => String(r.consensus_probability ?? "—") },
              { key: "ops", label: "باطل", render: (r) => (
                String(r.status) === "void" ? <span>باطل‌شده</span> :
                <button className="linkbtn" onClick={() => setVoidId(String(r.id))}>باطل‌کردن</button>
              ) },
            ]}
            rows={runs.data as unknown as Record<string, unknown>[]}
            rowKey={(r) => String(r.id)}
            emptyText="اجرایی ثبت نشده است."
          />
        )}
      </Section>
      {confirmRun && (
        <ConfirmDialog title="اجرای debate واقعی" confirmLabel="اجرا کن"
          message={`debate روی «${target}» اجرا شود؟ هزینه از سهمیه‌ی روزانه کم می‌شود.`}
          onConfirm={run} onCancel={() => setConfirmRun(false)} />
      )}
      {voidId && (
        <Modal title="باطل‌کردن اجرا (به‌جای حذف)" onClose={() => setVoidId(null)}>
          <Field label="دلیل (الزامی)"><input value={voidReason} onChange={(e) => setVoidReason(e.target.value)} /></Field>
          <div className="row"><button className="danger" onClick={voidRun}>باطل کن</button><button className="secondary" onClick={() => setVoidId(null)}>لغو</button></div>
        </Modal>
      )}
    </div>
  );
}

// ---------- تب ۰: اتصال داخلی ----------
function InternalTab() {
  const { keySet, saveKey, clearKey } = useApiKey();
  const [key, setKey] = useState("");
  const [base, setBase] = useState(getApiBase());
  const [user, setUser] = useState("admin");
  const [pass, setPass] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const toast = useToast();

  const login = async () => {
    if (!user.trim() || !pass) { setMsg("نام کاربری و رمز را وارد کنید."); return; }
    setMsg("در حال ورود…");
    try {
      const r = await api.post<{ ok: boolean; api_key: string }>("/api/auth/login", {
        username: user.trim(), password: pass,
      });
      setPass("");
      if (r.api_key) {
        saveKey(r.api_key);
        setMsg("وارد شدید؛ کلید در حافظهٔ همین زبانه ثبت شد.");
      } else {
        setMsg("وارد شدید (سرور کلید داخلی ندارد؛ حالت آزاد).");
      }
    } catch (e) { setMsg(err(e)); }
  };

  return (
    <div>
      <Section title="ورود" error={null}>
        <p className="hint">با نام کاربری و رمز وارد شوید (پیش‌فرض: admin / admin — در سرور واقعی عوض کنید). نیازی به تایپ کلید طولانی نیست.</p>
        <Field label="نام کاربری">
          <input value={user} onChange={(e) => setUser(e.target.value)} dir="ltr" autoComplete="username" />
        </Field>
        <Field label="رمز">
          <input type="password" value={pass} onChange={(e) => setPass(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") login(); }}
            dir="ltr" autoComplete="current-password" />
        </Field>
        <div className="row">
          <button onClick={login}>ورود</button>
        </div>
        {msg && <p className="hint">{msg}</p>}
        <p>وضعیت کلید: <Badge tone={keySet ? "ok" : "warn"}>{keySet ? "ثبت‌شده (فقط حافظه)" : "ثبت‌نشده"}</Badge></p>
      </Section>
      <Section title="کلید API داخلی (دستی)" error={null}>
        <Field label="کلید (فقط حافظهٔ همین زبانه)" hint="همان API_KEY فایل .env سرور؛ جایگزین ورود بالا.">
          <input type="password" value={key} onChange={(e) => setKey(e.target.value)} dir="ltr" autoComplete="off" />
        </Field>
        <div className="row">
          <button onClick={() => { saveKey(key); setKey(""); setMsg("ثبت شد."); }}>ذخیره در حافظه</button>
          <button className="secondary" onClick={() => { clearKey(); setMsg("پاک شد."); }}>پاک کردن</button>
        </div>
      </Section>
      <Section title="نشانی Backend" error={null}>
        <Field label="API Base (فقط حافظه)">
          <input value={base} onChange={(e) => setBase(e.target.value)} dir="ltr" />
        </Field>
        <button onClick={() => { setApiBase(base); toast("نشانی به‌روز شد.", "ok"); }}>اعمال</button>
      </Section>
    </div>
  );
}

const TABS = [
  { id: "providers", label: "ارائه‌دهندگان AI" },
  { id: "models", label: "مدل‌ها و قیمت" },
  { id: "agents", label: "نگاشت agentها" },
  { id: "budget", label: "بودجه و سقف‌ها" },
  { id: "runs", label: "اجرای debate" },
  { id: "internal", label: "اتصال داخلی" },
];

export function SettingsPanel() {
  const [tab, setTab] = useState("providers");
  return (
    <div>
      <PageHeader title="تنظیمات" subtitle="مدیریت ارائه‌دهندگان، مدل‌ها، agentها، بودجه و اجراها — بدون ویرایش .env." />
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id}
            className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      {tab === "providers" && <ProvidersTab goInternal={() => setTab("internal")} />}
      {tab === "models" && <ModelsTab />}
      {tab === "agents" && <AgentsTab />}
      {tab === "budget" && <BudgetTab />}
      {tab === "runs" && <RunsTab />}
      {tab === "internal" && <InternalTab />}
    </div>
  );
}
