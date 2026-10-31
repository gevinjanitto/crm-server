import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Send, Sparkles, Loader2, Wrench, RotateCcw, Zap } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "../ui/sheet";
import { api, errorText } from "../../lib/api";

const STARTERS = ["Ada tugas apa untuk saya?", "Rekomendasikan tugas berikutnya", "Tugas apa yang belum ada pemiliknya?", "Daftar project saya"];

const Steps = ({ steps }) => !steps?.length ? null : (
  <div className="ai-steps" data-testid="assistant-steps">
    {steps.map((s, i) => <span key={i} className={s.ok ? "" : "failed"}><Wrench size={11} />{s.tool}</span>)}
  </div>
);

const Message = ({ m, onAction, busy }) => (
  <div className={`ai-msg ${m.role}`} data-testid={`assistant-message-${m.role}`}>
    {m.role === "assistant" ? <><Steps steps={m.steps} /><div className="ai-md"><ReactMarkdown components={{ a: (p) => <a {...p} target="_blank" rel="noreferrer">{p.children}</a> }}>{m.content}</ReactMarkdown></div></> : <p>{m.content}</p>}
    {m.suggestions?.length > 0 && (
      <div className="ai-chips">
        {m.suggestions.map((s, i) => (
          <button key={i} type="button" disabled={busy} data-testid={`assistant-suggestion-${i}`} onClick={() => onAction(s)}><Zap size={12} />{s.label}</button>
        ))}
      </div>
    )}
  </div>
);

export const AssistantPanel = ({ open, onOpenChange, ready }) => {
  const [messages, setMessages] = useState([]), [input, setInput] = useState(""), [busy, setBusy] = useState(false), [conversation, setConversation] = useState(null);
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);
  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setInput(""); setMessages((m) => [...m, { role: "user", content: message }]); setBusy(true);
    try {
      const r = await api.post("/assistant/chat", { message, conversation_id: conversation });
      setConversation(r.data.conversation_id);
      setMessages((m) => [...m, { role: "assistant", content: r.data.reply, steps: r.data.steps, suggestions: r.data.suggestions }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `**Gagal:** ${errorText(e)}` }]);
    } finally { setBusy(false); }
  };
  const runAction = async (s) => {
    setBusy(true);
    try {
      const r = await api.post("/assistant/action", s.action);
      const t = r.data.result;
      toast.success(`${s.label} — berhasil`);
      setMessages((m) => [...m, { role: "assistant", content: `Selesai: **${t?.judul || s.label}**${t?.assignees ? ` sekarang di-assign ke ${t.assignees.join(", ")}` : ""}.${t?.url ? ` [Buka kartu](${t.url})` : ""}` }]);
    } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  const reset = () => { setMessages([]); setConversation(null); };
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="ai-panel" data-testid="assistant-panel">
        <SheetHeader className="ai-head">
          <SheetTitle className="ai-title"><Sparkles size={17} />Asisten AI</SheetTitle>
          <SheetDescription>Bertanya dengan data asli CRM Anda.</SheetDescription>
          {messages.length > 0 && <button type="button" className="ai-reset" data-testid="assistant-reset" onClick={reset} title="Percakapan baru"><RotateCcw size={14} /></button>}
        </SheetHeader>
        {!ready ? (
          <div className="ai-disabled" data-testid="assistant-disabled-message">
            <Sparkles size={26} />
            <b>Asisten AI belum aktif</b>
            <p>Admin belum mengisi konfigurasi provider AI (base URL, model, dan API key) di Pengaturan → Fitur AI & MCP.</p>
          </div>
        ) : (
          <>
            <div className="ai-thread" data-testid="assistant-thread">
              {!messages.length && (
                <div className="ai-empty">
                  <p>Coba tanyakan:</p>
                  {STARTERS.map((s, i) => <button key={s} type="button" data-testid={`assistant-starter-${i}`} onClick={() => send(s)}>{s}</button>)}
                </div>
              )}
              {messages.map((m, i) => <Message key={i} m={m} onAction={runAction} busy={busy} />)}
              {busy && <div className="ai-msg assistant ai-typing" data-testid="assistant-loading"><Loader2 size={14} className="spin" />Sedang memproses…</div>}
              <div ref={endRef} />
            </div>
            <form className="ai-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
              <textarea data-testid="assistant-input" rows={2} value={input} maxLength={4000} placeholder="Tulis pertanyaan…" onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
              <button type="submit" data-testid="assistant-send-button" disabled={busy || !input.trim()} aria-label="Kirim"><Send size={16} /></button>
            </form>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
};
