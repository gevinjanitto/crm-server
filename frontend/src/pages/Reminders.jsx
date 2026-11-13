import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Search, BellRing, CheckCircle2, Clock3, AlertTriangle } from "lucide-react";
import { useData, dateLabel } from "../lib/api";
import { PageHead, Loading, ErrorState, Empty } from "../components/Common";
import { ReminderFiles } from "../components/ProjectReminders";

export const remainingLabel = (r) => r.done ? "—" : r.days_left > 0 ? `${r.days_left} hari lagi` : r.days_left === 0 ? "Hari ini" : `Lewat ${-r.days_left} hari`;
export const urgency = (r) => r.done ? "" : r.days_left < 0 ? "overdue" : r.days_left <= 14 ? "soon" : "";

const Stat = ({ icon: Icon, label, value, id, tone }) => (
  <div className={`reminder-stat ${tone || ""}`} data-testid={`reminder-stat-${id}`}><Icon size={18} /><small>{label}</small><b>{value}</b></div>
);

export default function Reminders() {
  const { data, loading, error, reload } = useData("/reminders"),
    [filter, setFilter] = useState("Semua"),
    [q, setQ] = useState("");
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data.filter((r) => (filter === "Semua" || r.status === filter) &&
    `${r.name} ${r.project_name}`.toLowerCase().includes(q.toLowerCase()));
  const running = data.filter((r) => !r.done);
  return (
    <div className="reminders-page" data-testid="reminders-page">
      <PageHead eyebrow="LAPORAN" title="Reminder"
        description="Seluruh reminder project, diurutkan dari tanggal akhir terdekat. Admin menerima notifikasi WhatsApp 2 minggu sebelum tanggal akhir, plus notif tambahan bila diatur." />
      <div className="reminder-stats">
        <Stat icon={BellRing} label="Total reminder" value={data.length} id="total" />
        <Stat icon={Clock3} label="Berjalan" value={running.length} id="running" />
        <Stat icon={AlertTriangle} label="≤ 14 hari / lewat" value={running.filter((r) => r.days_left <= 14).length} id="soon" tone="warn" />
        <Stat icon={CheckCircle2} label="Selesai" value={data.length - running.length} id="done" tone="ok" />
      </div>
      <div className="list-toolbar">
        <div className="filter-tabs">
          {["Semua", "Berjalan", "Selesai"].map((f) => (
            <button key={f} className={`filter-tab ${filter === f ? "active" : ""}`} onClick={() => setFilter(f)} data-testid={`reminder-filter-${f.toLowerCase()}`}>{f}</button>
          ))}
        </div>
        <div className="list-search">
          <Search size={15} />
          <input data-testid="reminder-search" placeholder="Cari reminder / project..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      <div className="panel table-wrap">
        {rows.length ? (
          <table className="data-table reminder-table" data-testid="reminder-table">
            <thead><tr><th>Project</th><th>Nama</th><th>Tgl mulai</th><th>Tgl akhir</th><th>Sisa waktu</th><th>Status</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} data-testid={`reminder-row-${r.id}`} className={r.done ? "is-done" : ""}>
                  <td><Link to={`/projects/${r.project_id}/reminder`} data-testid={`reminder-project-link-${r.id}`}>{r.project_name}</Link></td>
                  <td><b>{r.name}</b>{r.done && r.done_by && <small className="reminder-done-by">Diselesaikan {r.done_by}</small>}
                    {r.description && <p className="reminder-desc" data-testid={`reminder-row-description-${r.id}`}>{r.description}</p>}
                    {r.extra_notify && <small className="reminder-extra-note" data-testid={`reminder-row-extra-${r.id}`}>+ Notif tambahan H-{r.extra_notify_days}</small>}
                    <ReminderFiles r={r} /></td>
                  <td className="nowrap">{dateLabel(r.start_date)}</td>
                  <td className="nowrap">{dateLabel(r.end_date)}</td>
                  <td className={`nowrap reminder-left ${urgency(r)}`} data-testid={`reminder-left-${r.id}`}>{remainingLabel(r)}</td>
                  <td data-testid={`reminder-status-${r.id}`}><span className={`status-badge ${r.done ? "green" : "blue"}`}><i />{r.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty message={data.length ? "Tidak ada reminder yang cocok." : "Belum ada reminder. Tambahkan dari tab Reminder di halaman project."} />}
      </div>
    </div>
  );
}
