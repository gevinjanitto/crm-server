import React, { useState } from "react";
import { Flag, Trash2, ChevronDown, ChevronRight, X } from "lucide-react";
import { toast } from "sonner";
import { api, errorText, dateLabel, slug } from "../../lib/api";
import { MultiAssigneeSelect } from "./MultiAssigneeSelect";
import { Empty } from "../Common";
import {
  PRIORITIES,
  PRIORITY_COLOR,
  SOURCE_LABEL,
  byOrder,
  canEditTask,
  canMoveTask,
  fmtDuration,
  isOverdue,
  taskAssigneeIds,
} from "./helpers";

const BulkBar = ({ ids, project, statuses, team, clear, reload }) => {
  const run = async (body, ok) => {
    try {
      await api.post(`/projects/${project.id}/tasks/bulk`, { ids, ...body });
      toast.success(ok);
      clear();
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <div className="ck-bulkbar" data-testid="bulk-bar">
      <b>{ids.length} dipilih</b>
      <select
        className="ck-select"
        data-testid="bulk-status"
        defaultValue=""
        onChange={(e) => e.target.value && run({ status: e.target.value }, "Status diperbarui")}
      >
        <option value="">Ubah status…</option>
        {statuses.map((s) => (
          <option key={s.id}>{s.name}</option>
        ))}
      </select>
      <select
        className="ck-select"
        data-testid="bulk-assignee"
        defaultValue=""
        onChange={(e) => e.target.value && run({ assigned_to: e.target.value }, "PIC diperbarui")}
      >
        <option value="">Ubah PIC…</option>
        {team.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
      <select
        className="ck-select"
        data-testid="bulk-priority"
        defaultValue=""
        onChange={(e) => e.target.value && run({ priority: e.target.value }, "Prioritas diperbarui")}
      >
        <option value="">Ubah prioritas…</option>
        {PRIORITIES.map((p) => (
          <option key={p}>{p}</option>
        ))}
      </select>
      <button
        className="ck-danger"
        data-testid="bulk-delete"
        onClick={() => window.confirm(`Hapus ${ids.length} task?`) && run({ delete: true }, "Task dihapus")}
      >
        <Trash2 size={14} /> Hapus
      </button>
      <button className="ck-icon" data-testid="bulk-clear" onClick={clear} title="Batal">
        <X size={16} />
      </button>
    </div>
  );
};

export const ListView = ({
  project,
  tasks,
  statuses,
  user,
  manager,
  team,
  onOpen,
  onLocalUpdate,
  reload,
}) => {
  const [collapsed, setCollapsed] = useState({}),
    [selected, setSelected] = useState([]);
  const patch = async (t, body) => {
    onLocalUpdate({ ...t, ...body });
    try {
      const r = await api.patch(`/projects/${project.id}/tasks/${t.id}`, body);
      onLocalUpdate(r.data);
    } catch (e) {
      toast.error(errorText(e));
      onLocalUpdate(t);
    }
  };
  const toggle = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  return (
    <div className="ck-list" data-testid="kanban-list">
      {statuses.map((col) => {
        const items = tasks.filter((t) => t.status === col.name).sort(byOrder);
        if (!items.length) return null;
        const hidden = collapsed[col.id];
        return (
          <section key={col.id} className="ck-group" data-testid={`list-group-${slug(col.name)}`}>
            <header
              className="ck-group-head"
              onClick={() => setCollapsed({ ...collapsed, [col.id]: !hidden })}
            >
              {hidden ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
              <span className="ck-status-pill" style={{ background: col.color }}>
                {col.name}
              </span>
              <span className="ck-col-count">{items.length}</span>
            </header>
            {!hidden && (
              <table className="ck-table">
                <thead>
                  <tr>
                    {manager && <th style={{ width: 36 }} />}
                    <th>Task</th>
                    <th>PIC</th>
                    <th>Prioritas</th>
                    <th>Target</th>
                    <th>Status</th>
                    <th>Waktu</th>
                    <th>Sumber</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((t) => {
                    const editable = canEditTask(user, t);
                    const movable = canMoveTask(user);
                    return (
                      <tr key={t.id} data-testid={`task-row-${t.id}`}>
                        {manager && (
                          <td data-label="Pilih" className="ck-td-select">
                            <input
                              type="checkbox"
                              data-testid={`select-task-${t.id}`}
                              checked={selected.includes(t.id)}
                              onChange={() => toggle(t.id)}
                            />
                          </td>
                        )}
                        <td className="ck-td-title" role="button" tabIndex={0} data-testid={`open-task-row-${t.id}`} onKeyDown={e => e.key === 'Enter' && onOpen(t.id)} onClick={() => onOpen(t.id)}>
                          <b>{t.title}</b>
                          {t.blocked_count > 0 && <small className="ck-blocked" data-testid={`row-blocked-${t.id}`}>Menunggu {t.blocked_count} prasyarat</small>}
                          {t.tags?.length > 0 && (
                            <span className="ck-tags inline">
                              {t.tags.map((g) => (
                                <span className="ck-tag" key={g}>
                                  {g}
                                </span>
                              ))}
                            </span>
                          )}
                          {t.subtasks?.length > 0 && (
                            <small>
                              {t.subtasks.filter((s) => s.done).length}/{t.subtasks.length} subtask
                            </small>
                          )}
                        </td>
                        <td data-label="PIC">
                          <MultiAssigneeSelect testId={`row-assignee-${t.id}`} people={team} value={taskAssigneeIds(t)} selectedPeople={t.assignees || []} disabled={!manager} onChange={ids => patch(t, { assignee_ids: ids })} />
                        </td>
                        <td data-label="Prioritas">
                          <span className="ck-row-person" style={{ color: PRIORITY_COLOR[t.priority] }}>
                            <Flag size={14} fill="currentColor" />
                            {manager ? (
                              <select
                                className="ck-inline"
                                data-testid={`row-priority-${t.id}`}
                                value={t.priority}
                                onChange={(e) => patch(t, { priority: e.target.value })}
                              >
                                {PRIORITIES.map((p) => (
                                  <option key={p}>{p}</option>
                                ))}
                              </select>
                            ) : (
                              t.priority
                            )}
                          </span>
                        </td>
                        <td data-label="Target" className={isOverdue(statuses, t) ? "ck-overdue" : ""}>
                          {manager ? (
                            <input
                              type="date"
                              className="ck-inline"
                              data-testid={`row-due-${t.id}`}
                              value={t.due_date || ""}
                              onChange={(e) => patch(t, { due_date: e.target.value || null })}
                            />
                          ) : (
                            dateLabel(t.due_date)
                          )}
                        </td>
                        <td data-label="Status">
                          {movable ? (
                            <select
                              className="ck-inline ck-inline-status"
                              data-testid={`row-status-${t.id}`}
                              style={{ background: col.color }}
                              value={t.status}
                              onChange={(e) => patch(t, { status: e.target.value })}
                            >
                              {statuses.map((s) => (
                                <option key={s.id}>{s.name}</option>
                              ))}
                            </select>
                          ) : (
                            <span className="ck-status-pill" style={{ background: col.color }}>
                              {t.status}
                            </span>
                          )}
                        </td>
                        <td data-label="Waktu" data-testid={`row-time-${t.id}`}>{t.time_total ? fmtDuration(t.time_total) : "—"}</td>
                        <td data-label="Sumber" data-testid={`row-source-${t.id}`}>
                          <span className={`ck-source src-${t.source}`}>{SOURCE_LABEL[t.source]}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </section>
        );
      })}
      {!tasks.length && <Empty message="Belum ada task yang sesuai." />}
      {selected.length > 0 && (
        <BulkBar
          ids={selected}
          project={project}
          statuses={statuses}
          team={team}
          clear={() => setSelected([])}
          reload={reload}
        />
      )}
    </div>
  );
};
