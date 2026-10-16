import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';
import { toast } from "sonner";
import { api, errorText } from "../lib/api";
import { Toolbar } from "./kanban/Toolbar";
import { BoardView } from "./kanban/BoardView";
import { ListView } from "./kanban/ListView";
import { CalendarView } from "./kanban/CalendarView";
import { DashboardView } from "./kanban/DashboardView";
import { TimelineView } from "./kanban/TimelineView";
import { SavedViews } from "./kanban/SavedViews";
import { TaskDetail } from "./kanban/TaskDetail";
import { TaskForm } from "./TaskModal";
import { isManager, taskAssigneeIds, isOverdue, isDone } from "./kanban/helpers";
import "./kanban/workspace.css";
import { descendantLists } from './workspace/SpaceSidebar';
import './workspace/workspace.css';

export const EMPTY_FILTERS = { q: "", assignee: "", priority: "", tag: "", status: "", mine: false, overdue: false, list_id: '', sprint_id: '', milestone: false };

export const KanbanBoard = ({ project, tasks, setTasks, statuses, setStatuses, user, team, reload, dashboardOnly = false, workspace = { nodes: [], sprints: [], templates: [] } }) => {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [view, setView] = useState(() => dashboardOnly ? 'dashboard' : ['board', 'list', 'calendar', 'timeline'].includes(localStorage.getItem('ck-view')) ? localStorage.getItem('ck-view') : 'board'),
    [filters, setFilters] = useState({ ...EMPTY_FILTERS, list_id: params.get('list') || '', assignee: params.get('assignee') || '', ...location.state?.taskFilters }),
    [selected, selectTask] = useState(params.get('task')),
    [creating, setCreating] = useState(false);
  const manager = isManager(user);
  useEffect(() => { selectTask(params.get('task')); }, [params]);
  const setSelected = id => { selectTask(id); setParams(previous => { const next = new URLSearchParams(previous); if (id) next.set('task', id); else { next.delete('task'); next.delete('comment'); } return next; }, { replace: true }); };
  const listIds = descendantLists(workspace.nodes, filters.list_id);
  const changeView = (v, nextFilters = filters) => {
    if (v === 'dashboard' && !dashboardOnly) {
      navigate(`/projects/${project.id}/dashboard`, { state: { taskFilters: nextFilters } });
      return;
    }
    if (dashboardOnly) {
      if (v !== 'dashboard') {
        localStorage.setItem('ck-view', v);
        navigate(`/projects/${project.id}/kanban`, { state: { taskFilters: nextFilters } });
      }
      return;
    }
    localStorage.setItem("ck-view", v);
    setView(v);
  };
  const people = useMemo(
    () => [...new Map(tasks.flatMap((t) => t.assignees || (t.assigned_to ? [{ id: t.assigned_to, name: t.assigned_name }] : [])).map(p => [p.id, p.name])).entries()],
    [tasks],
  );
  const tags = useMemo(() => [...new Set(tasks.flatMap((t) => t.tags || []))].sort(), [tasks]);
  const enriched = tasks.map(t => ({ ...t, blocked_count: (t.dependencies || []).filter(id => tasks.some(other => other.id === id && !isDone(statuses, other))).length }));
  const rows = enriched.filter(
    (t) =>
      (!filters.list_id || (filters.list_id === 'none' ? !t.list_id : listIds.includes(t.list_id))) &&
      (!filters.sprint_id || (filters.sprint_id === 'none' ? !t.sprint_id : t.sprint_id === filters.sprint_id)) &&
      (!filters.milestone || t.milestone) &&
      (!filters.assignee || (filters.assignee === "none" ? !taskAssigneeIds(t).length : taskAssigneeIds(t).includes(filters.assignee))) &&
      (!filters.mine || taskAssigneeIds(t).includes(user.id) || (t.subtasks || []).some(s => s.assigned_to === user.id)) &&
      (!filters.overdue || isOverdue(statuses, t)) &&
      (!filters.status || t.status === filters.status) &&
      (!filters.priority || t.priority === filters.priority) &&
      (!filters.tag || (t.tags || []).includes(filters.tag)) &&
      (t.title + " " + (t.description || "") + " " + (t.tags || []).join(" ")).toLowerCase().includes(filters.q.toLowerCase()),
  );
  const onLocalUpdate = (t) => setTasks((list) => list.map((x) => (x.id === t.id ? { ...x, ...t } : x)));
  const onAdded = (t) => setTasks((list) => [...list, t]);
  const onDelete = async (t) => {
    try {
      await api.delete(`/projects/${project.id}/tasks/${t.id}`);
      setTasks((list) => list.filter((x) => x.id !== t.id).map(x => ({ ...x, dependencies: (x.dependencies || []).filter(id => id !== t.id) })));
      setSelected(null);
      toast.success("Task dihapus");
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  const current = selected && tasks.find((t) => t.id === selected);
  const common = { project, tasks: rows, statuses, user, manager, team, onOpen: setSelected, onLocalUpdate, reload };
  return (
    <div className="ck-root" data-testid="kanban-workspace">
      <div className="pw-kanban-main">
      {dashboardOnly && <h2 className="detail-heading" data-testid="project-dashboard-heading">Dashboard Project</h2>}
      <Toolbar
        dashboardOnly={dashboardOnly}
        view={view}
        setView={changeView}
        filters={filters}
        setFilters={setFilters}
        people={people}
        tags={tags}
        manager={manager}
        onCreate={() => setCreating(true)}
        total={rows.length}
        statuses={statuses}
        sprints={workspace.sprints}
        onReset={() => setFilters(EMPTY_FILTERS)}
      />
      <SavedViews projectId={project.id} filters={filters} view={view} onApply={item => { const next = { ...EMPTY_FILTERS, ...item.filters }; setFilters(next); changeView(item.view, next); }} />
      {view === "board" && <BoardView {...common} setStatuses={setStatuses} onAdded={onAdded} />}
      {view === "list" && <ListView {...common} />}
      {view === "calendar" && <CalendarView {...common} />}
      {view === "timeline" && <TimelineView {...common} />}
      {view === "dashboard" && <DashboardView tasks={rows} statuses={statuses} />}
      </div>
      {current && (
        <TaskDetail
          key={current.id}
          task={current}
          tasks={tasks}
          project={project}
          user={user}
          team={team}
          statuses={statuses}
          onClose={() => setSelected(null)}
          onChange={onLocalUpdate}
          onDelete={onDelete}
          onOpen={setSelected}
          onDuplicate={(t) => { onAdded(t); setSelected(t.id); }}
        />
      )}
      <TaskForm
        open={creating}
        onClose={() => setCreating(false)}
        projectId={project.id}
        team={team}
        lists={workspace.nodes.filter(n => n.kind === 'list')}
        defaultList={workspace.nodes.some(n => n.id === filters.list_id && n.kind === 'list') ? filters.list_id : ''}
        statuses={statuses}
        onSaved={(t) => {
          onAdded(t);
          setSelected(t.id);
        }}
      />
    </div>
  );
};
