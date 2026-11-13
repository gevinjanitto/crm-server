import React, { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { api, errorText } from "../../lib/api";
import { colorOf, canEditTask, PRIORITY_COLOR } from "./helpers";
import { format } from "date-fns";

const DAYS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];
const iso = (d) => format(d, 'yyyy-MM-dd');

export const CalendarView = ({ project, tasks, statuses, user, onOpen, onLocalUpdate }) => {
  const [cursor, setCursor] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });
  const [drag, setDrag] = useState(null);
  const first = new Date(cursor),
    offset = (first.getDay() + 6) % 7,
    start = new Date(first);
  start.setDate(first.getDate() - offset);
  const cells = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
  const today = iso(new Date());
  const drop = async (day) => {
    if (!drag) return;
    const t = drag;
    setDrag(null);
    if (t.due_date === day) return;
    onLocalUpdate({ ...t, due_date: day });
    try {
      const r = await api.patch(`/projects/${project.id}/tasks/${t.id}`, { due_date: day });
      onLocalUpdate(r.data);
      toast.success("Target selesai diperbarui");
    } catch (e) {
      toast.error(errorText(e));
      onLocalUpdate(t);
    }
  };
  const manager = ["Admin", "Admin Project"].includes(user.role);
  return (
    <div className="ck-cal" data-testid="kanban-calendar">
      <header className="ck-cal-head">
        <button className="ck-icon" data-testid="cal-prev" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}>
          <ChevronLeft size={18} />
        </button>
        <b data-testid="cal-month">
          {cursor.toLocaleDateString("id-ID", { month: "long", year: "numeric" })}
        </b>
        <button className="ck-icon" data-testid="cal-next" onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}>
          <ChevronRight size={18} />
        </button>
        <button className="ck-clear" data-testid="cal-today" onClick={() => setCursor(new Date(new Date().getFullYear(), new Date().getMonth(), 1))}>
          Hari ini
        </button>
        <span className="ck-cal-note">
          {tasks.filter((t) => !t.due_date).length} task tanpa target tanggal
        </span>
      </header>
      <div className="ck-cal-grid">
        {DAYS.map((d) => (
          <div className="ck-cal-dow" key={d}>
            {d}
          </div>
        ))}
        {cells.map((d) => {
          const key = iso(d),
            items = tasks.filter((t) => t.due_date === key);
          return (
            <div
              key={key}
              className={`ck-cal-day ${d.getMonth() !== cursor.getMonth() ? "other" : ""} ${key === today ? "today" : ""} ${drag ? "droppable" : ""}`}
              data-testid={`cal-day-${key}`}
              onDragOver={(e) => manager && e.preventDefault()}
              onDrop={() => drop(key)}
            >
              <span className="ck-cal-num">{d.getDate()}</span>
              {items.map((t) => (
                <button
                  key={t.id}
                  className="ck-cal-task"
                  data-testid={`cal-task-${t.id}`}
                  draggable={manager && canEditTask(user, t)}
                  onDragStart={() => setDrag(t)}
                  onDragEnd={() => setDrag(null)}
                  style={{ borderLeftColor: colorOf(statuses, t.status) }}
                  onClick={() => onOpen(t.id)}
                  title={`${t.title} · ${t.status}`}
                >
                  <i style={{ background: PRIORITY_COLOR[t.priority] }} />
                  {t.title}
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
};
