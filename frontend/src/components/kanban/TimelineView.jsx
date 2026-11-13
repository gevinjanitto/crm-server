import React, { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, CalendarDays, Link2 } from 'lucide-react';
import { addDays, differenceInCalendarDays, format, parseISO, startOfWeek } from 'date-fns';
import { id as indonesia } from 'date-fns/locale';
import { colorOf, isOverdue, shortDate } from './helpers';

export const TimelineView = ({ tasks, statuses, onOpen }) => {
  const [start, setStart] = useState(() => startOfWeek(new Date(), { weekStartsOn: 1 }));
  const [span, setSpan] = useState(14);
  const end = addDays(start, span - 1);
  const days = Array.from({ length: span }, (_, i) => addDays(start, i));
  const scheduled = useMemo(() => tasks.filter(t => t.start_date || t.due_date).sort((a, b) => (a.start_date || a.due_date).localeCompare(b.start_date || b.due_date)), [tasks]);
  const unscheduled = tasks.filter(t => !t.start_date && !t.due_date);
  const visible = scheduled.filter(t => (t.start_date || t.due_date) <= format(end, 'yyyy-MM-dd') && (t.due_date || t.start_date) >= format(start, 'yyyy-MM-dd'));
  const todayOffset = differenceInCalendarDays(new Date(), start);
  return <section className="ck-timeline" data-testid="timeline-view">
    <header className="ck-timeline-toolbar">
      <div className="ck-timeline-nav"><button className="ck-icon" data-testid="timeline-prev" title="Periode sebelumnya" onClick={() => setStart(addDays(start, -span))}><ChevronLeft size={17} /></button><b data-testid="timeline-range">{format(start, 'd MMM', { locale: indonesia })} – {format(end, 'd MMM yyyy', { locale: indonesia })}</b><button className="ck-icon" data-testid="timeline-next" title="Periode berikutnya" onClick={() => setStart(addDays(start, span))}><ChevronRight size={17} /></button></div>
      <div className="ck-timeline-controls"><button className="ck-clear" data-testid="timeline-today" onClick={() => setStart(startOfWeek(new Date(), { weekStartsOn: 1 }))}>Hari ini</button><input type="date" className="ck-select" data-testid="timeline-date" aria-label="Awal periode" value={format(start, 'yyyy-MM-dd')} onChange={e => e.target.value && setStart(parseISO(e.target.value))} /><select className="ck-select" data-testid="timeline-scale" aria-label="Rentang timeline" value={span} onChange={e => setSpan(Number(e.target.value))}><option value={7}>7 hari</option><option value={14}>14 hari</option><option value={30}>30 hari</option></select></div>
    </header>
    <div className="ck-timeline-head"><span data-testid="timeline-task-label">TASK <small data-testid="timeline-visible-count">{visible.length} terjadwal</small></span><div className={`ck-timeline-days span-${span}`} style={{ gridTemplateColumns: `repeat(${span}, minmax(0, 1fr))` }}>{days.map((day, i) => <div data-testid={`timeline-day-${format(day, 'yyyy-MM-dd')}`} className={i === todayOffset ? 'today' : ''} key={i}><small>{format(day, 'EE', { locale: indonesia })}</small><b>{format(day, 'd')}</b></div>)}</div></div>
    <div className="ck-timeline-body">
      {visible.map(t => {
        const left = Math.max(0, differenceInCalendarDays(parseISO(t.start_date || t.due_date), start));
        const right = Math.min(span - 1, differenceInCalendarDays(parseISO(t.due_date || t.start_date), start));
        return <div key={t.id} className="ck-timeline-row" data-testid={`timeline-row-${t.id}`}>
          <button className="ck-timeline-task" data-testid={`timeline-open-${t.id}`} onClick={() => onOpen(t.id)}><i style={{ background: colorOf(statuses, t.status) }} /><span><b>{t.title}</b><small className={isOverdue(statuses, t) ? 'ck-overdue' : ''}>{shortDate(t.start_date || t.due_date)}{t.due_date && t.start_date && ` – ${shortDate(t.due_date)}`}</small></span>{t.dependencies?.length > 0 && <Link2 size={13} />}</button>
          <div className="ck-timeline-track" style={{ '--day-width': `${100 / span}%` }}>
            {todayOffset >= 0 && todayOffset < span && <i className="ck-today-line" style={{ left: `${(todayOffset + 0.5) / span * 100}%` }} />}
            <button className={`ck-timeline-bar ${t.blocked_count ? 'blocked' : ''}`} style={{ left: `${left / span * 100}%`, width: `${(right - left + 1) / span * 100}%`, backgroundColor: colorOf(statuses, t.status) }} data-testid={`timeline-bar-${t.id}`} onClick={() => onOpen(t.id)} title={`${t.title} · ${t.status}${t.blocked_count ? ' · Menunggu prasyarat' : ''}`}><span>{t.title}</span></button>
          </div>
        </div>;
      })}
      {!visible.length && <div className="ck-timeline-empty" data-testid="timeline-empty"><CalendarDays size={27} /><b>Tidak ada task pada periode ini</b>{scheduled.length > 0 && <button className="ck-clear" data-testid="timeline-first-task" onClick={() => setStart(startOfWeek(parseISO(scheduled[0].start_date || scheduled[0].due_date), { weekStartsOn: 1 }))}>Lihat jadwal task pertama</button>}</div>}
    </div>
    {unscheduled.length > 0 && <div className="ck-unscheduled"><h4 data-testid="timeline-unscheduled-count">Belum dijadwalkan <span>{unscheduled.length}</span></h4><div>{unscheduled.map(t => <button className="ck-unscheduled-task" key={t.id} data-testid={`unscheduled-${t.id}`} onClick={() => onOpen(t.id)}><i style={{ background: colorOf(statuses, t.status) }} />{t.title}</button>)}</div></div>}
  </section>;
};