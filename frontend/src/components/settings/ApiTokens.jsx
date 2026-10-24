import React, { useState } from "react";
import { toast } from "sonner";
import { KeyRound, Copy } from "lucide-react";
import { api, useData, errorText } from "../../lib/api";
import { Field } from "../Common";
import "../assistant/assistant.css";

const when = (d) => (d ? new Date(d).toLocaleString("id-ID") : "—");
const BACKEND = process.env.REACT_APP_BACKEND_URL;

export const TokenRow = ({ t, owner, onRevoke, prefix = "my" }) => (
  <div className={`ai-token ${t.revoked_at ? "revoked" : ""}`} data-testid={`${prefix}-token-${t.id}`}>
    <div className="meta">
      <span><b>{t.name}</b> <code>{t.prefix}…</code> {t.kind === "oauth" && <code>OAuth</code>} <code>{(t.scopes || []).join(" + ")}</code></span>
      <small>{owner ? `${owner} · ` : ""}Dibuat {when(t.created_at)} · Terakhir dipakai {when(t.last_used_at)}{t.kind === "pat" && t.expires_at ? ` · Kedaluwarsa ${when(t.expires_at)}` : ""}</small>
    </div>
    {t.revoked_at ? <small>Dicabut</small> : <button type="button" className="secondary-button" data-testid={`${prefix}-token-revoke-${t.id}`} onClick={() => onRevoke(t)}>Cabut</button>}
  </div>
);

const copy = (text) => navigator.clipboard?.writeText(text).then(() => toast.success("Disalin")).catch(() => {});

const CreateForm = ({ onCreated }) => {
  const [form, setForm] = useState({ name: "", write: false, expires_days: "" }), [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try {
      const body = { name: form.name, scopes: form.write ? ["read", "write"] : ["read"] };
      if (form.expires_days) body.expires_days = Number(form.expires_days);
      onCreated((await api.post("/me/tokens", body)).data); setForm({ name: "", write: false, expires_days: "" });
    } catch (err) { toast.error(errorText(err)); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={submit} className="ai-settings-grid" data-testid="token-create-form">
      <Field label="Nama token" value={form.name} required maxLength={60} placeholder="mis. Claude Desktop" onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="token-name-input" />
      <Field label="Kedaluwarsa (hari)" type="number" min={1} max={365} value={form.expires_days} onChange={(e) => setForm({ ...form, expires_days: e.target.value })} data-testid="token-expiry-input" />
      <label className="ai-toggle-row" style={{ cursor: "pointer" }}>
        <span><b>Izinkan aksi tulis</b><small>Assign, ubah status, subtask, komentar</small></span>
        <input type="checkbox" checked={form.write} onChange={(e) => setForm({ ...form, write: e.target.checked })} data-testid="token-write-checkbox" />
      </label>
      <div className="form-actions"><button type="submit" className="primary-button" disabled={busy} data-testid="token-create-button">Buat token</button></div>
    </form>
  );
};

export const ApiTokens = () => {
  const { data, reload } = useData("/me/tokens"), [created, setCreated] = useState(null);
  const revoke = async (t) => {
    if (!window.confirm(`Cabut token "${t.name}"? Aplikasi yang memakainya akan langsung ditolak.`)) return;
    try { await api.delete(`/me/tokens/${t.id}`); toast.success("Token dicabut"); reload(); } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <section className="panel panel-padding" data-testid="api-tokens-section">
      <div className="section-heading">
        <div><h2>Token API & koneksi AI</h2><p>Hubungkan ChatGPT, Claude Desktop, atau Cursor ke CRM. Maksimal 10 token aktif.</p></div>
        <KeyRound size={18} color="#7d9de2" />
      </div>
      <p className="ai-endpoint">Server MCP: <code data-testid="mcp-endpoint">{BACKEND}/api/mcp</code> <button type="button" className="pw-icon" onClick={() => copy(`${BACKEND}/api/mcp`)} title="Salin"><Copy size={13} /></button></p>
      <CreateForm onCreated={(t) => { setCreated(t); reload(); }} />
      {created && (
        <div className="ai-secret" data-testid="token-created-secret">
          <b>Salin token sekarang — hanya ditampilkan sekali.</b>
          <code data-testid="token-created-value">{created.token}</code>
          <button type="button" className="secondary-button" style={{ marginTop: 8 }} data-testid="token-copy-button" onClick={() => copy(created.token)}>Salin token</button>
        </div>
      )}
      <div className="ai-token-list">
        {(data || []).map((t) => <TokenRow key={t.id} t={t} onRevoke={revoke} />)}
        {data?.length === 0 && <p className="form-note" data-testid="tokens-empty">Belum ada token.</p>}
      </div>
    </section>
  );
};
