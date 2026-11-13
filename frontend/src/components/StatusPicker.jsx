import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, CheckCircle2, FileText, Lock, Loader2, Upload, CircleDot } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import "./status-picker.css";

export const REQUIRED_DEV_DOCS = ["Penawaran Harga", "Kontrak"];
const DEV_STATUSES = ["Development", "Uploaded to Dev Server", "Testing", "Revisi"];
const FINAL = ["Uploaded to Production", "Selesai"];

const HINTS = {
  "Project Masuk": "Project baru diterima",
  "Follow Up": "Tindak lanjuti kebutuhan client",
  "Dokumen Disiapkan": "Siapkan penawaran & kontrak",
  "Scope Dirinci": "Rinci fitur & ruang lingkup",
  "UI/UX": "Rancangan desain antarmuka",
  Disetujui: "Client menyetujui scope",
  Development: "Tim mulai mengerjakan",
  "Uploaded to Dev Server": "Build di server development",
  Testing: "Uji sebelum rilis",
  Revisi: "Perbaiki temuan testing",
  "Uploaded to Production": "Rilis ke production",
  Selesai: "Project diserahterimakan",
};

// Aturan role (sama dengan backend). Mengembalikan alasan terkunci, atau "" jika boleh dipilih.
export const roleBlock = (role, current, target) => {
  if (role === "Developer")
    return DEV_STATUSES.includes(current) && DEV_STATUSES.slice(1).includes(target) ? "" : "Khusus Admin / Admin Project";
  if (FINAL.includes(target) && role !== "Admin") return "Khusus Admin";
  return "";
};
export const canChangeAnyStatus = (role, current, statuses) =>
  ["Admin", "Admin Project"].includes(role) || statuses.some((s) => s !== current && !roleBlock(role, current, s));

export const StatusPicker = ({ p, user, statuses, reload }) => {
  const [next, setNext] = useState(""),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [docs, setDocs] = useState(null);
  const idx = statuses.indexOf(p.status), devIdx = statuses.indexOf("Development");
  const needsDocs = idx < devIdx && user.role !== "Developer";
  useEffect(() => {
    if (!needsDocs) return;
    api.get(`/projects/${p.id}/documents`).then((r) => setDocs(r.data)).catch(() => setDocs([]));
  }, [needsDocs, p.id]);
  const docsReady = !needsDocs || (docs || []).some((d) => REQUIRED_DEV_DOCS.includes(d.kind));
  const blockOf = (s) => {
    if (s === p.status) return "Status saat ini";
    const r = roleBlock(user.role, p.status, s);
    if (r) return r;
    if (needsDocs && statuses.indexOf(s) >= devIdx && docs !== null && !docsReady) return "Butuh dokumen Penawaran/Kontrak";
    return "";
  };
  const submit = async () => {
    if (!next) return setError("Pilih status tujuan terlebih dahulu.");
    if (blockOf(next)) return setError(blockOf(next));
    setBusy(true);
    setError("");
    try {
      await api.post(`/projects/${p.id}/status`, { status: next, note });
      toast.success(`Status project: ${next}`);
      setNote("");
      setNext("");
      reload();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="sp-wrap" data-testid="status-picker">
      <div className="sp-head">
        <h2 className="detail-heading">Perbarui status</h2>
        <span className="sp-current" data-testid="status-picker-current"><CircleDot size={13} /> Saat ini: <b>{p.status}</b></span>
      </div>
      <p className="sp-sub">Pilih status mana pun yang diinginkan, lalu konfirmasi perubahan.</p>
      <div className="sp-options sp-grid" role="radiogroup" aria-label="Status project">
        {statuses.map((s, i) => {
          const block = blockOf(s), current = s === p.status, active = next === s, passed = i < idx;
          return (
            <button type="button" key={s} role="radio" aria-checked={active} disabled={current}
              className={`sp-option ${active ? "active" : ""} ${current ? "current" : ""} ${passed ? "passed" : ""} ${block && !current ? "locked" : ""}`}
              data-testid={`status-option-${s.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
              title={block || HINTS[s]}
              onClick={() => { if (block) { setError(`${s}: ${block}`); return; } setNext(s); setError(""); }}>
              <span className="sp-step">{active ? <Check size={14} /> : block && !current ? <Lock size={13} /> : passed ? <Check size={13} /> : i + 1}</span>
              <span className="sp-text">
                <b>{s}</b>
                <small>{current ? "Status saat ini" : block || HINTS[s]}</small>
              </span>
            </button>
          );
        })}
      </div>
      {needsDocs && (
        <div className={`sp-docs ${docsReady ? "ready" : ""}`} data-testid="status-required-docs">
          <div className="sp-docs-icon">{docs === null ? <Loader2 size={16} className="spin" /> : docsReady ? <CheckCircle2 size={17} /> : <FileText size={17} />}</div>
          <div className="sp-docs-text">
            <b>Dokumen wajib sebelum Development</b>
            <small>{docsReady ? "Penawaran/Kontrak sudah tersedia. Project siap masuk Development." : "Unggah dokumen Penawaran Harga atau Kontrak terlebih dahulu."}</small>
          </div>
          {!docsReady && docs !== null && (
            <Link to={`/projects/${p.id}/dokumen`} className="sp-docs-link" data-testid="status-upload-docs-link"><Upload size={14} /> Unggah dokumen</Link>
          )}
        </div>
      )}
      <div className="sp-confirm">
        <label className="sp-note">
          <span>Catatan perubahan <em>(opsional)</em></span>
          <input data-testid="field-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Contoh: kontrak sudah ditandatangani client" />
        </label>
        <button type="button" className="sp-submit" data-testid="save-button" disabled={busy || !next || !!blockOf(next)} onClick={submit}>
          {busy ? <Loader2 size={15} className="spin" /> : <Check size={15} />}
          {next ? `Pindah ke ${next}` : "Pilih status"}
        </button>
      </div>
      {error && <p className="form-error" data-testid="status-update-error">{error}</p>}
    </section>
  );
};
