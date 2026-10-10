import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  FolderKanban,
  Activity,
  CheckCheck,
  Ticket,
  ArrowUpRight,
  ArrowRight,
  CalendarDays,
  Download,
  Check,
  Clock3,
  Layers,
  CircleDot,
  Loader,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from "recharts";
import { ChartFrame as ResponsiveContainer } from "../components/ChartFrame";
import { useAuth } from "../App";
import { useData, compact, dateLabel, download } from "../lib/api";
import {
  PageHead,
  AddButton,
  Loading,
  ErrorState,
  Empty,
} from "../components/Common";
import { Button } from "../components/ui/button";
import { ProjectTable } from "../components/ProjectTable";
import { ProjectForm } from "../components/ProjectForm";
import { canListProjects } from '../lib/projectAccess';
const colors = ["#5d85f4", "#62b6c3", "#bda8dd", "#dfb367", "#6dc3a2"];
export default function Dashboard() {
  const { user } = useAuth(),
    { data: d, loading, error, reload } = useData("/dashboard"),
    [show, setShow] = useState(false),
    navigate = useNavigate();
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const manager = ["Admin", "Admin Project"].includes(user.role),
    isClient = user.role === "Client",
    fin = d.finance,
    ts = d.ticket_stats;
  const distribution = [
    { name: "Development", value: d.development + d.dev_server },
    {
      name: "Persiapan & desain",
      value:
        d.status_counts["Project Masuk"] +
        (d.status_counts["Follow Up"] || 0) +
        d.status_counts["Dokumen Disiapkan"] +
        d.status_counts["Scope Dirinci"] +
        d.status_counts["UI/UX"] +
        d.status_counts["Disetujui"],
    },
    {
      name: "Testing & revisi",
      value: d.status_counts.Testing + d.status_counts.Revisi,
    },
    { name: "Production", value: d.production },
    { name: "Selesai", value: d.completed },
  ];
  const chart = d.projects.map((p) => ({
    name: p.client_name.split(" ")[0],
    nilai: p.value / 1e6 || 0,
    biaya: ((p.development_cost || 0) + (p.server_cost || 0)) / 1e6,
    progress: p.progress,
  }));
  const ticketKpis = ts && [
    ["Total tiket", ts.total, Ticket, `${ts.waiting_client} menunggu tanggapan Anda`, "/tickets"],
    ["Open", ts.open, CircleDot, "Baru, ditinjau & menunggu", "/tickets?group=open"],
    ["In Progress", ts.in_progress, Loader, "Sedang dikerjakan tim", "/tickets?status=Dikerjakan"],
    ["Selesai / Closed", ts.closed, CheckCheck, `${ts.rejected} ditolak`, "/tickets?group=closed"],
  ];
  const acc = user.role === "Accounting";
  const kpis = isClient && ticketKpis ? ticketKpis : [
    ["Total project", d.total, FolderKanban, `${d.active} project aktif`, "/projects"],
    ["Project aktif", d.active, Activity, `${d.development} dalam development`, "/projects?tab=Aktif"],
    ["Project selesai", d.completed, CheckCheck, `${d.production} di production`, "/projects?tab=Selesai"],
    [
      acc ? "Nilai project" : "Tiket terbuka",
      acc ? `Rp ${compact(fin?.value)}` : d.open_tickets,
      Ticket,
      acc ? "Seluruh portofolio" : `${d.closed_tickets} tiket terselesaikan`,
      acc ? "/finance" : "/tickets?group=active",
    ],
  ];
  return (
    <>
      <PageHead
        eyebrow="OVERVIEW WORKSPACE"
        title={
          <>
            Halo, {user.name.split(" ")[0]}
            <span className="greeting-wave">✺</span>
          </>
        }
        description="Satu pandangan untuk setiap progres dan peluang hari ini."
      >
        <div className="date-button" data-testid="dashboard-date">
          <CalendarDays size={14} />
          {dateLabel(new Date())}
        </div>
        {manager && (
          <AddButton onClick={() => setShow(true)} id="dashboard-add-project">
            Project baru
          </AddButton>
        )}
      </PageHead>
      <div className="kpi-grid">
        {kpis.map(([label, value, Icon, sub, to], i) => (
          <Link
            to={to}
            className="kpi-card kpi-link"
            key={label}
            data-testid={`dashboard-kpi-${i}`}
            style={{ animation: `page-enter .4s ease ${i * 0.07}s both` }}
          >
            <div className="kpi-top">
              <span>{label}</span>
              <span className="kpi-icon">
                <Icon size={15} />
              </span>
            </div>
            <div className="kpi-value">
              <b>{value}</b>
              {i === 0 && <span>{isClient && ticketKpis ? "tiket" : "project"}</span>}
            </div>
            <div className="kpi-bottom">
              <span>
                <ArrowUpRight size={12} />
              </span>
              {sub}
            </div>
          </Link>
        ))}
      </div>
      {!isClient && <div className="dashboard-grid">
        <section className="panel panel-padding">
          <div className="section-heading">
            <div>
              <h2 data-testid="chart-title">
                {fin ? "Ringkasan finansial" : "Progres project"}
              </h2>
              <p>
                {fin
                  ? "Nilai dan biaya pada project terkini"
                  : "Persentase penyelesaian project terkini"}
              </p>
            </div>
            <div className="chart-legend">
              <span>
                <i />
                {fin ? "Nilai" : "Progres"}
              </span>
              {fin && (
                <span>
                  <i />
                  Biaya
                </span>
              )}
            </div>
          </div>
          {fin ? (
            <div className="chart-stats">
              <div className="chart-stat" data-testid="dashboard-value">
                <small>Total nilai project</small>
                <b>Rp {compact(fin.value)}</b>
              </div>
              <div className="chart-separator" />
              <div className="chart-stat" data-testid="dashboard-profit">
                <small>Estimasi keuntungan</small>
                <b>Rp {compact(fin.profit)}</b>
                <span>
                  {fin.value ? Math.round((fin.profit / fin.value) * 100) : 0}%
                  margin
                </span>
              </div>
            </div>
          ) : (
            <div className="chart-stats">
              <div className="chart-stat">
                <small>Rata-rata progres</small>
                <b data-testid="dashboard-average-progress">
                  {d.projects.length
                    ? Math.round(
                        d.projects.reduce((a, p) => a + p.progress, 0) /
                          d.projects.length,
                      )
                    : 0}
                  %
                </b>
              </div>
              <div className="chart-stat">
                <small>Development & testing</small>
                <b>{d.development + d.dev_server + d.status_counts.Testing}</b>
              </div>
            </div>
          )}
          <div className="chart-box" data-testid="financial-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chart}
                margin={{ top: 15, right: 5, left: -32, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#477cff" stopOpacity={0.22} />
                    <stop offset="100%" stopColor="#477cff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  stroke="var(--line)"
                  strokeDasharray="3 5"
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  tick={{ fill: "#8993a7", fontSize: 8 }}
                  axisLine={false}
                  tickLine={false}
                  dy={9}
                />
                <YAxis
                  tick={{ fill: "#8993a7", fontSize: 8 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    borderRadius: 7,
                    fontSize: 10,
                  }}
                  formatter={(v, n) => [`${v}${fin ? " jt" : "%"}`, n]}
                />
                <Area
                  type="monotone"
                  dataKey={fin ? "nilai" : "progress"}
                  name={fin ? "Nilai" : "Progres"}
                  stroke="#628eff"
                  strokeWidth={2.5}
                  fill="url(#valueFill)"
                />
                {fin && (
                  <Area
                    type="monotone"
                    dataKey="biaya"
                    name="Biaya"
                    stroke="#62baa9"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    fill="transparent"
                  />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
        <section className="panel panel-padding">
          <div className="section-heading">
            <div>
              <h2 data-testid="distribution-title">Status project</h2>
              <p>Perjalanan setiap project Anda</p>
            </div>
            <Layers size={16} color="#758098" />
          </div>
          <div className="distribution-body">
            <div className="donut-wrap" data-testid="project-distribution">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={
                      d.total ? distribution : [{ name: "Belum ada", value: 1 }]
                    }
                    dataKey="value"
                    innerRadius="76%"
                    outerRadius="96%"
                    paddingAngle={4}
                    stroke="none"
                    startAngle={90}
                    endAngle={-270}
                  >
                    {distribution.map((_, i) => (
                      <Cell key={i} fill={d.total ? colors[i] : "#303647"} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="donut-total">
                <b>{d.total}</b>
                <span>Total project</span>
              </div>
            </div>
            <div className="distribution-list">
              {distribution.map((s, i) => (
                <div
                  className="distribution-row"
                  key={s.name}
                  data-testid={`distribution-${i}`}
                >
                  <i style={{ background: colors[i] }} />
                  <span>{s.name}</span>
                  <b>{s.value}</b>
                </div>
              ))}
            </div>
          </div>
          <div className="distribution-bottom">
            <span>Project terselesaikan</span>
            <b>
              {d.total ? Math.round((d.completed / d.total) * 100) : 0}% dari
              total project
            </b>
          </div>
        </section>
      </div>}
      <section className="project-section panel">
        <div className="section-heading">
          <div>
            <h2 data-testid="recent-projects-title">
              Project terkini{" "}
              <span className="sample-tag" style={{ marginLeft: 8 }}>
                {d.total} project
              </span>
            </h2>
            <p>Setiap detail, selangkah lebih dekat dengan tujuan.</p>
          </div>
          {canListProjects(user) && <Link
            to="/projects"
            className="section-link"
            data-testid="view-all-projects"
          >
            Lihat semua <ArrowRight size={13} />
          </Link>}
        </div>
        <ProjectTable projects={d.projects} compact />
      </section>
      <div className="dashboard-bottom">
        <section className="panel panel-padding">
          <div className="section-heading">
            <h2>Aktivitas terbaru</h2>
            <Activity size={16} color="#758098" />
          </div>
          {d.activity.length ? (
            <div className="activity-list">
              {d.activity.map((a) => (
                <Link
                  to={`/projects/${a.project_id}`}
                  className="activity-item"
                  key={a.id}
                  data-testid={`activity-${a.id}`}
                >
                  <span className="activity-icon">
                    <Check size={13} />
                  </span>
                  <div>
                    <b>{a.project_name}</b>
                    <p>{a.message}</p>
                  </div>
                  <time>{dateLabel(a.created_at)}</time>
                </Link>
              ))}
            </div>
          ) : (
            <Empty message="Belum ada aktivitas." />
          )}
        </section>
        <section className="panel panel-padding">
          <div className="section-heading">
            <h2>Deadline terdekat</h2>
            <Clock3 size={16} color="#758098" />
          </div>
          {d.deadlines.map((p) => (
            <Link
              to={`/projects/${p.id}`}
              key={p.id}
              className="deadline-item"
              data-testid={`deadline-${p.id}`}
            >
              <div className="deadline-date">
                <b>{new Date(p.due_date).getDate()}</b>
                <small>
                  {new Date(p.due_date).toLocaleDateString("id-ID", {
                    month: "short",
                  })}
                </small>
              </div>
              <div>
                <strong>{p.name}</strong>
                <p>{p.client_name}</p>
              </div>
              <span className="deadline-days">
                {Math.ceil((new Date(p.due_date) - new Date()) / 86400000) < 0
                  ? "Terlewat"
                  : `${Math.ceil((new Date(p.due_date) - new Date()) / 86400000)} hari lagi`}
              </span>
            </Link>
          ))}
          {!d.deadlines.length && <Empty message="Tidak ada deadline aktif." />}
        </section>
      </div>
      <ProjectForm
        open={show}
        onClose={() => setShow(false)}
        onSaved={(p) => navigate(`/projects/${p.id}`)}
      />
    </>
  );
}
