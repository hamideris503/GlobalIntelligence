/** Sources: list/search/filter/sort + create/edit/enable + trial ingest + health. */
import { useMemo, useState } from "react";
import { api, getApiBase, getApiKey } from "../api";
import type { Source } from "../types";
import { Badge, Empty, Modal, Field, RunButton, Section, Table, useApi } from "../ui";

const TYPES = ["rss", "api", "dataset", "official", "scrape", "manual", "other"];

function SourceForm({
  initial,
  onDone,
  onCancel,
}: {
  initial?: Source;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    name: initial?.name ?? "",
    domain: initial?.domain ?? "",
    country: initial?.country ?? "",
    type: initial?.type ?? "rss",
    language: initial?.language ?? "",
    collection_method: initial?.collection_method ?? "",
    feed_url: (initial as unknown as Record<string, string>)?.feed_url ?? "",
    active: initial?.active ?? true,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) {
      setError("نام منبع لازم است.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        name: form.name.trim(),
        type: form.type,
        active: form.active,
      };
      for (const k of ["domain", "country", "language", "collection_method", "feed_url"]) {
        const v = (form as unknown as Record<string, string>)[k].trim();
        if (v) body[k] = k === "country" ? v.toUpperCase().slice(0, 2) : v;
      }
      if (initial) {
        await api.patch(`/api/sources/${initial.id}`, body);
      } else {
        await api.post(`/api/sources`, body);
      }
      onDone();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "خطا در ذخیره.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <Field label="نام منبع">
        <input value={form.name} onChange={(e) => set("name", e.target.value)} disabled={!!initial} />
      </Field>
      <Field label="دامنه">
        <input value={form.domain} onChange={(e) => set("domain", e.target.value)} placeholder="example.com" dir="ltr" />
      </Field>
      <Field label="نوع منبع">
        <select value={form.type} onChange={(e) => set("type", e.target.value)}>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </Field>
      <Field label="کشور (دو حرفی)">
        <input value={form.country} onChange={(e) => set("country", e.target.value)} placeholder="IR" />
      </Field>
      <Field label="زبان">
        <input value={form.language} onChange={(e) => set("language", e.target.value)} placeholder="fa" />
      </Field>
      <Field label="روش دریافت">
        <input
          value={form.collection_method}
          onChange={(e) => set("collection_method", e.target.value)}
          placeholder="rss"
        />
      </Field>
      <Field label="نشانی فید (RSS/Atom)" hint="فقط در صورت معتبر بودن؛ دکمهٔ «بررسی مجدد» آن را می‌آزماید.">
        <input
          value={form.feed_url}
          onChange={(e) => set("feed_url", e.target.value)}
          placeholder="https://example.com/feed"
          dir="ltr"
        />
      </Field>
      <Field label="فعال">
        <input
          type="checkbox"
          checked={form.active}
          onChange={(e) => set("active", e.target.checked)}
        />
      </Field>
      {error && <p className="err-text">{error}</p>}
      <div className="row">
        <button onClick={submit} disabled={busy}>{busy ? "…" : "ذخیره"}</button>
        <button onClick={onCancel}>لغو</button>
      </div>
      <p className="hint">حذف منبع در API پشتیبانی نمی‌شود؛ برای کنار گذاشتن، غیرفعال کنید.</p>
    </div>
  );
}

export default function Sources() {
  const [q, setQ] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [modal, setModal] = useState<"create" | Source | null>(null);
  const [trial, setTrial] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const list = useApi<Source[]>("/api/sources?limit=500", [tick]);

  const rows = useMemo(() => {
    const items = list.data ?? [];
    const needle = q.trim().toLowerCase();
    return items.filter((s) => {
      if (typeFilter && s.type !== typeFilter) return false;
      if (activeFilter === "on" && !s.active) return false;
      if (activeFilter === "off" && s.active) return false;
      if (statusFilter && (s.validation_status || "") !== statusFilter) return false;
      if (needle && !`${s.name} ${s.domain ?? ""} ${s.category ?? ""}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [list.data, q, typeFilter, activeFilter, statusFilter]);

  const recheck = async (s: Source) => {
    setTrial(`در حال بررسی مجدد ${s.name}…`);
    try {
      const r = await api.post<Source>(`/api/sources/${s.id}/recheck`, undefined, 120000);
      setTrial(`${r.name}: ${r.validation_status}`);
      setTick((t) => t + 1);
    } catch (e: unknown) {
      setTrial(e instanceof Error ? e.message : "خطا");
    }
  };

  const trialFetch = async (s: Source) => {
    setTrial(`در حال دریافت آزمایشی از ${s.name}…`);
    try {
      const r = await api.post<{ fetched: number; stored: number; source_name: string }>(
        `/api/ingest`,
        { source_name: s.name, limit: 5 },
        120000,
      );
      setTrial(`نتیجهٔ ${r.source_name}: دریافت ${r.fetched}، ذخیره ${r.stored}.`);
    } catch (e: unknown) {
      setTrial(e instanceof Error ? e.message : "خطا");
    }
  };

  const toggleActive = async (s: Source) => {
    try {
      await api.patch(`/api/sources/${s.id}`, { active: !s.active });
      setTick((t) => t + 1);
    } catch {
      /* error surfaces on refetch */
    }
  };

  const downloadExport = async (format: "csv" | "json") => {
    setTrial(`در حال ساخت خروجی ${format}…`);
    try {
      const res = await fetch(
        `${getApiBase()}/api/sources/export/all?format=${format}`,
        { headers: { "X-API-Key": getApiKey() } },
      );
      if (!res.ok) throw new Error(`خطا: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sources.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      setTrial(`خروجی ${format} دانلود شد.`);
    } catch (e: unknown) {
      setTrial(e instanceof Error ? e.message : "خطا");
    }
  };

  return (
    <div>
      <div className="page-head">
        <h1>منابع اطلاعاتی</h1>
        <div className="row">
          <button onClick={() => setModal("create")}>افزودن منبع</button>
          <button className="secondary" onClick={() => downloadExport("csv")}>خروجی CSV</button>
          <button className="secondary" onClick={() => downloadExport("json")}>خروجی JSON</button>
        </div>
      </div>
      <div className="filters">
        <input placeholder="جست‌وجو…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="جست‌وجوی منابع" />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="فیلتر نوع">
          <option value="">همهٔ نوع‌ها</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} aria-label="فیلتر وضعیت">
          <option value="">فعال/غیرفعال</option>
          <option value="on">فقط فعال</option>
          <option value="off">فقط غیرفعال</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="فیلتر اعتبارسنجی">
          <option value="">همهٔ وضعیت‌ها</option>
          {["PENDING_VALIDATION", "VERIFIED", "ACTIVE", "LIMITED_ACCESS", "AUTH_REQUIRED", "PAID", "TEMPORARILY_UNAVAILABLE", "INVALID_URL", "NEEDS_REVIEW", "DISABLED"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>
      {trial && <p className="hint">{trial}</p>}
      {list.error ? (
        <Section title="منابع" error={list.error} loading={false}><span /></Section>
      ) : list.loading ? (
        <p className="hint">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <Empty text="منبعی یافت نشد." />
      ) : (
        <Table
          columns={[
            { key: "name", label: "نام" },
            { key: "homepage_url", label: "نشانی", render: (r) => (
              r.homepage_url
                ? <a href={String(r.homepage_url)} target="_blank" rel="noreferrer">باز کردن</a>
                : "—"
            ) },
            { key: "category", label: "دسته", render: (r) => String(r.category ?? "—") },
            {
              key: "validation_status", label: "اعتبارسنجی",
              render: (r) => {
                const v = String(r.validation_status ?? "PENDING_VALIDATION");
                const tone = v === "VERIFIED" || v === "ACTIVE" ? "ok"
                  : v === "PENDING_VALIDATION" ? "info" : "warn";
                return <Badge tone={tone as "ok" | "warn" | "info"}>{v}</Badge>;
              },
            },
            { key: "domain", label: "دامنه", render: (r) => String(r.domain ?? "—") },
            { key: "type", label: "نوع" },
            {
              key: "active", label: "وضعیت",
              render: (r) => <Badge tone={r.active ? "ok" : "warn"}>{r.active ? "فعال" : "غیرفعال"}</Badge>,
            },
            { key: "last_error", label: "آخرین خطا", render: (r) => String(r.last_error ?? "—").slice(0, 60) },
            {
              key: "actions", label: "اقدامات", render: (r) => (
                <span className="row">
                  <button className="linkbtn" onClick={() => setModal(r as unknown as Source)}>ویرایش</button>
                  <button className="linkbtn" onClick={() => toggleActive(r as unknown as Source)}>
                    {(r as unknown as Source).active ? "غیرفعال" : "فعال"}
                  </button>
                  <button className="linkbtn" onClick={() => recheck(r as unknown as Source)}>بررسی مجدد</button>
                  <button className="linkbtn" onClick={() => trialFetch(r as unknown as Source)}>دریافت آزمایشی</button>
                </span>
              ),
            },
          ]}
          rows={rows as unknown as Record<string, unknown>[]}
          rowKey={(r) => String(r.id)}
        />
      )}
      <p className="hint">آخرین موفقیت‌ها در ستون خطا/وضعیت هر منبع دیده می‌شود. تاریخچهٔ اجرای کامل در صفحهٔ «کارهای خودکار» است.</p>
      {modal && (
        <Modal title={modal === "create" ? "افزودن منبع" : "ویرایش منبع"} onClose={() => setModal(null)}>
          <SourceForm
            initial={modal === "create" ? undefined : modal}
            onDone={() => {
              setModal(null);
              setTick((t) => t + 1);
            }}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}
      <Section title="دریافت دستی همه" error={null}>
        <RunButton label="اجرای دریافت همهٔ منابع" path="/api/ingest/all?limit=20" />
      </Section>
    </div>
  );
}
