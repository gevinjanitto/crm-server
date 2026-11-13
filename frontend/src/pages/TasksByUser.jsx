import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Flag, ChevronDown, ChevronRight, Search } from "lucide-react";
import { PRIORITY_COLOR } from "../components/kanban/helpers";
import { useData, initials } from "../lib/api";
import { PageHead, Loading, ErrorState, Empty } from "../components/Common";
import { ProjectTaskGroups } from "../components/ProjectTaskGroups";

const due = (d) => {
  if (!d) return "Tanpa tenggat";
  const day = String(d).slice(0, 10), late = day < new Date().toISOString().slice(0, 10);
  return `${late ? "Terlambat · " : ""}${new Date(`${day}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" })}`;
};

const TaskRow = ({ t, gid }) => (
  <li>
    <Link to={`/projects/${t.project_id}/kanban?task=${t.id}`} data-testid={`admin-task-${gid}-${t.id}`}
      style={{ display: "flex", flexWrap: "wrap", gap: "6px 12px", alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--line)", color: "inherit" }}>
      <span style={{ flex: "1 1 220px", minWidth: 0 }}>
        <b style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.title}</b>
        <small className="note-meta">{t.subtasks.length ? `Subtask: ${t.subtasks.join(", ")}` : ""}</small>
      </span>
      <span className="note-badge" style={{ background: "transparent", color: PRIORITY_COLOR[t.priority] || "#87909e", display: "inline-flex", alignItems: "center", gap: 4 }}><Flag size={12} fill="currentColor" />{t.priority || "-"}</span>
      <span className="note-badge">{t.status}</span>
      <small className="note-meta" style={{ minWidth: 120, textAlign: "right", color: due(t.due_date).startsWith("Terlambat") ? "#dc2626" : undefined }}>{due(t.due_date)}</small>
    </Link>
  </li>
);

const Group = ({ g }) => {
  const [open, setOpen] = useState(false), gid = g.user_id || "unassigned";
  return (
    <section className="panel panel-padding" style={{ marginBottom: 14 }} data-testid={`admin-task-group-${gid}`}>
      <button type="button" onClick={() => setOpen(!open)} data-testid={`admin-task-group-toggle-${gid}`}
        style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", background: "none", border: 0, color: "inherit", cursor: "pointer", textAlign: "left" }}>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span className="avatar small">{initials(g.name)}</span>
        <b style={{ flex: 1 }}>{g.name} {g.role && <small className="note-meta">· {g.role}</small>}</b>
        <span className="sample-tag" data-testid={`admin-task-count-${gid}`}>{g.tasks.length} task</span>
      </button>
      {open && <ul style={{ margin: "8px 0 0", padding: 0, listStyle: "none" }}><ProjectTaskGroups rows={g.tasks} prefix={`admin-task-${gid}`} renderRow={(t) => <TaskRow key={t.id} t={t} gid={gid} />} /></ul>}
    </section>
  );
};

export default function TasksByUser() {
  const { data, loading, error, reload } = useData("/admin/tasks-by-user"), [q, setQ] = useState("");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const groups = data.filter((g) => g.name.toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <PageHead eyebrow="TIM" title="Task Tim" description="Task yang belum selesai, dikelompokkan per anggota tim. Klik nama untuk membuka daftarnya." />
      <div className="list-toolbar"><div className="list-search" style={{ marginLeft: 0 }}><Search size={15} /><input placeholder="Cari user..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="admin-task-search" /></div></div>
      {!groups.length ? <Empty message="Tidak ada task yang belum selesai." /> : groups.map((g) => <Group key={g.user_id || "unassigned"} g={g} />)}
    </>
  );
}
