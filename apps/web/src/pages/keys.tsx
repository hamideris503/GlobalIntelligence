/** کلیدها و سرویس‌ها: برای هر سرویس نشان می‌دهد چه متغیری، کجا، و علاوه بر کلید چه چیزی لازم است. */
import { useMemo, useState } from "react";
import { GROUP_TITLES, SERVICES } from "../config/services";
import type { EnvVar, Service } from "../config/services";
import { Icon } from "../icons";
import type { AIProvider, AIStatus } from "../types";
import { Badge, Empty, PageHeader, StateBanner, useApi, useApiKey, useToast } from "../ui";

function copy(text: string, toast: (t: string, tone?: "ok" | "bad" | "info") => void) {
  navigator.clipboard?.writeText(text).then(() => toast("کپی شد.", "ok"), () => toast("کپی ممکن نشد.", "bad"));
}

function Step({ ok, title, hint }: { ok: boolean | null; title: string; hint: string }) {
  const tone = ok === null ? "info" : ok ? "ok" : "warn";
  return (
    <li className="step">
      <span className={`step-dot ${tone}`}>{ok ? <Icon name="check" size={14} /> : ok === null ? "…" : "!"}</span>
      <div><strong>{title}</strong><div className="hint">{hint}</div></div>
    </li>
  );
}

function ProviderStatus({ s, providers, loading, err }: { s: Service; providers: AIProvider[] | null; loading: boolean; err: string | null }) {
  if (s.support === "not_implemented") return <Badge tone="warn">پیاده‌سازی‌نشده در Backend</Badge>;
  if (s.support === "no_key") return <Badge tone="ok">بدون کلید</Badge>;
  if (!s.providerId) return <Badge tone="info">تنظیم سرور</Badge>;
  if (loading) return <Badge tone="info">در حال بررسی</Badge>;
  if (err) return <Badge tone="info" >نامشخص</Badge>;
  const p = providers?.find((x) => x.provider === s.providerId);
  if (!p) return <Badge tone="warn">در Backend یافت نشد</Badge>;
  return p.healthy ? <Badge tone="ok">کلید ثبت شده</Badge> : <Badge tone="bad">کلید ثبت نشده</Badge>;
}

export default function Keys() {
  const toast = useToast();
  const { keySet } = useApiKey();
  const ai = useApi<AIStatus>("/api/ai/status", []);
  const prov = useApi<AIProvider[]>("/api/ai/providers", []);
  const [open, setOpen] = useState<string | null>("gemini");
  const [vals, setVals] = useState<Record<string, string>>({});
  const [reveal, setReveal] = useState(false);

  const configured = prov.data?.filter((p) => p.provider !== "mock" && p.healthy).map((p) => p.provider) ?? [];
  const realProviderSet = !!ai.data && ai.data.default_provider !== "mock";

  const envBlock = useMemo(() => {
    const lines: string[] = [];
    for (const s of SERVICES) for (const v of s.vars) {
      const val = vals[v.name];
      if (val !== undefined && val !== "") lines.push(`${v.name}=${val}`);
    }
    return lines.join("\n");
  }, [vals]);
  const shownBlock = reveal ? envBlock : envBlock.replace(/^([A-Z_]*(KEY|PASSWORD|SECRET|TOKEN)[A-Z_]*)=.+$/gm, "$1=••••••••");

  const groups = (["ai", "data", "security"] as const);

  return (
    <div>
      <PageHeader title="کلیدها و سرویس‌ها" subtitle="هر سرویس چه چیزی می‌خواهد، آن را کجا باید گذاشت، و چه چیزی غیر از کلید لازم است." />

      <div className="banner nc" role="note">
        <Icon name="info" size={18} />
        <div>
          <strong>کلیدها فقط در فایل <code>.env</code> سرور (کنار <code>docker-compose.yml</code>) ذخیره می‌شوند. </strong>
          این رابط هیچ کلیدی را ذخیره یا به Backend ارسال نمی‌کند، چون Backend فعلی endpoint ذخیرهٔ کلید ندارد. می‌توانید پایین‌تر مقدارها را وارد کنید تا یک بلوک آمادهٔ <code>.env</code> بسازد.
        </div>
      </div>

      <section className="panel">
        <div className="panel-head"><h2>چک‌لیست راه‌اندازی (وضعیت زنده)</h2></div>
        <ul className="steps">
          <Step ok={keySet} title="کلید داخلی API در رابط ثبت شده" hint="مقدار API_KEY فایل .env را در «تنظیمات» وارد کنید." />
          <Step ok={ai.loading ? null : ai.data ? !ai.data.mock_mode : false} title="حالت واقعی فعال است (MOCK_MODE=false)" hint={ai.error ? `نامشخص: ${ai.error}` : ai.data?.mock_mode ? "الان Mock فعال است؛ حتی با کلید معتبر خروجی نمونه می‌آید." : "حالت واقعی فعال است."} />
          <Step ok={ai.loading ? null : realProviderSet} title="ارائه‌دهندهٔ پیش‌فرض واقعی انتخاب شده" hint={ai.data ? `الان: ${ai.data.default_provider}` : "AI_DEFAULT_PROVIDER را روی gemini/openai/anthropic/openrouter بگذارید."} />
          <Step ok={prov.loading ? null : configured.length > 0} title="حداقل یک کلید ارائه‌دهنده ثبت شده" hint={configured.length ? `ثبت‌شده: ${configured.join("، ")}` : "هیچ کلید واقعی‌ای توسط Backend دیده نشد."} />
        </ul>
        <p className="hint">«کلید ثبت شده» یعنی Backend مقدار را دیده است، نه اینکه معتبر باشد. اعتبار کلید و مدل فقط با «آزمایش اتصال» در صفحهٔ <button className="linkbtn" onClick={() => { window.location.hash = "#/ai"; }}>هوش مصنوعی و مدل‌ها</button> معلوم می‌شود.</p>
      </section>

      {groups.map((g) => (
        <section key={g} className="panel">
          <div className="panel-head"><h2>{GROUP_TITLES[g]}</h2></div>
          <div className="svc-list">
            {SERVICES.filter((s) => s.group === g).map((s) => {
              const isOpen = open === s.id;
              return (
                <div key={s.id} className={`svc ${isOpen ? "open" : ""}`}>
                  <button className="svc-head" onClick={() => setOpen(isOpen ? null : s.id)} aria-expanded={isOpen}>
                    <span className="svc-name">{s.name}</span>
                    <span className="svc-meta"><ProviderStatus s={s} providers={prov.data} loading={prov.loading} err={prov.error} /></span>
                    <Icon name="chevron" size={18} style={{ transform: isOpen ? "rotate(90deg)" : "none", transition: "transform .15s" }} />
                  </button>
                  {isOpen && (
                    <div className="svc-body">
                      <p>{s.purpose}</p>
                      {s.support === "not_implemented" && <StateBanner state="nc" text="Backend فعلی این سرویس را نمی‌خواند؛ ثبت کلید تنها کافی نیست و نیاز به توسعهٔ Backend دارد." />}
                      <div className="tablewrap">
                        <table>
                          <thead><tr><th>متغیر در .env</th><th>الزامی</th><th>پیش‌فرض</th><th>توضیح</th><th>مقدار (برای ساخت بلوک)</th></tr></thead>
                          <tbody>
                            {s.vars.map((v: EnvVar) => (
                              <tr key={v.name}>
                                <td><code className="ltr">{v.name}</code> <button className="ghost" onClick={() => copy(v.name, toast)} aria-label={`کپی ${v.name}`}>کپی</button></td>
                                <td>{v.required ? <Badge tone="warn">بله</Badge> : "خیر"}</td>
                                <td>{v.def ? <code className="ltr">{v.def}</code> : "—"}</td>
                                <td style={{ minWidth: 220 }}>{v.help}</td>
                                <td>
                                  <input dir="ltr" type={v.kind === "secret" && !reveal ? "password" : "text"} autoComplete="off" spellCheck={false}
                                    placeholder={v.def ?? ""} value={vals[v.name] ?? ""} onChange={(e) => setVals({ ...vals, [v.name]: e.target.value })} aria-label={v.name} style={{ width: 200 }} />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <h4 className="subhead">علاوه بر کلید لازم است</h4>
                      <ul className="list">{s.alsoNeeded.map((t) => <li key={t}>{t}</li>)}</ul>
                      <dl className="kv" style={{ marginTop: 12 }}>
                        <dt>کد مصرف‌کننده</dt><dd><code className="ltr">{s.usedBy}</code></dd>
                        {s.getKeyUrl && <><dt>دریافت کلید</dt><dd><a href={s.getKeyUrl} target="_blank" rel="noreferrer noopener" className="ltr">{s.getKeyUrl}</a></dd></>}
                        {s.docsUrl && <><dt>مستندات</dt><dd><a href={s.docsUrl} target="_blank" rel="noreferrer noopener" className="ltr">{s.docsUrl}</a></dd></>}
                      </dl>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}

      <section className="panel">
        <div className="panel-head">
          <h2>بلوک آمادهٔ <code>.env</code></h2>
          <div className="row">
            <button className="secondary" onClick={() => setReveal(!reveal)}><Icon name="eye" size={16} /> {reveal ? "مخفی‌کردن مقادیر" : "نمایش مقادیر"}</button>
            <button disabled={!envBlock} onClick={() => copy(envBlock, toast)}>کپی بلوک</button>
            <button className="secondary" disabled={!envBlock} onClick={() => setVals({})}>پاک‌کردن</button>
          </div>
        </div>
        <p className="hint">مقادیر فقط در حافظهٔ همین صفحه‌اند و با بستن یا رفرش پاک می‌شوند. بلوک را در فایل <code>.env</code> سرور، جایگزین خط هم‌نام، بچسبانید و Backend را دوباره بسازید. اگر <code>.env</code> دارای خط تکراری باشد، آخرین خط ملاک است.</p>
        {envBlock ? <pre className="envblock" dir="ltr">{shownBlock}</pre> : <Empty text="هنوز مقداری وارد نشده است." />}
      </section>
    </div>
  );
}
