export const PRIORITIES = ["Mendesak", "Tinggi", "Sedang", "Rendah"];
export const PRIORITY_COLOR = {
  Mendesak: "#e5484d",
  Tinggi: "#f5a623",
  Sedang: "#4f8ef7",
  Rendah: "#9aa4b8",
};
export const SOURCE_LABEL = {
  manual: "Manual",
  feature: "Fitur",
  revision: "Revisi",
  maintenance: "Maintenance",
  ticket: "Tiket",
  clickup: "ClickUp",
};
export const STATUS_COLORS = [
  "#87909e",
  "#3b82f6",
  "#8b5cf6",
  "#f59e0b",
  "#ef4444",
  "#10b981",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#0ea5e9",
];
export const isManager = (u) => ["Admin", "Admin Project"].includes(u.role);
export const taskAssigneeIds = (t) => [...new Set([...(t.assignee_ids || []), ...(t.assigned_to ? [t.assigned_to] : [])])];
export const canEditTask = (u, t) =>
  isManager(u) ||
  (u.role === "Developer" && (!taskAssigneeIds(t).length || taskAssigneeIds(t).includes(u.id)));
// Developer yang punya akses project (anggota atau memiliki minimal 1 task) dapat memindahkan semua kartu.
export const canMoveTask = (u) => isManager(u) || u?.role === "Developer";
export const kindOf = (statuses, name) =>
  (statuses || []).find((s) => s.name === name)?.kind || "active";
export const colorOf = (statuses, name) =>
  (statuses || []).find((s) => s.name === name)?.color || "#87909e";
export const isDone = (statuses, t) => kindOf(statuses, t.status) === "done";
export const isOverdue = (statuses, t) =>
  t.due_date &&
  !isDone(statuses, t) &&
  t.due_date < new Date().toISOString().slice(0, 10);
export const fmtDuration = (s) => {
  s = Math.max(0, Math.round(s || 0));
  const h = Math.floor(s / 3600),
    m = Math.floor((s % 3600) / 60),
    sec = s % 60;
  if (h) return `${h}j ${m}m`;
  if (m) return `${m}m ${sec}d`;
  return `${sec}d`;
};
export const midOrder = (before, after) => {
  if (before && after) return (before.order + after.order) / 2;
  if (before) return before.order + 1;
  if (after) return after.order - 1;
  return 1;
};
export const byOrder = (a, b) => (a.order || 0) - (b.order || 0);
export const shortDate = (d) =>
  d
    ? new Date(d).toLocaleDateString("id-ID", { day: "numeric", month: "short" })
    : "";

export const summarizeTasks = (tasks, statuses) => {
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString();
  const people = new Map();
  tasks.forEach(t => {
    const assignees = t.assignees?.length ? t.assignees : t.assigned_to ? [{ id: t.assigned_to, name: t.assigned_name }] : [{ id: '', name: 'Belum ditugaskan' }];
    assignees.forEach(person => {
      const row = people.get(person.id) || { name: person.name, total: 0, done: 0, time: 0 };
      row.total += 1; row.done += Number(isDone(statuses, t));
      row.time += (t.time_entries || []).filter(e => e.ended_at && e.user_id === person.id).reduce((n, e) => n + (e.seconds || 0), 0);
      people.set(person.id, row);
    });
  });
  return {
    total: tasks.length, done: tasks.filter(t => isDone(statuses, t)).length,
    overdue: tasks.filter(t => isOverdue(statuses, t)).length,
    unassigned: tasks.filter(t => !taskAssigneeIds(t).length).length,
    completed_week: tasks.filter(t => isDone(statuses, t) && t.updated_at >= weekAgo).length,
    time_total: tasks.reduce((n, t) => n + (t.time_total || 0), 0),
    estimate_total: tasks.reduce((n, t) => n + (t.estimate_hours || 0), 0),
    by_status: statuses.map(s => ({ name: s.name, color: s.color, count: tasks.filter(t => t.status === s.name).length })),
    by_priority: PRIORITIES.map(name => ({ name, count: tasks.filter(t => t.priority === name).length })),
    by_source: Object.keys(SOURCE_LABEL).map(name => ({ name, count: tasks.filter(t => t.source === name).length })),
    by_assignee: [...people.values()].sort((a, b) => b.total - a.total),
  };
};
