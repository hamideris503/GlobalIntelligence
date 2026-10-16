/** Shared UI: shell, tables, forms, charts (zero deps). */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { ApiError, api, faError, getApiKey, setApiKey } from "./api";
import { Icon } from "./icons";
import { NAV_GROUPS, nav, useRoute } from "./router";
import { useTheme } from "./theme";

// ---------- API key state (memory only, never persisted) ----------
interface KeyCtx {
  keySet: boolean;
  saveKey: (k: string) => void;
  clearKey: () => void;
  version: number;
}
const KeyContext = createContext<KeyCtx>({
  keySet: false,
  saveKey: () => {},
  clearKey: () => {},
  version: 0,
});

export function KeyProvider({ children }: { children: ReactNode }) {
  const [keySet, setKeySet] = useState(() => getApiKey().length > 0);
  const [version, setVersion] = useState(0);
  const saveKey = useCallback((k: string) => {
    setApiKey(k);
    setKeySet(k.length > 0);
    setVersion((v) => v + 1);
  }, []);
  const clearKey = useCallback(() => {
    setApiKey("");
    setKeySet(false);
    setVersion((v) => v + 1);
  }, []);
  return (
    <KeyContext.Provider value={{ keySet, saveKey, clearKey, version }}>
      {children}
    </KeyContext.Provider>
  );
}

export function useApiKey() {
  return useContext(KeyContext);
}

// ---------- data hook: loading / data / empty / error ----------
export function useApi<T>(path: string | null, deps: unknown[] = [], timeoutMs?: number) {
  const { version } = useApiKey();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    let live = true;
    setLoading(true);
    setError(null);
    api
      .get<T>(path, timeoutMs)
      .then((r) => live && (setData(r), setLoading(false)))
      .catch((e: unknown) => live && (setError(faError(e)), setLoading(false)));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, version, ...deps]);
  return { data, error, loading };
}

// ---------- primitives ----------
export function Badge({ tone, children }: { tone: "ok" | "warn" | "bad" | "info" | "demo"; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/** Sortable table. columns: key + label + optional render. */
export function Table<T extends Record<string, unknown>>({
  columns,
  rows,
  rowKey,
  emptyText,
}: {
  columns: { key: string; label: string; render?: (row: T) => ReactNode; numeric?: boolean }[];
  rows: T[];
  rowKey: (row: T, i: number) => string;
  emptyText?: string;
}) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [asc, setAsc] = useState(true);
  const sorted = [...rows].sort((a, b) => {
    if (!sortKey) return 0;
    const av = a[sortKey];
    const bv = b[sortKey];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    const cmp = typeof av === "number" && typeof bv === "number"
      ? av - bv
      : String(av).localeCompare(String(bv), "fa");
    return asc ? cmp : -cmp;
  });
  const toggle = (key: string) => {
    if (sortKey === key) setAsc(!asc);
    else {
      setSortKey(key);
      setAsc(true);
    }
  };
  if (!rows.length) return <Empty text={emptyText} />;
  return (
    <div className="tablewrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key}>
                <button
                  className="thbtn"
                  onClick={() => toggle(c.key)}
                  aria-label={`مرتب‌سازی بر اساس ${c.label}`}
                >
                  {c.label}
                  {sortKey === c.key ? (asc ? " ▲" : " ▼") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={rowKey(r, i)}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? "num" : undefined}>
                  {c.render ? c.render(r) : String(r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Button that POSTs to a run endpoint and shows progress/result. */
export function RunButton({
  label,
  path,
  body,
  timeoutMs,
  onDone,
}: {
  label: string;
  path: string;
  body?: unknown;
  timeoutMs?: number;
  onDone?: (result: unknown) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    setBusy(true);
    setResult(null);
    setError(null);
    try {
      const r = await api.post<Record<string, unknown>>(path, body, timeoutMs ?? 180000);
      const summary = Object.entries(r)
        .filter(([, v]) => typeof v === "number" || typeof v === "string")
        .slice(0, 6)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" · ");
      setResult(summary || "انجام شد.");
      onDone?.(r);
    } catch (e) {
      setError(faError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="runbox">
      <button className="secondary" onClick={run} disabled={busy}>
        {busy ? "در حال اجرا…" : label}
      </button>
      {busy && <span className="hint">در حال پردازش…</span>}
      {result && <span className="ok-text">{result}</span>}
      {error && <span className="err-text">{error}</span>}
    </span>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay" onClick={onClose} role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="ghost" onClick={onClose} aria-label="بستن"><Icon name="close" size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

/** Hand-rolled SVG sparkline (no deps). */
export function Sparkline({ values, width = 160, height = 40 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <span className="hint">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * width},${height - ((v - min) / span) * (height - 4) - 2}`)
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg width={width} height={height} role="img" aria-label="نمودار روند">
      <polyline points={pts} fill="none" stroke={up ? "var(--ok)" : "var(--bad)"} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

/** Hand-rolled horizontal bars (no deps). */
export function Bars({ items }: { items: { label: string; value: number }[] }) {
  const max = Math.max(1e-9, ...items.map((i) => Math.abs(i.value)));
  return (
    <div className="bars">
      {items.map((i) => (
        <div className="bar-row" key={i.label}>
          <span className="bar-label">{i.label}</span>
          <div className="bar-track">
            <div
              className={`bar-fill ${i.value < 0 ? "neg" : ""}`}
              style={{ width: `${(Math.abs(i.value) / max) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- toasts ----------
interface Toast { id: number; text: string; tone: "ok" | "bad" | "info" }
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

// ---------- page-level building blocks ----------
export type PageState = "demo" | "dev" | "nc";
const STATE_COPY: Record<PageState, { cls: string; icon: string; title: string; text: string }> = {
  demo: { cls: "demo", icon: "flask", title: "نمایشی", text: "داده‌های این بخش نمونه‌اند و به سرویس واقعی وصل نیستند." },
  dev: { cls: "dev", icon: "tool", title: "در دست توسعه", text: "این بخش هنوز در Backend پیاده‌سازی نشده است." },
  nc: { cls: "nc", icon: "plug", title: "نیازمند اتصال", text: "برای فعال‌شدن این بخش، API متناظر در Backend لازم است." },
};
/** برچسب شفاف برای بخش‌هایی که واقعی نیستند: demo | dev | nc */
export function StateBanner({ state, text }: { state: PageState; text?: string }) {
  const c = STATE_COPY[state];
  return (
    <div className={`banner ${c.cls}`} role="note">
      <Icon name={c.icon} size={18} />
      <div><strong>{c.title}: </strong>{text ?? c.text}</div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="page-sub">{subtitle}</p>}
      </div>
      {actions && <div className="row">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, unit, icon, foot, tone }: { label: string; value: ReactNode; unit?: string; icon: string; foot?: ReactNode; tone?: "ok" | "warn" | "bad" }) {
  return (
    <div className="card stat">
      <div className="stat-top">
        <span className="card-label">{label}</span>
        <span className="stat-ico" style={tone ? { background: `color-mix(in srgb, var(--${tone}) 15%, transparent)`, color: `var(--${tone})` } : undefined}><Icon name={icon} size={18} /></span>
      </div>
      <div className="stat-val">{value}{unit && <small>{unit}</small>}</div>
      {foot && <div className="stat-foot">{foot}</div>}
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel = "تأیید", danger, onConfirm, onCancel }: { title: string; message: string; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onCancel: () => void }) {
  return (
    <Modal title={title} onClose={onCancel}>
      <p>{message}</p>
      <div className="row">
        <button className={danger ? "danger" : undefined} onClick={onConfirm}>{confirmLabel}</button>
        <button className="secondary" onClick={onCancel}>لغو</button>
      </div>
    </Modal>
  );
}

/** نمودار خطی/مساحتی SVG (بدون وابستگی). series: یک یا چند خط با مقادیر هم‌طول labels. */
export function LineChart({ labels, series, height = 200 }: { labels: string[]; series: { name: string; values: number[]; color?: string }[]; height?: number }) {
  const W = 640, P = { l: 8, r: 8, t: 12, b: 24 };
  const all = series.flatMap((s) => s.values);
  if (labels.length < 2 || all.length === 0) return <Empty text="داده‌ٔ کافی برای رسم نمودار نیست." />;
  const min = Math.min(...all), max = Math.max(...all), span = max - min || 1;
  const x = (i: number) => P.l + (i / (labels.length - 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - (v - min) / span) * (height - P.t - P.b);
  const colors = ["var(--brand)", "var(--info)", "var(--warn)", "var(--demo)"];
  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${W} ${height}`} role="img" aria-label="نمودار روند">
        {[0, 0.5, 1].map((t) => <line key={t} x1={P.l} x2={W - P.r} y1={P.t + t * (height - P.t - P.b)} y2={P.t + t * (height - P.t - P.b)} stroke="var(--chart-grid)" />)}
        {series.map((s, si) => {
          const c = s.color ?? colors[si % colors.length];
          const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
          return (
            <g key={s.name}>
              {si === 0 && <polygon points={`${x(0)},${height - P.b} ${pts} ${x(s.values.length - 1)},${height - P.b}`} fill={c} opacity="0.1" />}
              <polyline points={pts} fill="none" stroke={c} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
            </g>
          );
        })}
        <text x={P.l} y={height - 6}>{labels[0]}</text>
        <text x={W - P.r} y={height - 6} textAnchor="end">{labels[labels.length - 1]}</text>
        <text x={P.l} y={P.t + 10}>{Math.round(max).toLocaleString("fa-IR")}</text>
        <text x={P.l} y={height - P.b - 4}>{Math.round(min).toLocaleString("fa-IR")}</text>
      </svg>
      {series.length > 1 && <div className="legend">{series.map((s, i) => <span key={s.name}><i style={{ background: s.color ?? colors[i % colors.length] }} />{s.name}</span>)}</div>}
    </div>
  );
}

/** نمودار حلقه‌ای برای توزیع (مثلاً موضوع خبرها). */
export function Donut({ items, size = 150 }: { items: { label: string; value: number }[]; size?: number }) {
  const total = items.reduce((a, b) => a + b.value, 0);
  if (!total) return <Empty text="داده‌ای برای توزیع نیست." />;
  const colors = ["var(--brand)", "var(--info)", "var(--warn)", "var(--demo)", "var(--ok)", "var(--bad)"];
  const r = 52, c = 2 * Math.PI * r;
  let acc = 0;
  return (
    <div className="row" style={{ gap: 20, alignItems: "center" }}>
      <svg width={size} height={size} viewBox="0 0 140 140" role="img" aria-label="توزیع">
        <circle cx="70" cy="70" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="18" />
        {items.map((it, i) => {
          const len = (it.value / total) * c;
          const el = <circle key={it.label} cx="70" cy="70" r={r} fill="none" stroke={colors[i % colors.length]} strokeWidth="18" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-acc} transform="rotate(-90 70 70)" />;
          acc += len;
          return el;
        })}
      </svg>
      <div className="legend" style={{ flexDirection: "column", gap: 6, marginTop: 0 }}>
        {items.map((it, i) => <span key={it.label}><i style={{ background: colors[i % colors.length] }} />{it.label} <strong style={{ color: "var(--fg)" }}>{it.value}</strong></span>)}
      </div>
    </div>
  );
}

/** جدول با جست‌وجو و صفحه‌بندی. برای جدول‌های ساده‌تر از Table استفاده کنید. */
export function DataTable<T extends Record<string, unknown>>({ columns, rows, rowKey, emptyText, pageSize = 10, searchKeys }: { columns: { key: string; label: string; render?: (row: T) => ReactNode; numeric?: boolean }[]; rows: T[]; rowKey: (row: T, i: number) => string; emptyText?: string; pageSize?: number; searchKeys?: string[] }) {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(0);
  const needle = q.trim().toLowerCase();
  const filtered = needle && searchKeys ? rows.filter((r) => searchKeys.some((k) => String(r[k] ?? "").toLowerCase().includes(needle))) : rows;
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const cur = Math.min(page, pages - 1);
  const slice = filtered.slice(cur * pageSize, (cur + 1) * pageSize);
  return (
    <div>
      {searchKeys && (
        <div className="filters">
          <input placeholder="جست‌وجو در جدول…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} aria-label="جست‌وجو در جدول" />
        </div>
      )}
      <Table columns={columns} rows={slice} rowKey={rowKey} emptyText={needle ? "نتیجه‌ای یافت نشد." : emptyText} />
      {filtered.length > pageSize && (
        <div className="pager">
          <span>{filtered.length.toLocaleString("fa-IR")} مورد</span>
          <span className="row">
            <button className="secondary" disabled={cur === 0} onClick={() => setPage(cur - 1)}>قبلی</button>
            <span>{(cur + 1).toLocaleString("fa-IR")} / {pages.toLocaleString("fa-IR")}</span>
            <button className="secondary" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>بعدی</button>
          </span>
        </div>
      )}
    </div>
  );
}

// ---------- notifications (واقعی: /api/alerts + /api/ops/monitoring) ----------
function NotificationsList() {
  const alerts = useApi<{ message?: string | null }[]>("/api/alerts?status=active&limit=20", []);
  const monitoring = useApi<{ status: string; checks: { name: string; status: string }[] }>("/api/ops/monitoring", []);
  if (alerts.error && monitoring.error) return <p className="hint">وضعیت اعلان‌ها نامشخص است ({alerts.error})</p>;
  if (alerts.loading || monitoring.loading) return <Spinner />;
  const items: string[] = [];
  for (const a of (alerts.data ?? []).slice(0, 5)) items.push(`هشدار: ${a.message ?? "فعال"}`);
  if (monitoring.data && monitoring.data.status !== "pass")
    for (const c of monitoring.data.checks.filter((c) => c.status !== "pass").slice(0, 5)) items.push(`پایش: ${c.name} (${c.status})`);
  return items.length ? <ul className="list">{items.map((t, i) => <li key={i}>{t}</li>)}</ul> : <Empty text="اعلان جدیدی نیست." />;
}

// ---------- shell ----------
type Tone = "ok" | "bad" | "warn" | "demo" | "";
function TopStatus() {
  const health = useApi<{ status: string }>("/health", []);
  const ai = useApi<{ mock_mode: boolean }>("/api/ai/status", []);
  let sys: { tone: Tone; text: string } = { tone: "", text: "نامشخص" };
  if (health.loading) sys = { tone: "", text: "در حال بررسی" };
  else if (health.data?.status === "ok") sys = { tone: "ok", text: "سیستم فعال" };
  else if (health.error) sys = { tone: "bad", text: "قطع" };
  let mode: { tone: Tone; text: string } = { tone: "", text: "حالت نامشخص" };
  if (ai.data) mode = ai.data.mock_mode ? { tone: "demo", text: "حالت آزمایشی (Mock)" } : { tone: "ok", text: "حالت واقعی" };
  return (
    <>
      <span className={`statuspill ${sys.tone}`} title="از /health"><i /><span className="lbl">{sys.text}</span></span>
      <span className={`statuspill ${mode.tone}`} title="از /api/ai/status (نیازمند کلید API)"><i /><span className="lbl">{mode.text}</span></span>
    </>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const route = useRoute();
  const { theme, setTheme } = useTheme();
  const { keySet } = useApiKey();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [bell, setBell] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setMobileOpen(false); setBell(false); }
      if (e.key === "/" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) { e.preventDefault(); document.getElementById("gsearch")?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (name: Parameters<typeof nav>[0]) => { setMobileOpen(false); nav(name); window.scrollTo({ top: 0 }); };
  const submitSearch = (e: FormEvent) => { e.preventDefault(); if (q.trim()) { nav("search", encodeURIComponent(q.trim())); } };

  return (
    <ToastProvider>
      <div className={`layout ${collapsed ? "collapsed" : ""}`}>
        <aside className={`sidebar ${mobileOpen ? "open" : ""}`} aria-label="منوی اصلی">
          <div className="brand">
            <span className="brand-logo"><Icon name="pulse" size={18} /></span>
            {!collapsed && <span className="brand-name">GlobalIntelligence</span>}
          </div>
          <nav>
            {NAV_GROUPS.map((g) => (
              <div className="nav-group" key={g.title}>
                <div className="nav-title">{g.title}</div>
                {g.items.map((m) => (
                  <button key={m.name} className={`navitem ${route.name === m.name ? "active" : ""}`} onClick={() => go(m.name)} aria-current={route.name === m.name ? "page" : undefined} title={m.label}>
                    <Icon name={m.icon} size={19} />
                    <span className="navlabel">{m.label}</span>
                    {m.status === "dev" && <span className="navbadge" title="در دست توسعه">توسعه</span>}
                    {m.status === "nc" && <span className="navbadge">نیازمند اتصال</span>}
                  </button>
                ))}
              </div>
            ))}
          </nav>
          <div className="sidebar-foot">
            <button className="navitem" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "باز کردن منو" : "جمع‌کردن منو"}>
              <Icon name="chevron" size={19} style={{ transform: collapsed ? "scaleX(-1)" : "none" }} />
              <span className="navlabel">جمع‌کردن منو</span>
            </button>
          </div>
        </aside>
        {mobileOpen && <div className="scrim" onClick={() => setMobileOpen(false)} />}

        <div className="main">
          <header className="topbar">
            <button className="iconbtn only-mobile" onClick={() => setMobileOpen(true)} aria-label="باز کردن منو"><Icon name="menu" /></button>
            <span className="topbar-title">GlobalIntelligence</span>
            <form className="searchbox" onSubmit={submitSearch} role="search">
              <Icon name="search" size={17} />
              <input id="gsearch" value={q} onChange={(e) => setQ(e.target.value)} placeholder="جست‌وجوی سراسری (کلید /)" aria-label="جست‌وجوی سراسری" />
            </form>
            <span className="grow" />
            <TopStatus />
            <span className={`statuspill ${keySet ? "ok" : "warn"}`} title="کلید API داخلی (فقط حافظهٔ همین زبانه)"><i /><span className="lbl">{keySet ? "کلید ثبت‌شده" : "کلید ثبت‌نشده"}</span></span>
            <div className="relwrap">
              <button className="iconbtn" onClick={() => setBell(!bell)} aria-label="اعلان‌ها" aria-expanded={bell}><Icon name="bell" /></button>
              {bell && <div className="popover"><h4>اعلان‌ها</h4><NotificationsList /></div>}
            </div>
            <button className="iconbtn" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="تغییر تم" title={theme === "dark" ? "تم روشن" : "تم تیره"}><Icon name={theme === "dark" ? "sun" : "moon"} /></button>
            <button className="iconbtn" onClick={() => go("settings")} aria-label="تنظیمات"><Icon name="settings" /></button>
          </header>
          <main className="content" key={route.name}>{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}

export function Section({ title, error, loading, children, actions }: { title: string; error: string | null; loading?: boolean; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="panel" aria-label={title}>
      <div className="panel-head">
        <h2>{title}</h2>
        {actions}
      </div>
      {loading ? <Spinner /> : error ? <Err message={error} /> : children}
    </section>
  );
}

export function Spinner() {
  return (
    <div role="status" aria-label="در حال بارگذاری">
      <div className="skeleton" style={{ width: "70%" }} />
      <div className="skeleton" style={{ width: "92%" }} />
      <div className="skeleton" style={{ width: "55%" }} />
    </div>
  );
}

export function Empty({ text = "داده‌ای موجود نیست." }: { text?: string }) {
  return <div className="empty">{text}</div>;
}

export function Err({ message }: { message: string }) {
  const needsKey = message.includes("کلید API");
  return (
    <div className="errbox" role="alert">
      <p>{needsKey ? "برای مشاهدهٔ این بخش، کلید API داخلی را در تنظیمات وارد کنید. (کلید فقط در حافظهٔ همین زبانه می‌ماند.)" : message}</p>
      {needsKey && <button onClick={() => nav("settings")}>رفتن به تنظیمات</button>}
    </div>
  );
}

export function MockTag({ isMock }: { isMock: boolean | null | undefined }) {
  if (!isMock) return null;
  return <Badge tone="demo">نمونه (Mock)</Badge>;
}

export function apiErrorText(e: unknown): string {
  return e instanceof ApiError ? e.message : faError(e);
}
