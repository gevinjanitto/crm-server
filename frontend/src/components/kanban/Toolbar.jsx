import React from "react";
import {
  LayoutGrid,
  List as ListIcon,
  CalendarDays,
  Search,
  Plus,
  X,
  CalendarRange,
  UserRound,
  Clock3,
} from "lucide-react";
import { PRIORITIES } from "./helpers";

const VIEWS = [
  ["board", "Board", LayoutGrid],
  ["list", "List", ListIcon],
  ["calendar", "Kalender", CalendarDays],
  ["timeline", "Timeline", CalendarRange],
];

export const Toolbar = ({
  view,
  setView,
  filters,
  setFilters,
  people,
  tags,
  manager,
  onCreate,
  total,
  statuses,
  onReset,
  sprints = [],
  dashboardOnly = false,
}) => {
  const set = (k, v) => setFilters({ ...filters, [k]: v });
  const active = Object.values(filters).some(Boolean);
  return (
    <div className="ck-toolbar">
      <div className="ck-views" data-testid="kanban-views">
        {!dashboardOnly && VIEWS.map(([id, label, Icon]) => (
          <button
            key={id}
            data-testid={`kanban-view-${id}`}
            className={`ck-view-btn ${view === id ? "active" : ""}`}
            onClick={() => setView(id)}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
        <span className="ck-total" data-testid="kanban-total">
          {total} task
        </span>
      </div>
      <div className="ck-filters">
        <select className="ck-select" data-testid="kanban-sprint-filter" aria-label="Filter sprint" value={filters.sprint_id || ''} onChange={e => set('sprint_id', e.target.value)}><option value="">Semua sprint</option><option value="none">Backlog</option>{sprints.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <button className={`ck-quick-filter ${filters.milestone ? 'active' : ''}`} data-testid="kanban-milestone-filter" aria-pressed={filters.milestone} onClick={() => set('milestone', !filters.milestone)}>◆ Milestone</button>
        <button className={`ck-quick-filter ${filters.mine ? 'active' : ''}`} data-testid="kanban-my-tasks" aria-pressed={filters.mine} onClick={() => setFilters({ ...filters, mine: !filters.mine, assignee: '' })}><UserRound size={15} /> Tugas saya</button>
        <button className={`ck-quick-filter overdue ${filters.overdue ? 'active' : ''}`} data-testid="kanban-overdue-filter" aria-pressed={filters.overdue} onClick={() => set('overdue', !filters.overdue)}><Clock3 size={15} /> Terlambat</button>
        <label className="ck-search">
          <Search size={16} />
          <input
            data-testid="kanban-search"
            placeholder="Cari task..."
            value={filters.q}
            onChange={(e) => set("q", e.target.value)}
          />
        </label>
        <select
          className="ck-select"
          data-testid="kanban-assignee-filter"
          value={filters.assignee}
          onChange={(e) => set("assignee", e.target.value)}
        >
          <option value="">Semua PIC</option>
          <option value="none">Belum ditugaskan</option>
          {people.map(([id, name]) => (
            <option key={id} value={id}>
              {name}
            </option>
          ))}
        </select>
        <select className="ck-select" data-testid="kanban-status-filter" aria-label="Filter status" value={filters.status} onChange={e => set('status', e.target.value)}><option value="">Semua status</option>{statuses.map(s => <option key={s.id}>{s.name}</option>)}</select>
        <select
          className="ck-select"
          data-testid="kanban-priority-filter"
          value={filters.priority}
          onChange={(e) => set("priority", e.target.value)}
        >
          <option value="">Semua prioritas</option>
          {PRIORITIES.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        {tags.length > 0 && (
          <select
            className="ck-select"
            data-testid="kanban-tag-filter"
            value={filters.tag}
            onChange={(e) => set("tag", e.target.value)}
          >
            <option value="">Semua tag</option>
            {tags.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        )}
        {active && (
          <button
            className="ck-clear"
            data-testid="kanban-clear-filters"
            onClick={onReset}
          >
            <X size={14} /> Reset
          </button>
        )}
        {manager && (
          <button
            className="ck-primary"
            data-testid="add-task"
            onClick={onCreate}
          >
            <Plus size={16} /> Task baru
          </button>
        )}
      </div>
    </div>
  );
};
