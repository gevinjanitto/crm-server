import React, { useEffect, useMemo, useState } from "react";
import { Copy, Eye, Download, Clock3, UserRound, KeyRound, Files, LoaderCircle } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import { Modal } from "./Common";
import { shareUrl, expiryLabel } from "./ShareDialog";
import "./share.css";

const FILTERS = ["Semua", "Aktif", "Kedaluwarsa", "Dicabut"];
const when = (iso) => new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" });

const ReportItem = ({ s }) => {
  const copy = async () => {
    try { await navigator.clipboard.writeText(shareUrl(s.token)); toast.success("Link disalin"); }
    catch { toast.error("Gagal menyalin link."); }
  };
  return (
    <article className="share-report-item" data-testid={`share-report-item-${s.id}`}>
      <header>
        <b>{s.name}</b>
        <span className={`share-status ${s.status.toLowerCase()}`} data-testid={`share-report-status-${s.id}`}>{s.status}</span>
      </header>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <code data-testid={`share-report-url-${s.id}`}>{shareUrl(s.token)}</code>
        {s.status === "Aktif" && <button type="button" className="icon-button" title="Salin link" data-testid={`share-report-copy-${s.id}`} onClick={copy}><Copy size={13} /></button>}
      </div>
      <small>
        <span data-testid={`share-report-recipient-${s.id}`}><UserRound size={12} /> {s.recipient ? `Untuk ${s.recipient}` : "Penerima tidak diisi"}</span>
        <span>Dibuat {s.created_by_name} · {when(s.created_at)}</span>
        <span><Clock3 size={12} /> {s.expires_at ? `s/d ${expiryLabel(s.expires_at)}` : "Tanpa batas"}</span>
        <span><Eye size={12} /> {s.views} dilihat</span>
        {s.document_type !== "link" && <span><Download size={12} /> {s.downloads} unduhan</span>}
        {(s.document_ids || []).length > 1 && <span><Files size={12} /> {s.document_ids.length} dokumen</span>}
        {s.has_password && <span><KeyRound size={12} /> Berpassword</span>}
      </small>
    </article>
  );
};

export const ShareReport = ({ projectId, open, onClose }) => {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("Semua");
  useEffect(() => {
    if (!open) return;
    setRows(null); setError(""); setFilter("Semua");
    api.get("/shares/report", { params: { project_id: projectId } }).then((r) => setRows(r.data)).catch((e) => setError(errorText(e)));
  }, [open, projectId]);
  const stats = useMemo(() => (rows || []).reduce((a, s) => ({ ...a, [s.status]: (a[s.status] || 0) + 1, views: a.views + s.views, downloads: a.downloads + s.downloads }), { views: 0, downloads: 0 }), [rows]);
  const shown = (rows || []).filter((s) => filter === "Semua" || s.status === filter);
  return (
    <Modal open={open} onClose={onClose} title="Laporan link berbagi" description="Semua link dokumen yang pernah dibuat di project ini">
      <div className="share-report" data-testid="share-report-dialog">
        {error && <p className="form-error" data-testid="share-report-error">{error}</p>}
        {!rows && !error && <p className="share-empty"><LoaderCircle className="spin" size={14} /> Memuat laporan...</p>}
        {rows && <>
          <div className="share-report-stats" data-testid="share-report-stats">
            <div><b data-testid="share-report-total">{rows.length}</b><span>Total link</span></div>
            <div><b data-testid="share-report-active">{stats.Aktif || 0}</b><span>Masih aktif</span></div>
            <div><b data-testid="share-report-views">{stats.views}</b><span>Total dilihat</span></div>
            <div><b data-testid="share-report-downloads">{stats.downloads}</b><span>Total unduhan</span></div>
          </div>
          <div className="share-presets share-report-filter">
            {FILTERS.map((f) => <button type="button" key={f} className={filter === f ? "active" : ""} data-testid={`share-report-filter-${f.toLowerCase()}`} onClick={() => setFilter(f)}>{f}{f !== "Semua" && ` (${stats[f] || 0})`}</button>)}
          </div>
          <div className="share-report-list" data-testid="share-report-list">
            {shown.map((s) => <ReportItem key={s.id} s={s} />)}
            {!shown.length && <p className="share-empty">Belum ada link pada kategori ini.</p>}
          </div>
        </>}
      </div>
    </Modal>
  );
};
