/** Chat: user picks a provider/model and chats over text (stateless server).
 * Uses vendored @localmode/ui conversation primitives (MIT): Conversation
 * (scroll anchoring), Response (markdown), Loader (busy states). */
import { useState } from "react";
import { api } from "../api";
import {
  Conversation, ConversationContent, ConversationEmptyState, ConversationScrollAnchor,
  ConversationScrollButton,
} from "../components/ui/conversation";
import { Loader } from "../components/ui/loader";
import { Response } from "../components/ui/response";
import { Badge, PageHeader, Section, useApi, useToast } from "../ui";

interface Provider {
  id: string; name: string; kind: string; key_set: boolean; key_source: string; enabled: boolean;
}
interface Model {
  id: string; provider_id: string; provider_name: string; model_name: string; enabled: boolean;
}
interface Msg { role: "user" | "assistant"; text: string; meta?: string }

function err(e: unknown): string {
  return e instanceof Error ? e.message : "خطا";
}

export default function Chat() {
  const toast = useToast();
  const providers = useApi<Provider[]>("/api/settings/providers", []);
  const models = useApi<Model[]>("/api/settings/models", []);
  const status = useApi<{ mock_mode: boolean }>("/api/ai/status", []);
  const [pid, setPid] = useState("");
  const [mid, setMid] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const usable = (providers.data ?? []).filter((p) => p.enabled && (p.key_source === "env" || p.key_set));
  const sel = usable.find((p) => p.id === pid) ?? null;
  const modelsOf = (models.data ?? []).filter((m) => !sel || m.provider_id === sel.id);

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    const history: Msg[] = [...msgs, { role: "user" as const, text }];
    setMsgs(history);
    setDraft("");
    setBusy(true);
    try {
      const r = await api.post<{
        text: string; provider: string; model: string; is_mock: boolean;
        total_tokens?: number | null; latency_ms?: number | null;
      }>("/api/ai/chat", {
        provider: sel ? (sel.key_source === "env" ? sel.kind : sel.name) : undefined,
        model: mid || undefined,
        messages: history.slice(-20).map((m) => ({ role: m.role, content: m.text })),
      }, 120000);
      setMsgs([...history, {
        role: "assistant",
        text: r.text,
        meta: `${r.provider}/${r.model} · ${r.total_tokens ?? "—"} توکن · ${r.latency_ms ?? "—"}ms${r.is_mock ? " · نمونه (Mock)" : ""}`,
      }]);
    } catch (e) {
      toast(err(e), "bad");
      setMsgs(history);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="گفت‌وگو با هوش مصنوعی" subtitle="ارائه‌دهنده را انتخاب کن و متنی صحبت کن. تاریخچه فقط در همین صفحه می‌ماند." />
      <Section title="انتخاب" error={providers.error} loading={providers.loading}>
        <div className="filters">
          <select value={pid} onChange={(e) => { setPid(e.target.value); setMid(""); }} aria-label="ارائه‌دهنده">
            <option value="">— پیش‌فرض سامانه —</option>
            {usable.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.kind})</option>)}
          </select>
          <select value={mid} onChange={(e) => setMid(e.target.value)} aria-label="مدل">
            <option value="">— مدل پیش‌فرض —</option>
            {modelsOf.filter((m) => m.enabled).map((m) => <option key={m.id} value={m.model_name}>{m.model_name}</option>)}
          </select>
          <button className="secondary" onClick={() => setMsgs([])}>پاک کردن گفت‌وگو</button>
        </div>
        {status.data?.mock_mode && <p className="hint">حالت آزمایشی (Mock) روشن است؛ پاسخ‌ها نمونه‌اند. <Badge tone="demo">نمونه</Badge></p>}
        {usable.length === 0 && !providers.loading && (
          <p className="hint">ارائه‌دهنده‌ی آماده‌ای نیست؛ اول در تنظیمات کلید ثبت کن.</p>
        )}
      </Section>
      <Section title="گفت‌وگو" error={null}>
        <div className="chatbox">
          <Conversation streaming={busy}>
            <ConversationContent>
              {msgs.length === 0 && !busy && (
                <ConversationEmptyState title="سلام! پیامت را بنویس." description="پاسخ مدل اینجا با قالب‌بندی نمایش داده می‌شود." />
              )}
              {msgs.map((m, i) => m.role === "user" ? (
                <div key={i} className="chat-me">
                  <div className="bubble">{m.text}</div>
                </div>
              ) : (
                <div key={i} className="chat-ai">
                  <Response>{m.text}</Response>
                  {m.meta && <small>{m.meta}</small>}
                </div>
              ))}
              {busy && <Loader variant="typing" label="در حال نوشتن پاسخ…" />}
              <ConversationScrollAnchor />
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
        </div>
        <div className="filters">
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            placeholder="پیامت را بنویس… (Enter برای ارسال)" rows={2} aria-label="متن پیام" />
          <button onClick={send} disabled={busy || !draft.trim()}>{busy ? "…" : "ارسال"}</button>
        </div>
        <p className="hint">توکن مصرفی هر پاسخ زیر همان پیام نمایش داده می‌شود.</p>
      </Section>
    </div>
  );
}
