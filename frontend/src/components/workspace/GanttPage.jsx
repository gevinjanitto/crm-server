import React, { useEffect, useRef, useState } from 'react';
import Gantt from 'frappe-gantt';
import '../../../node_modules/frappe-gantt/dist/frappe-gantt.css';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { Flag, CalendarDays } from 'lucide-react';
import { api, errorText } from '../../lib/api';
import { toast } from 'sonner';
import { isDone } from '../kanban/helpers';
import { WorkspaceHead, EmptyWorkspace } from './WorkspaceUI';

const escapeHtml = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
export const GanttPage = ({ p, tasks, statuses, manager, reload }) => {
  const ref = useRef(null), chart = useRef(null), navigate = useNavigate();
  const [mode, setMode] = useState('Week'), [busy, setBusy] = useState(false);
  const scheduled = tasks.filter(t => t.start_date || t.due_date), unscheduled = tasks.filter(t => !t.start_date && !t.due_date);
  useEffect(() => {
    if (!ref.current || !scheduled.length) return;
    ref.current.replaceChildren();
    const ids = new Set(scheduled.map(t => t.id));
    const data = scheduled.map(t => ({ id: t.id, name: escapeHtml(`${t.milestone ? '◆ ' : ''}${t.title}`), start: t.start_date || t.due_date, end: t.due_date || t.start_date, progress: isDone(statuses, t) ? 100 : t.subtasks?.length ? Math.round(t.subtasks.filter(s => s.done).length / t.subtasks.length * 100) : 0, dependencies: (t.dependencies || []).filter(id => ids.has(id)).join(','), custom_class: t.milestone ? 'pw-gantt-milestone' : isDone(statuses, t) ? 'pw-gantt-done' : '' }));
    const first = data.reduce((a, t) => t.start < a ? t.start : a, data[0].start);
    chart.current = new Gantt(ref.current, data, { view_mode: mode, readonly: !manager, readonly_progress: true, move_dependencies: false, infinite_padding: false, container_height: 460, popup: false, today_button: false, scroll_to: first, language: 'id', bar_height: 28, padding: 20,
      on_click: t => navigate(`/projects/${p.id}/kanban?task=${t.id}`),
      on_date_change: async (t, start, end) => { setBusy(true); try { await api.patch(`/projects/${p.id}/tasks/${t.id}`, { start_date: format(start, 'yyyy-MM-dd'), due_date: format(end, 'yyyy-MM-dd') }); toast.success('Jadwal task diperbarui'); } catch (e) { toast.error(errorText(e)); } finally { await reload(); setBusy(false); } },
    });
    ref.current.querySelectorAll('.bar-wrapper').forEach(el => { const id = el.getAttribute('data-id'); el.setAttribute('data-testid', `gantt-bar-${id}`); el.setAttribute('tabindex', '0'); el.setAttribute('role', 'button'); el.setAttribute('aria-label', scheduled.find(t => t.id === id)?.title || 'Task'); el.onkeydown = e => { if (e.key === 'Enter') navigate(`/projects/${p.id}/kanban?task=${id}`); }; });
    return () => { if (chart.current?.$container) chart.current.$container.innerHTML = ''; chart.current = null; };
  // The project reload replaces the task array after a date change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, statuses, mode, manager, p.id]);
  return <div data-testid="gantt-page"><WorkspaceHead id="gantt" title="Gantt" subtitle={`${scheduled.length} task terjadwal · ${tasks.filter(t => t.milestone).length} milestone`}><span className="pw-muted" data-testid="gantt-save-status">{busy ? 'Menyimpan jadwal…' : ''}</span><div className="pw-segmented">{[['Day', 'Harian'], ['Week', 'Mingguan'], ['Month', 'Bulanan']].map(([v, l]) => <button key={v} data-testid={`gantt-scale-${v.toLowerCase()}`} className={mode === v ? 'active' : ''} onClick={() => setMode(v)}>{l}</button>)}</div></WorkspaceHead>{scheduled.length ? <div className="pw-gantt-chart" ref={ref} data-testid="gantt-chart" /> : <EmptyWorkspace title="Belum ada task terjadwal" id="gantt-empty" />}
    <section className="pw-section"><h3 data-testid="gantt-unscheduled-heading">Belum dijadwalkan <span className="pw-muted">{unscheduled.length}</span></h3><div className="pw-unscheduled-list">{unscheduled.map(t => <button key={t.id} data-testid={`gantt-unscheduled-${t.id}`} onClick={() => navigate(`/projects/${p.id}/kanban?task=${t.id}`)}>{t.milestone ? <Flag size={15} /> : <CalendarDays size={15} />}{t.title}</button>)}{!unscheduled.length && <p className="pw-muted" data-testid="gantt-all-scheduled">Semua task sudah memiliki jadwal.</p>}</div></section>
  </div>;
};