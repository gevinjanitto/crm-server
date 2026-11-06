import React, { useEffect, useState } from "react";
import { Copy, Link2, Trash2, Eye, Download, Clock3, LoaderCircle, KeyRound, Files } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import { Modal } from "./Common";
import "./share.css";

const PRESETS = [
  { id: "1h", label: "1 jam", hours: 1 },
  { id: "1d", label: "1 hari", hours: 24 },
  { id: "7d", label: "7 hari", hours: 168 },
  { id: "30d", label: "30 hari", hours: 720 },
  { id: "custom", label: "Tanggal sendiri" },
  { id: "forever", label: "Tanpa batas" },
];
const pad = (n) => String(n).padStart(2, "0");
const localInput = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
export const shareUrl = (token) => `${window.location.origin}/s/${token}`;
export const expiryLabel = (iso) => (iso ? new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }) : "tanpa batas waktu");

const ShareRow = ({ s, onRevoke }) => {
  const copy = async () => {
    try { await navigator.clipboard.writeText(shareUrl(s.token)); toast.success("Link disalin"); }
    catch { toast.error("Gagal menyalin, salin manual dari kolom link."); }
  };
  const many = (s.document_ids || []).length > 1;
  const mode = s.document_type === "link" ? "Link dokumen" : s.allow_download ? "Lihat & download" : "Hanya lihat";
  return (
    <div className="share-row" data-testid={`share-row-${s.id}`}>
      <div className="share-row-main">
        <input readOnly value={shareUrl(s.token)} data-testid={`share-url-${s.id}`} onFocus={(e) => e.target.select()} />
        <small>
          <Clock3 size={12} /> {s.expires_at ? `s/d ${expiryLabel(s.expires_at)}` : "Tanpa batas"} · {mode}
          {many && <> · <Files size={12} /> {s.document_ids.length} dokumen</>}
          {s.has_password && <> · <KeyRound size={12} /> Berpassword</>}
          {` · ${s.views} dilihat`}{s.document_type !== "link" && ` · ${s.downloads} unduhan`}
        </small>
      </div>
      <button type="button" className="icon-button" title="Salin link" data-testid={`copy-share-${s.id}`} onClick={copy}><Copy size={15} /></button>
      <button type="button" className="icon-button danger" title="Cabut link" data-testid={`revoke-share-${s.id}`} onClick={() => onRevoke(s)}><Trash2 size={15} /></button>
    </div>
  );
};

const ExpiryPicker = ({ preset, setPreset, custom, setCustom }) => <>
  <span className="share-label">Masa berlaku link</span>
  <div className="share-presets" role="radiogroup">
    {PRESETS.map((p) => <button type="button" key={p.id} role="radio" aria-checked={preset === p.id} className={preset === p.id ? "active" : ""} data-testid={`share-preset-${p.id}`} onClick={() => setPreset(p.id)}>{p.label}</button>)}
  </div>
  {preset === "custom" && <input type="datetime-local" className="share-datetime" data-testid="share-custom-date" min={localInput(new Date(Date.now() + 120000))} value={custom} onChange={(e) => setCustom(e.target.value)} />}
</>;

const PasswordPicker = ({ usePass, setUsePass, password, setPassword }) => <>
  <span className="share-label">Proteksi password</span>
  <div className="share-presets">
    <button type="button" className={!usePass ? "active" : ""} data-testid="share-password-off" onClick={() => setUsePass(false)}>Tanpa password</button>
    <button type="button" className={usePass ? "active" : ""} data-testid="share-password-on" onClick={() => setUsePass(true)}><KeyRound size={14} /> Pakai password</button>
  </div>
  {usePass && <input type="text" className="share-datetime" placeholder="Minimal 4 karakter" autoComplete="off" data-testid="share-password-input" value={password} onChange={(e) => setPassword(e.target.value)} />}
</>;

export const ShareDialog = ({ doc, docs, onClose, onCreated }) => {
  const items = docs?.length ? docs : doc ? [doc] : [];
  const open = items.length > 0;
  const single = items.length === 1 ? items[0] : null;
  const allLinks = items.every((d) => d.document_type === "link");
  const [preset, setPreset] = useState("1d");
  const [custom, setCustom] = useState(localInput(new Date(Date.now() + 3 * 864e5)));
  const [allowDownload, setAllowDownload] = useState(true);
  const [usePass, setUsePass] = useState(false);
  const [password, setPassword] = useState("");
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const key = items.map((d) => d.id).join(",");
  const load = () => single && api.get("/shares", { params: { document_id: single.id } }).then((r) => setRows(r.data)).catch((e) => setError(errorText(e)));
  useEffect(() => { setError(""); setRows([]); setPassword(""); setUsePass(false); load(); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const create = async () => {
    const p = PRESETS.find((x) => x.id === preset);
    const expires = p.id === "forever" ? null : p.hours ? new Date(Date.now() + p.hours * 36e5) : new Date(custom);
    if (expires && Number.isNaN(expires.getTime())) return setError("Tanggal kedaluwarsa tidak valid.");
    if (usePass && password.trim().length < 4) return setError("Password link minimal 4 karakter.");
    setBusy(true); setError("");
    try {
      const r = await api.post("/shares", { document_ids: items.map((d) => d.id), expires_at: expires ? expires.toISOString() : null, allow_download: allowDownload, password: usePass ? password.trim() : "" });
      setRows((x) => [r.data, ...x]);
      onCreated?.(r.data);
      try { await navigator.clipboard.writeText(shareUrl(r.data.token)); toast.success("Link dibuat dan disalin"); } catch { toast.success("Link dibuat"); }
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const revoke = async (s) => {
    if (!window.confirm("Cabut link ini? Penerima tidak bisa membuka file lagi.")) return;
    try { await api.delete(`/shares/${s.id}`); setRows((x) => x.filter((r) => r.id !== s.id)); toast.success("Link dicabut"); }
    catch (e) { toast.error(errorText(e)); }
  };
  const title = single ? (single.document_type === "link" ? "Bagikan dokumen" : "Bagikan file") : `Bagikan ${items.length} dokumen`;
  const description = single ? `Buat link publik untuk "${single.name}"` : "Semua dokumen terpilih dibagikan dalam 1 link";
  return (
    <Modal open={open} onClose={onClose} title={title} description={open ? description : ""}>
      {open && <div className="share-dialog" data-testid="share-dialog">
        {!single && <div className="share-selected" data-testid="share-selected-list">
          {items.map((d) => <span key={d.id} title={d.name}>{d.name}</span>)}
        </div>}
        <ExpiryPicker preset={preset} setPreset={setPreset} custom={custom} setCustom={setCustom} />
        {!allLinks && <>
        <span className="share-label">Akses penerima</span>
        <div className="share-presets">
          <button type="button" className={!allowDownload ? "active" : ""} data-testid="share-mode-view" onClick={() => setAllowDownload(false)}><Eye size={14} /> Hanya lihat</button>
          <button type="button" className={allowDownload ? "active" : ""} data-testid="share-mode-download" onClick={() => setAllowDownload(true)}><Download size={14} /> Lihat & download</button>
        </div>
        </>}
        <PasswordPicker usePass={usePass} setUsePass={setUsePass} password={password} setPassword={setPassword} />
        {error && <p className="form-error" data-testid="share-error">{error}</p>}
        <button type="button" className="primary-button share-create" data-testid="share-create-button" disabled={busy} onClick={create}>
          {busy ? <LoaderCircle className="spin" size={16} /> : <Link2 size={16} />} Buat link berbagi
        </button>
        <span className="share-label">{single ? `Link aktif (${rows.length})` : `Link dibuat (${rows.length})`}</span>
        <div className="share-list" data-testid="share-list">
          {rows.map((s) => <ShareRow key={s.id} s={s} onRevoke={revoke} />)}
          {!rows.length && <p className="share-empty">{single ? "Belum ada link aktif untuk file ini." : "Belum ada link untuk pilihan ini."}</p>}
        </div>
      </div>}
    </Modal>
  );
};
