import React from "react";
import { Link } from "react-router-dom";
import { ListChecks, Flag } from "lucide-react";
import { PRIORITY_COLOR } from "./kanban/helpers";
import { useData } from "../lib/api";

const dueLabel = (d) => {
  if (!d) return "Tanpa tenggat";
  const day = String(d).slice(0, 10), today = new Date().toISOString().slice(0, 10);
  const text = new Date(`${day}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
  return day < today ? `Terlambat · ${text}` : day === today ? "Hari ini" : text;
};

const TaskRow = ({ t }) => (
  <li data-testid={`my-task-${t.id}`}>
    <Link to={`/projects/${t.project_id}/kanban?task=${t.id}`} data-testid={`my-task-link-${t.id}`}
      style={{ display: "flex", gap: 12, alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--line)", color: "inherit" }}>
      <span style={{ flex: 1, minWidth: 0 }}>
        <b style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.title}</b>
        <small className="note-meta">{t.project_name}{t.subtasks.length ? ` · Subtask: ${t.subtasks.join(", ")}` : ""}</small>
      </span>
      <span className="note-badge" data-testid={`my-task-priority-${t.id}`} style={{ background: "transparent", color: PRIORITY_COLOR[t.priority] || "#87909e", display: "inline-flex", alignItems: "center", gap: 4 }}>
        <Flag size={12} fill="currentColor" />{t.priority || "-"}
      </span>
      <span className="note-badge" data-testid={`my-task-status-${t.id}`}>{t.status}</span>
      <small className="note-meta" style={{ minWidth: 110, textAlign: "right", color: dueLabel(t.due_date).startsWith("Terlambat") ? "#dc2626" : undefined }}>{dueLabel(t.due_date)}</small>
    </Link>
  </li>
);

export const MyTasks = () => {
  const { data, loading } = useData("/tasks/mine");
  const rows = data || [];
  return (
    <section className="panel panel-padding" data-testid="dashboard-my-tasks" style={{ marginBottom: 18 }}>
      <div className="section-heading">
        <div>
          <h2 data-testid="my-tasks-title">Task saya <span className="sample-tag" style={{ marginLeft: 8 }} data-testid="my-tasks-count">{rows.length} task</span></h2>
          <p>Task yang ditugaskan ke akun Anda dan belum selesai.</p>
        </div>
      </div>
      {loading ? <p className="form-note">Memuat task...</p> : !rows.length ? (
        <p className="form-note" data-testid="my-tasks-empty"><ListChecks size={14} style={{ verticalAlign: "-2px" }} /> Tidak ada task yang harus dikerjakan.</p>
      ) : (
        <ul data-testid="my-tasks-list" style={{ maxHeight: 360, overflow: "auto", margin: 0, padding: 0, listStyle: "none" }}>
          {rows.map((t) => <TaskRow key={t.id} t={t} />)}
        </ul>
      )}
    </section>
  );
};
