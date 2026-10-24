/** غربالگری و صف پردازش — بازبینی انسانی، نتایج غربالگری، وظایف پردازش و وضعیت Kev/Laya.
 *
 * همه‌چیز از API واقعی خوانده می‌شود؛ وضعیت «ذخیره‌شده»، «آمادگی اجرا»،
 * «نتیجه غربالگری» و «تکمیل پردازش» برچسب‌های جدا دارند. تأیید بازبینی فقط
 * human_review را کنار نتیجه ماشینی اضافه می‌کند و آن را بازنویسی نمی‌کند.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, faError } from "../api";
import { nav } from "../router";
import { faDateTime } from "../theme";
import { Badge, Empty, Err, PageHeader, Section, Spinner, Table, useApiKey, useToast } from "../ui";

type Tab = "review" | "outcomes" | "dispatch" | "runtime";

const TABS: { id: Tab; label: string }[] = [
  { id: "review", label: "صف بازبینی" },
  { id: "outcomes", label: "نتایج غربالگری" },
  { id: "dispatch", label: "وظایف پردازش" },
  { id: "runtime", label: "وضعیت Kev و Laya" },
];

type Paged<T> = { items: T[]; page: number; page_size: number; has_more: boolean };

type ReviewItem = {
  article_id: string;
  title: string | null;
  article_url: string | null;
  source_name: string | null;
  priority: string | null;
  priority_source: string | null;
  classification_status: string | null;
  classification_error: string | null;
  retrieved_at: string | null;
  screening: Record<string, unknown> | null;
  domains: string[] | null;
  domain_state: string | null;
  screening_status: string;
  review_required: boolean;
  review_reasons: string[];
  review_acknowledged: boolean;
  acknowledged_at: string | null;
};

type DispatchJob = {
  dispatch_id: string;
  article_id: string;
  title: string | null;
  article_url: string | null;
  priority: string | null;
  task: string;
  task_version: string;
  status: string;
  attempts: number;
  last_error: string | null;
  created_at: string | null;
  updated_at: string | null;
  next_retry_at: string | null;
  can_retry: boolean;
  screening_status: string;
  review_required: boolean;
  review_reasons: string[];
  review_acknowledged: boolean;
};

type RuntimeStatus = {
  enabled: boolean;
  state: string;
  pid: number | null;
  last_error: string | null;
  load_time_ms: number | null;
  last_inference_ms: number | null;
};

const SCREENING_LABEL: Record<string, string> = {
  missing: "بدون نتیجه ذخیره‌شده",
  skipped: "رد شده با گیت اولویت (بدون AI)",
  pending: "نامشخص / در انتظار",
  failed: "ناموفق",
  relevant: "مرتبط",
  not_relevant: "نامرتبط",
};

const DOMAIN_STATE_LABEL: Record<string, string> = {
  assigned: "دارای موتور متصل",
  pending: "بدون موتور مقاله‌محور",
  unassigned: "بدون سیگنال دامنه",
};

const DISPATCH_LABEL: Record<string, { text: string; tone: "ok" | "warn" | "bad" | "info" }> = {
  pending: { text: "در صف", tone: "info" },
  running: { text: "در حال اجرا", tone: "info" },
  completed: { text: "تکمیل‌شده (اجرا اثبات شده)", tone: "ok" },
  retryable: { text: "قابل تلاش مجدد", tone: "warn" },
  terminal: { text: "خطای پایانی", tone: "bad" },
};

const REASON_LABEL: Record<string, string> = {
  CLASSIFICATION_PENDING: "طبقه‌بندی ناتمام",
  CLASSIFICATION_FAILED: "طبقه‌بندی ناموفق",
  SCREENING_PENDING: "نتیجه غربالگری نامشخص",
  P0_P1_SAFEGUARD: "محافظ P0/P1 فعال شد",
  PRIORITY_REVIEW: "بازبینی اولویت (P0/P1)",
  DISAGREEMENT: "اختلاف دو مدل",
  LOW_MARGIN: "حاشیه اطمینان کم",
  KEV_LOW_MARGIN: "حاشیه اطمینان کم (Kev)",
  LAYA_LOW_MARGIN: "حاشیه اطمینان کم (Laya)",
  UNSUPPORTED_LANGUAGE: "زبان پشتیبانی‌نشده",
  EMPTY_INPUT: "متن خالی",
  AI_ABSTAINED: "پاسخ AI قابل استخراج نبود",
  AI_UNAVAILABLE: "AI Gateway در دسترس نبود",
  KEV_INPUT_TOO_LONG: "ورودی بلندتر از حد Kev",
  LAYA_INPUT_TOO_LONG: "ورودی بلندتر از حد Laya",
  KEV_TRUNCATED: "ورودی Kev بریده شد",
  LAYA_TRUNCATED: "ورودی Laya بریده شد",
  KEV_TOO_LONG: "ورودی Kev بیش از حد مجاز",
  LAYA_TOO_LONG: "ورودی Laya بیش از حد مجاز",
  KEV_UNAVAILABLE: "Kev در دسترس نبود",
  LAYA_UNAVAILABLE: "Laya در دسترس نبود",
  KEV_ERROR: "خطای Kev",
  LAYA_ERROR: "خطای Laya",
  KEV_NO_RESULT: "بدون پاسخ از Kev",
  LAYA_NO_RESULT: "بدون پاسخ از Laya",
  KEV_INVALID_OUTPUT: "پاسخ نامعتبر Kev",
  LAYA_INVALID_OUTPUT: "پاسخ نامعتبر Laya",
};

function reasonLabel(code: string): string {
  if (REASON_LABEL[code]) return REASON_LABEL[code];
  if (code.startsWith("AI_ERROR:")) return `خطای AI Gateway (${code.slice(9)})`;
  if (code.startsWith("PAIR_INVALID:")) return `پاسخ نامعتبر جفت مدل (${code.slice(13)})`;
  if (code.startsWith("SCREENING_EXCEPTION:")) return `استثنای غربالگری (${code.slice(20)})`;
  return code;
}

function safeUrl(url: string | null): string | null {
  return url && /^https?:\/\//i.test(url) ? url : null;
}

// ---------- polling hook: no overlap, cleanup on unmount ----------
function useLive<T>(path: string, deps: unknown[], pollMs = 0) {
  const { version } = useApiKey();
  const [state, setState] = useState<{
    data: T | null; error: string | null; loading: boolean; loadedAt: number | null;
  }>({ data: null, error: null, loading: true, loadedAt: null });
  const pathRef = useRef(path);
  pathRef.current = path;
  const inFlight = useRef<string | null>(null);

  const load = useCallback(async () => {
    const requested = pathRef.current;
    if (inFlight.current === requested) return; // same poll still running
    inFlight.current = requested;
    setState((s) => ({ ...s, loading: true }));
    try {
      const data = await api.get<T>(requested);
      if (pathRef.current === requested)
        setState({ data, error: null, loading: false, loadedAt: Date.now() });
    } catch (e) {
      if (pathRef.current === requested)
        setState((s) => ({ ...s, error: faError(e), loading: false }));
    } finally {
      if (inFlight.current === requested) inFlight.current = null;
    }
  }, []);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, version, ...deps]);

  useEffect(() => {
    if (!pollMs) return;
    const id = setInterval(() => {
      if (!document.hidden) void load();
    }, pollMs);
    return () => clearInterval(id);
  }, [load, pollMs]);

  return { ...state, reload: load };
}

function ActionButton({
  label, path, onDone,
}: { label: string; path: string; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const run = async () => {
    setBusy(true);
    try {
      await api.post(path, {});
      toast("انجام شد.", "ok");
      onDone();
    } catch (e) {
      toast(faError(e), "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <button className="secondary" disabled={busy} onClick={run}>
      {busy ? "…" : label}
    </button>
  );
}

function Pager({
  page, hasMore, loading, onPage,
}: { page: number; hasMore: boolean; loading: boolean; onPage: (p: number) => void }) {
  return (
    <div className="pager">
      <button className="secondary" disabled={page <= 1 || loading} onClick={() => onPage(page - 1)}>
        قبلی
      </button>
      <span>صفحه {page.toLocaleString("fa-IR")}</span>
      <button className="secondary" disabled={!hasMore || loading} onClick={() => onPage(page + 1)}>
        بعدی
      </button>
    </div>
  );
}

function Reasons({ codes }: { codes: string[] }) {
  if (!codes.length) return <span className="hint">—</span>;
  return (
    <span style={{ display: "inline-flex", gap: 4, flexWrap: "wrap" }}>
      {codes.map((c) => (
        <span key={c} className="badge badge-warn" title={c}>{reasonLabel(c)}</span>
      ))}
    </span>
  );
}

function Freshness({ at, loading }: { at: number | null; loading: boolean }) {
  return (
    <p className="hint" role="status">
      {at ? `آخرین به‌روزرسانی: ${new Date(at).toLocaleTimeString("fa-IR")}` : "هنوز داده‌ای دریافت نشده است."}
      {loading ? " — در حال به‌روزرسانی…" : ""}
    </p>
  );
}

// ---------- tab 1: review queue ----------
function ReviewTab() {
  const [page, setPage] = useState(1);
  const [onlyP0P1, setOnlyP0P1] = useState(false);
  const [onlyOpen, setOnlyOpen] = useState(true);
  const path = `/api/screening/queue?review_required=true&page=${page}&page_size=20`
    + (onlyP0P1 ? "&p0_p1=true" : "")
    + (onlyOpen ? "&acknowledged=false" : "");
  const live = useLive<Paged<ReviewItem>>(path, [page, onlyP0P1, onlyOpen], 15000);

  return (
    <Section title="صف بازبینی انسانی" error={live.error}>
      <p className="hint">
        این صف فقط از پرچم‌ها و کدهای ذخیره‌شده‌ی غربالگری ساخته می‌شود. اولویت P0/P1 به‌تنهایی
        «نیازمند بازبینی» نیست؛ فقط وقتی سیاست ذخیره‌شده آن را علامت زده باشد.
      </p>
      <div className="filters">
        <label>
          <input type="checkbox" checked={onlyP0P1} onChange={(e) => { setOnlyP0P1(e.target.checked); setPage(1); }} />{" "}
          فقط P0/P1
        </label>
        <label>
          <input type="checkbox" checked={onlyOpen} onChange={(e) => { setOnlyOpen(e.target.checked); setPage(1); }} />{" "}
          فقط تأییدنشده
        </label>
        <button className="secondary" onClick={() => void live.reload()} disabled={live.loading}>به‌روزرسانی</button>
      </div>
      <Freshness at={live.loadedAt} loading={live.loading} />
      {live.data ? (
        <>
          <Table<ReviewItem>
            rows={live.data.items}
            rowKey={(r) => r.article_id}
            emptyText="موردی در صف بازبینی نیست."
            columns={[
              { key: "title", label: "مقاله", render: (r) => (
                <button className="linkbtn" onClick={() => nav("news", `article-${r.article_id}`)}>
                  {r.title ?? "بدون عنوان"}
                </button>
              ) },
              { key: "priority", label: "اولویت", render: (r) => r.priority ?? "—" },
              { key: "screening_status", label: "نتیجه غربالگری", render: (r) => SCREENING_LABEL[r.screening_status] ?? r.screening_status },
              { key: "domains", label: "دامنه‌ها", render: (r) => (
                r.domains?.length
                  ? <span title={r.domains.join("، ")}>{r.domains.join("، ")}</span>
                  : <span className="hint">—</span>
              ) },
              { key: "review_reasons", label: "دلیل بازبینی", render: (r) => <Reasons codes={r.review_reasons} /> },
              { key: "review_acknowledged", label: "تأیید", render: (r) => (
                r.review_acknowledged
                  ? <Badge tone="ok">تأیید شده</Badge>
                  : <Badge tone="warn">باز</Badge>
              ) },
              { key: "retrieved_at", label: "دریافت", render: (r) => faDateTime(r.retrieved_at) },
              { key: "actions", label: "اقدام", render: (r) => (
                <span style={{ display: "inline-flex", gap: 6 }}>
                  <button className="secondary" onClick={() => nav("news", `article-${r.article_id}`)}>
                    مشاهده مقاله
                  </button>
                  {!r.review_acknowledged && (
                    <ActionButton
                      label="تأیید بازبینی"
                      path={`/api/screening/review/${r.article_id}/ack`}
                      onDone={() => void live.reload()}
                    />
                  )}
                </span>
              ) },
            ]}
          />
          <Pager page={page} hasMore={live.data.has_more} loading={live.loading} onPage={setPage} />
          <p className="hint">
            تأیید فقط یک نشانه‌ی عملیاتی است؛ نتیجه‌ی ماشینی را تغییر نمی‌دهد و «تصمیم انسانی» ثبت نمی‌کند.
          </p>
        </>
      ) : live.loading ? <Spinner /> : <Empty text="موردی در صف بازبینی نیست." />}
    </Section>
  );
}

// ---------- tab 2: screening outcomes ----------
function OutcomesTab() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [onlyP0P1, setOnlyP0P1] = useState(false);
  const path = `/api/screening/queue?review_required=false&page=${page}&page_size=20`
    + (status ? `&screening=${status}` : "")
    + (onlyP0P1 ? "&p0_p1=true" : "");
  const live = useLive<Paged<ReviewItem>>(path, [page, status, onlyP0P1], 15000);

  return (
    <Section title="نتایج ذخیره‌شده‌ی غربالگری" error={live.error}>
      <p className="hint">
        نتیجه‌ی غربالگری مشورتی است و تصمیم طبقه‌بندی را بازنویسی نمی‌کند؛ ردیف‌های نیازمند بازبینی
        در تب «صف بازبینی» هستند.
      </p>
      <div className="filters">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="وضعیت غربالگری">
          <option value="">همه وضعیت‌ها</option>
          <option value="relevant">مرتبط</option>
          <option value="not_relevant">نامرتبط</option>
          <option value="skipped">رد شده با گیت اولویت</option>
          <option value="missing">بدون نتیجه ذخیره‌شده</option>
        </select>
        <label>
          <input type="checkbox" checked={onlyP0P1} onChange={(e) => { setOnlyP0P1(e.target.checked); setPage(1); }} />{" "}
          فقط P0/P1
        </label>
        <button className="secondary" onClick={() => void live.reload()} disabled={live.loading}>به‌روزرسانی</button>
      </div>
      <Freshness at={live.loadedAt} loading={live.loading} />
      {live.data ? (
        <>
          <Table<ReviewItem>
            rows={live.data.items}
            rowKey={(r) => r.article_id}
            emptyText="نتیجه‌ای با این فیلتر ذخیره نشده است."
            columns={[
              { key: "title", label: "مقاله", render: (r) => (
                <button className="linkbtn" onClick={() => nav("news", `article-${r.article_id}`)}>
                  {r.title ?? "بدون عنوان"}
                </button>
              ) },
              { key: "priority", label: "اولویت", render: (r) => r.priority ?? "—" },
              { key: "screening_status", label: "نتیجه", render: (r) => SCREENING_LABEL[r.screening_status] ?? r.screening_status },
              { key: "route", label: "مسیر", render: (r) => String(r.screening?.route ?? "—") },
              { key: "domains", label: "دامنه‌ها", render: (r) => (
                r.domains?.length
                  ? <span title={r.domains.join("، ")}>
                      <Badge tone={r.domain_state === "assigned" ? "ok" : "info"}>
                        {r.domains.join("، ")}
                      </Badge>
                    </span>
                  : <span className="hint" title={DOMAIN_STATE_LABEL.unassigned}>—</span>
              ) },
              { key: "reason_codes", label: "کدهای دلیل", render: (r) => (
                <Reasons codes={Array.isArray(r.screening?.reason_codes) ? r.screening.reason_codes as string[] : []} />
              ) },
              { key: "retrieved_at", label: "دریافت", render: (r) => faDateTime(r.retrieved_at) },
              { key: "article_url", label: "منبع", render: (r) => {
                const url = safeUrl(r.article_url);
                return url ? <a href={url} target="_blank" rel="noreferrer">منبع اصلی</a> : "—";
              } },
            ]}
          />
          <Pager page={page} hasMore={live.data.has_more} loading={live.loading} onPage={setPage} />
        </>
      ) : live.loading ? <Spinner /> : <Empty text="نتیجه‌ای با این فیلتر ذخیره نشده است." />}
    </Section>
  );
}

// ---------- tab 3: dispatch jobs ----------
function DispatchTab() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [task, setTask] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [onlyP0P1, setOnlyP0P1] = useState(false);
  const path = `/api/dispatch/jobs?page=${page}&page_size=20`
    + (status ? `&status=${status}` : "")
    + (task ? `&task=${task}` : "")
    + (reviewOnly ? "&review_required=true" : "")
    + (onlyP0P1 ? "&p0_p1=true" : "");
  const live = useLive<Paged<DispatchJob>>(path, [page, status, task, reviewOnly, onlyP0P1], 10000);

  return (
    <Section title="وظایف پردازش (article_dispatches)" error={live.error}>
      <p className="hint">
        وجود یک ردیف یعنی کار «صف شده» است؛ فقط وضعیت «تکمیل‌شده» یعنی همان وظیفه اجرا و تأیید شده است،
        نه اینکه تحلیل نهایی کامل شده باشد. «خطای پایانی» هرگز موفقیت نیست.
      </p>
      <div className="filters">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="وضعیت وظیفه">
          <option value="">همه وضعیت‌ها</option>
          <option value="pending">در صف</option>
          <option value="running">در حال اجرا</option>
          <option value="completed">تکمیل‌شده</option>
          <option value="retryable">قابل تلاش مجدد</option>
          <option value="terminal">خطای پایانی</option>
        </select>
        <select value={task} onChange={(e) => { setTask(e.target.value); setPage(1); }} aria-label="نوع وظیفه">
          <option value="">همه وظایف</option>
          <option value="classification">classification</option>
          <option value="screening">screening</option>
          <option value="domain_routing">domain_routing</option>
          <option value="event_extraction">event_extraction</option>
          <option value="claim_extraction">claim_extraction</option>
          <option value="graph_extraction">graph_extraction</option>
          <option value="evidence_collection">evidence_collection</option>
          <option value="domain_geopolitics">domain_geopolitics</option>
          <option value="domain_society">domain_society</option>
          <option value="claim_independence">claim_independence</option>
        </select>
        <label>
          <input type="checkbox" checked={reviewOnly} onChange={(e) => { setReviewOnly(e.target.checked); setPage(1); }} />{" "}
          نیازمند بازبینی
        </label>
        <label>
          <input type="checkbox" checked={onlyP0P1} onChange={(e) => { setOnlyP0P1(e.target.checked); setPage(1); }} />{" "}
          فقط P0/P1
        </label>
        <button className="secondary" onClick={() => void live.reload()} disabled={live.loading}>به‌روزرسانی</button>
      </div>
      <Freshness at={live.loadedAt} loading={live.loading} />
      {live.data ? (
        <>
          <Table<DispatchJob>
            rows={live.data.items}
            rowKey={(r) => r.dispatch_id}
            emptyText="وظیفه‌ای با این فیلتر وجود ندارد."
            columns={[
              { key: "title", label: "مقاله", render: (r) => (
                <button className="linkbtn" onClick={() => nav("news", `article-${r.article_id}`)}>
                  {r.title ?? r.article_id.slice(0, 8)}
                </button>
              ) },
              { key: "priority", label: "اولویت", render: (r) => r.priority ?? "—" },
              { key: "task", label: "وظیفه", render: (r) => `${r.task}@v${r.task_version}` },
              { key: "status", label: "وضعیت", render: (r) => {
                const s = DISPATCH_LABEL[r.status] ?? { text: r.status, tone: "info" as const };
                return <Badge tone={s.tone}>{s.text}</Badge>;
              } },
              { key: "attempts", label: "تلاش", render: (r) => r.attempts.toLocaleString("fa-IR"), numeric: true },
              { key: "last_error", label: "آخرین خطا", render: (r) => r.last_error ? <span title={r.last_error}>{r.last_error.slice(0, 80)}</span> : "—" },
              { key: "next_retry_at", label: "تلاش بعدی", render: (r) => faDateTime(r.next_retry_at) },
              { key: "review", label: "بازبینی", render: (r) => (
                r.review_required
                  ? <span title={r.review_reasons.map(reasonLabel).join("، ")}>
                      <Badge tone={r.review_acknowledged ? "ok" : "warn"}>
                        {r.review_acknowledged ? "تأییدشده" : "نیازمند"}
                      </Badge>
                    </span>
                  : <span className="hint">—</span>
              ) },
              { key: "updated_at", label: "آخرین تغییر", render: (r) => faDateTime(r.updated_at) },
              { key: "actions", label: "اقدام", render: (r) => (
                <span style={{ display: "inline-flex", gap: 6 }}>
                  <button className="secondary" onClick={() => nav("news", `article-${r.article_id}`)}>
                    مشاهده مقاله
                  </button>
                  {r.can_retry && (
                    <ActionButton
                      label="تلاش مجدد"
                      path={`/api/dispatch/${r.dispatch_id}/retry`}
                      onDone={() => void live.reload()}
                    />
                  )}
                </span>
              ) },
            ]}
          />
          <Pager page={page} hasMore={live.data.has_more} loading={live.loading} onPage={setPage} />
          <p className="hint">
            «تلاش مجدد» فقط ردیف قابل‌تلاش را دوباره در دسترس مصرف‌کننده می‌گذارد؛ تعداد تلاش‌ها را
            بازنشانی نمی‌کند و کار تکمیل‌شده را دوباره اجرا نمی‌کند.
          </p>
        </>
      ) : live.loading ? <Spinner /> : <Empty text="وظیفه‌ای با این فیلتر وجود ندارد." />}
    </Section>
  );
}

// ---------- tab 4: runtime readiness ----------
function RuntimeTab() {
  const status = useLive<Record<string, RuntimeStatus>>("/api/local-runtimes/status", [], 5000);
  const app = useLive<Record<string, string>>("/api/settings/app", [], 15000);

  const rows = (["kev", "laya"] as const).map((name) => {
    const st = status.data?.[name];
    const saved = app.data?.[`${name}_local_screening_enabled`] === "true";
    return {
      name: name === "kev" ? "Kev" : "Laya",
      saved,
      enabled: st?.enabled ?? false,
      state: st?.state ?? "UNKNOWN",
      pid: st?.pid ?? null,
      error: st?.last_error ?? null,
      load_ms: st?.load_time_ms ?? null,
      infer_ms: st?.last_inference_ms ?? null,
    };
  });

  const ready = (state: string) => state === "READY" || state === "BUSY";

  return (
    <Section title="آمادگی اجرای محلی" error={status.error ?? app.error}>
      <p className="hint">
        «تنظیم ذخیره‌شده» با «آمادگی واقعی» یکی نیست: فعال بودن یعنی قابل زمان‌بندی؛ بارگذاری مدل
        فقط هنگام نیاز رخ می‌دهد. این نما فقط می‌خواند؛ تغییر از «تنظیمات ← اجرای محلی» انجام می‌شود.
      </p>
      <Freshness at={status.loadedAt} loading={status.loading} />
      {status.data ? (
        <Table
          rows={rows}
          rowKey={(r) => r.name}
          emptyText="وضعیت اجرای محلی در دسترس نیست."
          columns={[
            { key: "name", label: "مدل" },
            { key: "saved", label: "تنظیم ذخیره‌شده", render: (r) => (
              r.saved ? <Badge tone="info">فعال</Badge> : <Badge tone="info">غیرفعال</Badge>
            ) },
            { key: "enabled", label: "فعال در سوپروایزر", render: (r) => (r.enabled ? "بله" : "خیر") },
            { key: "state", label: "وضعیت واقعی", render: (r) => (
              <Badge tone={ready(r.state) ? "ok" : r.state === "ERROR" ? "bad" : "warn"}>{r.state}</Badge>
            ) },
            { key: "pid", label: "PID", render: (r) => r.pid ?? "—", numeric: true },
            { key: "load_ms", label: "زمان بارگذاری", render: (r) => r.load_ms ? `${Math.round(r.load_ms)} ms` : "—" },
            { key: "infer_ms", label: "آخرین استنتاج", render: (r) => r.infer_ms ? `${Math.round(r.infer_ms)} ms` : "—" },
            { key: "error", label: "خطا", render: (r) => r.error ?? "—" },
          ]}
        />
      ) : status.loading ? <Spinner /> : <Empty text="وضعیت اجرای محلی در دسترس نیست." />}
      {status.data && !status.data.kev && !status.data.laya && (
        <Err message="پاسخ وضعیت اجرای محلی خالی است." />
      )}
    </Section>
  );
}

export default function ScreeningOps() {
  const [tab, setTab] = useState<Tab>("review");
  return (
    <div>
      <PageHeader
        title="غربالگری و صف پردازش"
        subtitle="بازبینی نتایج غربالگری، صف وظایف پردازش و آمادگی Kev/Laya — مستقیم از بک‌اند."
      />
      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id}
            className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </div>
      {tab === "review" && <ReviewTab />}
      {tab === "outcomes" && <OutcomesTab />}
      {tab === "dispatch" && <DispatchTab />}
      {tab === "runtime" && <RuntimeTab />}
    </div>
  );
}
