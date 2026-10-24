/** News & events: articles list + filters + detail, events + claims/evidence. */
import { useMemo, useState } from "react";
import { nav } from "../router";
import { faDateTime, importanceLabel } from "../theme";
import type { ArticleDetail, ArticleItem, ClaimItem, EventItem } from "../types";
import { Empty, MockTag, RunButton, Section, Table, useApi } from "../ui";

function useFilter<T>(items: T[] | null, fn: (t: T, q: string) => boolean) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    if (!items) return null;
    const needle = q.trim();
    if (!needle) return items;
    return items.filter((t) => fn(t, needle));
  }, [items, fn, q]);
  return { q, setQ, filtered };
}

function ArticleDetailView({ id }: { id: string }) {
  const art = useApi<ArticleDetail>(`/api/classify/articles/${id}`, []);
  const claims = useApi<ClaimItem[]>(
    art.data?.event_id ? `/api/claims?event_id=${art.data.event_id}&limit=50` : null,
    [art.data?.event_id],
  );
  return (
    <div>
      <button onClick={() => nav("news")}>→ بازگشت به فهرست</button>
      <Section title="جزئیات خبر" error={art.error} loading={art.loading}>
        {art.data && (
          <div className="detail">
            <h2>{art.data.title ?? "—"}</h2>
            <p>
              <MockTag isMock={art.data.is_mock} />{" "}
              {art.data.provider && <span className="hint">({art.data.provider})</span>}
            </p>
            <p>{art.data.summary ?? "خلاصه‌ای ثبت نشده است."}</p>
            <dl className="kv">
              <dt>منبع</dt>
              <dd>{art.data.source_name ?? "—"}</dd>
              <dt>پیوند اصلی</dt>
              <dd>
                {art.data.url ? (
                  <a href={art.data.url} target="_blank" rel="noreferrer">
                    باز کردن در زبانهٔ جدید
                  </a>
                ) : (
                  "—"
                )}
              </dd>
              <dt>انتشار</dt>
              <dd>{faDateTime(art.data.published_at)}</dd>
              <dt>دریافت</dt>
              <dd>{faDateTime(art.data.retrieved_at)}</dd>
              <dt>زبان / کشور</dt>
              <dd>
                {art.data.language ?? "—"} / {art.data.country ?? "—"}
              </dd>
              <dt>اهمیت</dt>
              <dd>{importanceLabel(art.data.importance)}</dd>
              <dt>اولویت دریافت</dt>
              <dd>{art.data.priority ?? "—"}</dd>
              <dt>موضوعات</dt>
              <dd>{art.data.topics.join("، ") || "—"}</dd>
              <dt>موجودیت‌ها</dt>
              <dd>
                {art.data.entities.map((e) => `${e.name} (${e.type})`).join("، ") || "—"}
              </dd>
              <dt>وضعیت پردازش</dt>
              <dd>
                {art.data.classification_status ?? "—"}
                {art.data.classification_error && (
                  <span className="err-text"> — {art.data.classification_error}</span>
                )}
              </dd>
            </dl>
          </div>
        )}
      </Section>
      {art.data?.event_id && (
        <Section title="ادعاهای رویداد مرتبط" error={claims.error} loading={claims.loading}>
          {claims.data && claims.data.length > 0 ? (
            <ul className="list">
              {claims.data.map((c) => (
                <li key={c.id}>
                  {c.subject} {c.predicate} {c.object} — تأیید:{" "}
                  {c.verification_status} (مستقل: {c.independent_source_count ?? "—"} از{" "}
                  {c.supporting_source_count ?? "—"})
                </li>
              ))}
            </ul>
          ) : (
            !claims.loading && <Empty text="ادعایی ثبت نشده است." />
          )}
        </Section>
      )}
    </div>
  );
}

function EventDetailView({ id }: { id: string }) {
  const list = useApi<EventItem[]>("/api/events?limit=200", []);
  const claims = useApi<ClaimItem[]>(`/api/claims?event_id=${id}&limit=50`, [id]);
  const found = list.data?.find((e) => e.id === id) ?? null;
  return (
    <div>
      <button onClick={() => nav("news")}>→ بازگشت</button>
      <Section title="جزئیات رویداد" error={list.error} loading={list.loading}>
        {found ? (
          <dl className="kv">
            <dt>نوع</dt>
            <dd>{found.event_type ?? "—"}</dd>
            <dt>شرح</dt>
            <dd>{found.action ?? "—"}</dd>
            <dt>بازیگران</dt>
            <dd>{found.actors.join("، ") || "—"}</dd>
            <dt>زمان</dt>
            <dd>{faDateTime(found.occurred_at)}</dd>
            <dt>مقالات</dt>
            <dd>{found.article_count}</dd>
          </dl>
        ) : (
          !list.loading && <Empty text="رویداد یافت نشد." />
        )}
      </Section>
      <Section title="ادعاها و شواهد" error={claims.error} loading={claims.loading}>
        {claims.data && claims.data.length > 0 ? (
          <ul className="list">
            {claims.data.map((c) => (
              <li key={c.id}>
                {c.subject} {c.predicate} {c.object} — {c.verification_status}
              </li>
            ))}
          </ul>
        ) : (
          !claims.loading && <Empty text="ادعایی ثبت نشده است." />
        )}
      </Section>
    </div>
  );
}

export default function News({ param }: { param?: string }) {
  const [tab, setTab] = useState<"articles" | "events">("articles");
  const [topic, setTopic] = useState("");
  const [minImportance, setMinImportance] = useState("");
  const articles = useApi<ArticleItem[]>("/api/classify/articles?limit=200", []);
  const events = useApi<EventItem[]>("/api/events?limit=200", []);
  const art = useFilter(articles.data, (a, q) =>
    `${a.title ?? ""} ${a.topics.join(" ")}`.includes(q),
  );

  if (param?.startsWith("article-")) {
    return <ArticleDetailView id={param.slice("article-".length)} />;
  }
  if (param?.startsWith("event-")) {
    return <EventDetailView id={param.slice("event-".length)} />;
  }

  const filteredArticles = (art.filtered ?? []).filter((a) => {
    if (topic && !a.topics.some((t) => t.includes(topic))) return false;
    // قرارداد واقعی: ۱ بالاترین اهمیت است؛ فیلتر «حداقل اهمیت X» یعنی importance <= X
    if (minImportance && (a.importance === null || a.importance === undefined || a.importance > Number(minImportance))) return false;
    return true;
  });

  return (
    <div>
      <div className="page-head">
        <h1>اخبار و رویدادها</h1>
        <div className="row">
          <RunButton label="طبقه‌بندی جدید" path="/api/classify/run?limit=50" />
          <RunButton label="استخراج رویداد" path="/api/events/extract?limit=50" />
        </div>
      </div>
      <div className="tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "articles"}
          className={tab === "articles" ? "active" : ""}
          onClick={() => setTab("articles")}
        >
          اخبار
        </button>
        <button
          role="tab"
          aria-selected={tab === "events"}
          className={tab === "events" ? "active" : ""}
          onClick={() => setTab("events")}
        >
          رویدادها
        </button>
      </div>

      {tab === "articles" && (
        <div>
          <div className="filters">
            <input
              placeholder="جست‌وجو در عنوان و موضوع…"
              value={art.q}
              onChange={(e) => art.setQ(e.target.value)}
              aria-label="جست‌وجوی اخبار"
            />
            <input
              placeholder="موضوع (مثلاً economy)"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              aria-label="فیلتر موضوع"
            />
            <input
              placeholder="سقف اهمیت (۱ بالاترین)"
              inputMode="numeric"
              value={minImportance}
              onChange={(e) => setMinImportance(e.target.value)}
              aria-label="سقف عدد اهمیت"
            />
          </div>
          <p className="hint">
            توجه: اهمیت ۱ بالاترین و ۱۰ کمترین است (قرارداد Backend).
          </p>
          {articles.error ? (
            <Section title="اخبار" error={articles.error} loading={false}>
              <span />
            </Section>
          ) : articles.loading ? (
            <p className="hint">در حال بارگذاری…</p>
          ) : (
            <Table
              columns={[
                { key: "title", label: "عنوان", render: (r) => (
                  <button className="linkbtn" onClick={() => nav("news", `article-${String(r.id)}`)}>
                    {String(r.title ?? "—")}
                  </button>
                ) },
                { key: "importance", label: "اهمیت", numeric: true, render: (r) => importanceLabel(r.importance as number | null) },
                { key: "priority", label: "اولویت", render: (r) => String(r.priority ?? "—") },
                { key: "topics", label: "موضوعات", render: (r) => (r.topics as string[]).join("، ") || "—" },
                { key: "sentiment", label: "احساس", numeric: true, render: (r) => String(r.sentiment ?? "—") },
              ]}
              rows={filteredArticles as unknown as Record<string, unknown>[]}
              rowKey={(r) => String(r.id)}
              emptyText="خبری موجود نیست."
            />
          )}
        </div>
      )}

      {tab === "events" && (
        <div>
          {events.error ? (
            <Section title="رویدادها" error={events.error} loading={false}>
              <span />
            </Section>
          ) : events.loading ? (
            <p className="hint">در حال بارگذاری…</p>
          ) : (
            <Table
              columns={[
                { key: "event_type", label: "نوع", render: (r) => (
                  <button className="linkbtn" onClick={() => nav("news", `event-${String(r.id)}`)}>
                    {String(r.event_type ?? "—")}
                  </button>
                ) },
                { key: "action", label: "شرح", render: (r) => String(r.action ?? "—").slice(0, 120) },
                { key: "article_count", label: "مقالات", numeric: true },
              ]}
              rows={(events.data ?? []) as unknown as Record<string, unknown>[]}
              rowKey={(r) => String(r.id)}
              emptyText="رویدادی موجود نیست."
            />
          )}
        </div>
      )}
    </div>
  );
}
