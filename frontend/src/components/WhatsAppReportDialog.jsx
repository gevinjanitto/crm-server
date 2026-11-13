import React, { useState } from "react";
import { toast } from "sonner";
import { RotateCw, AlertTriangle, MessageCircle } from "lucide-react";
import { api, useData, errorText } from "../lib/api";
import { Loading, ErrorState, Empty } from "./Common";
import { Button } from "./ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";

const STATUS_LABEL = { queued: "Antre", accepted: "Diterima", sending: "Mengirim", sent: "Terkirim", delivered: "Delivered", read: "Read", undelivered: "Undelivered", failed: "Failed", receiving: "Menerima", received: "Diterima" };
const failed = (s) => s === "failed" || s === "undelivered";
const time = (d) => (d ? new Date(d).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "medium" }) : "-");

const ResendButton = ({ payload, id, done }) => {
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { await api.post("/admin/whatsapp-report/resend", payload); toast.success("Pesan dikirim ulang."); done(); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(false); }
  };
  return <Button size="sm" variant="outline" disabled={busy} onClick={run} data-testid={`wa-resend-${id}`}><RotateCw size={13} className={busy ? "animate-spin" : ""} /> {busy ? "Mengirim..." : "Kirim ulang"}</Button>;
};

const MessageRow = ({ m, reload }) => (
  <tr data-testid={`wa-row-${m.sid}`} style={failed(m.status) ? { background: "rgba(239,68,68,.07)" } : undefined}>
    <td>{time(m.date)}</td>
    <td><code style={{ fontSize: 11 }}>{m.sid}</code></td>
    <td>{m.recipient_name && <b style={{ display: "block" }}>{m.recipient_name}</b>}<small>{(m.to || "").replace("whatsapp:", "")}</small></td>
    <td style={{ maxWidth: 260 }}><small style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={m.body}>{m.notification_title || m.body}</small></td>
    <td><span className="note-badge" data-testid={`wa-status-${m.sid}`} style={failed(m.status) ? { color: "#dc2626" } : undefined}>{STATUS_LABEL[m.status] || m.status}</span></td>
    <td data-testid={`wa-error-${m.sid}`}>{m.error_code ? <><b>{m.error_code}</b><small style={{ display: "block", maxWidth: 280 }}>{m.error_help || m.error_message}</small></> : "-"}</td>
    <td>{m.resent_sid ? <small data-testid={`wa-resent-${m.sid}`}>Sudah dikirim ulang</small> : m.can_resend ? <ResendButton id={m.sid} payload={{ message_sid: m.sid }} done={reload} /> : null}</td>
  </tr>
);

const ReportBody = () => {
  const [status, setStatus] = useState(""), [page, setPage] = useState(""), [history, setHistory] = useState([]), [refreshing, setRefreshing] = useState(false);
  const path = `/admin/whatsapp-report?status=${status}${page ? `&page_uri=${encodeURIComponent(page)}` : ""}`;
  const { data, loading, error, reload, setData } = useData(path);
  const refresh = async () => {
    setRefreshing(true);
    try { setData((await api.get(path)).data); toast.success("Laporan WhatsApp diperbarui."); }
    catch (e) { toast.error(errorText(e)); }
    finally { setRefreshing(false); }
  };
  const refreshButton = <Button variant="outline" onClick={refresh} disabled={refreshing} data-testid="wa-refresh"><RotateCw size={14} className={refreshing ? "animate-spin" : ""} /> {refreshing ? "Memuat..." : "Muat ulang"}</Button>;
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorState error={error} reload={reload} />;
  const msgs = data.messages || [];
  const pick = (s) => { setStatus(s); setPage(""); setHistory([]); };
  return (
    <>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>{refreshButton}</div>
      {data.configuration_note && <p className="form-note" data-testid="wa-config-note"><AlertTriangle size={14} style={{ display: "inline", verticalAlign: "-2px" }} /> {data.configuration_note}</p>}
      {data.template_category && data.template_category.toUpperCase() !== "UTILITY" && (
        <p className="form-note" data-testid="wa-category-warning" style={{ color: "#b45309" }}><AlertTriangle size={14} style={{ display: "inline", verticalAlign: "-2px" }} /> Template WhatsApp saat ini berkategori <b>{data.template_category}</b> oleh Meta. Pesan marketing dibatasi Meta (error 63049). Buka Pengaturan → Notifikasi akun → Template WhatsApp lalu sinkronkan ulang agar berkategori UTILITY.</p>
      )}
      <div className="list-toolbar"><div className="filter-tabs">
        {[["", "Semua"], ["failed", "Gagal saja"]].map(([v, l]) => <button key={v || "all"} className={`filter-tab${status === v ? " active" : ""}`} onClick={() => pick(v)} data-testid={`wa-filter-${v || "all"}`}>{l}</button>)}
      </div></div>
      <section className="panel">
        {!msgs.length ? <Empty message="Belum ada pesan WhatsApp." /> : (
          <div className="table-wrap"><table className="data-table" data-testid="wa-report-table">
            <thead><tr><th>Waktu</th><th>Message SID</th><th>Penerima</th><th>Isi</th><th>Status</th><th>Error</th><th /></tr></thead>
            <tbody>{msgs.map((m) => <MessageRow key={m.sid} m={m} reload={refresh} />)}</tbody>
          </table></div>
        )}
      </section>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 12 }}>
        {history.length > 0 && <Button variant="outline" size="sm" data-testid="wa-prev-page" onClick={() => { const h = [...history]; setPage(h.pop()); setHistory(h); }}>Sebelumnya</Button>}
        {data.next_page && <Button variant="outline" size="sm" data-testid="wa-next-page" onClick={() => { setHistory([...history, page]); setPage(data.next_page); }}>Berikutnya</Button>}
      </div>
    </>
  );
};

export const WhatsAppReportDialog = () => {
  const [open, setOpen] = useState(false);
  return <>
    <Button type="button" variant="outline" data-testid="wa-report-open" onClick={() => setOpen(true)}><MessageCircle size={14} />Laporan WhatsApp</Button>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="wa-report-dialog" data-testid="wa-report-dialog" style={{ maxWidth: "min(1100px, 96vw)", maxHeight: "88vh", overflowY: "auto" }}>
        <DialogHeader>
          <DialogTitle data-testid="page-title">Laporan WhatsApp</DialogTitle>
          <DialogDescription>Status setiap pesan WhatsApp langsung dari Twilio. Pesan yang gagal bisa dikirim ulang.</DialogDescription>
        </DialogHeader>
        {open && <ReportBody />}
      </DialogContent>
    </Dialog>
  </>;
};
