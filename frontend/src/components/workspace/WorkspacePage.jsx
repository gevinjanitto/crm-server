import React, { lazy, Suspense } from 'react';
import { useData } from '../../lib/api';
import { Loading, ErrorState } from '../Common';
import { isManager } from '../kanban/helpers';
import './workspace.css';
const page = (file, name) => lazy(() => file().then(m => ({ default: m[name] })));
const Structure = page(() => import('./StructurePage'), 'StructurePage');
const Docs = page(() => import('./DocsPage'), 'DocsPage');
const Whiteboard = page(() => import('./WhiteboardPage'), 'WhiteboardPage');
const Sprints = page(() => import('./SprintsPage'), 'SprintsPage');
const Goals = page(() => import('./GoalsPage'), 'GoalsPage');
const Automations = page(() => import('./AutomationsPage'), 'AutomationsPage');
const Workload = page(() => import('./WorkloadPage'), 'WorkloadPage');
const Reports = page(() => import('./ReportsPage'), 'ReportsPage');
const Gantt = page(() => import('./GanttPage'), 'GanttPage');
const Reminders = page(() => import('../ProjectReminders'), 'ProjectReminders');
const pages = { reminder: Reminders, struktur: Structure, docs: Docs, whiteboard: Whiteboard, sprint: Sprints, goals: Goals, automasi: Automations, kapasitas: Workload, laporan: Reports, gantt: Gantt };

export const WorkspacePage = ({ p, user, section }) => {
  const meta = useData(`/projects/${p.id}/workspace/meta`), tasks = useData(`/projects/${p.id}/tasks`), statuses = useData(`/projects/${p.id}/statuses`);
  const reload = async () => { await Promise.all([meta.reload(), tasks.reload(), statuses.reload()]); };
  if (meta.error || tasks.error || statuses.error) return <ErrorState error={meta.error || tasks.error || statuses.error} reload={reload} />;
  if (!meta.data || !tasks.data || !statuses.data) return <Loading />;
  const Component = pages[section]; if (!Component) return null;
  return <div className="pw-root" data-testid={`workspace-section-${section}`}><Suspense fallback={<Loading />}><Component p={p} user={user} meta={meta.data} tasks={tasks.data} statuses={statuses.data} manager={isManager(user)} reload={reload} /></Suspense></div>;
};