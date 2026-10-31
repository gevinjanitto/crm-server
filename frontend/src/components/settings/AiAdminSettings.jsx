import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { Switch } from "../ui/switch";
import { api, errorText } from "../../lib/api";
import { Field } from "../Common";
import { notifyAiStatus } from "../assistant/useAiStatus";
import { AdminTokens } from "./AdminTokens";
import "../assistant/assistant.css";

export const AiAdminSettings = () => {
  const [s, setS] = useState(null), [form, setForm] = useState({ base_url: "", model: "", api_key: "" }), [busy, setBusy] = useState(false);
  const apply = (d) => { setS(d); setForm({ base_url: d.base_url, model: d.model, api_key: "" }); };
  useEffect(() => { api.get("/admin/ai-settings").then((r) => apply(r.data)).catch((e) => toast.error(errorText(e))); }, []);
  const save = async (body, msg) => {
    setBusy(true);
    try { apply((await api.patch("/admin/ai-settings", body)).data); notifyAiStatus(); toast.success(msg); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  if (!s) return null;
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const submit = (e) => { e.preventDefault(); const body = { base_url: form.base_url, model: form.model }; if (form.api_key) body.api_key = form.api_key; save(body, "Konfigurasi AI disimpan"); };
  return (
    <section className="panel panel-padding" data-testid="ai-admin-settings">
      <div className="section-heading">
        <div><h2>Fitur AI & MCP</h2><p>Asisten AI, token API, server MCP, dan koneksi OAuth ChatGPT/Claude.</p></div>
        <Sparkles size={18} color="#c9963b" />
      </div>
      <div className="ai-toggle-row">
        <div><b>{s.enabled ? "Aktif" : "Nonaktif"}</b><small>{s.env_locked ? "Dikunci nonaktif oleh AI_ENABLED=false di .env backend." : "Satu sakelar untuk semua fitur AI. Saat nonaktif, token & MCP langsung ditolak."}</small></div>
        <Switch data-testid="ai-enabled-toggle" checked={s.enabled} disabled={busy || s.env_locked} onCheckedChange={(v) => save({ enabled: v }, v ? "Fitur AI diaktifkan" : "Fitur AI dinonaktifkan")} />
      </div>
      <form onSubmit={submit}>
        <div className="ai-settings-grid">
          <Field label="AI base URL (OpenAI-compatible)" name="base_url" value={form.base_url} hint={false} onChange={change} placeholder="https://ai.sumopod.com/v1" data-testid="ai-base-url-input" />
          <Field label="Model" name="model" value={form.model} hint={false} onChange={change} placeholder="gpt-4o-mini" data-testid="ai-model-input" />
          <Field label={`API key ${s.has_api_key ? `(tersimpan ${s.key_hint}, sumber: ${s.key_source})` : "(belum ada)"}`} name="api_key" type="password" autoComplete="off" value={form.api_key} hint={false} onChange={change} placeholder="Kosongkan bila tidak diubah" data-testid="ai-api-key-input" />
        </div>
        <div className="form-actions">
          {s.key_source === "admin" && <button type="button" className="secondary-button" data-testid="ai-clear-key-button" disabled={busy} onClick={() => save({ api_key: "" }, "API key admin dihapus")}>Hapus API key</button>}
          <button type="submit" className="primary-button" data-testid="ai-settings-save-button" disabled={busy}>Simpan konfigurasi</button>
        </div>
      </form>
      <p className="form-note" data-testid="ai-assistant-ready">{s.assistant_ready ? "Asisten AI siap dipakai." : "Asisten AI belum siap: lengkapi base URL, model, dan API key (atau atur di .env backend)."}</p>
      {s.enabled && <AdminTokens />}
    </section>
  );
};
