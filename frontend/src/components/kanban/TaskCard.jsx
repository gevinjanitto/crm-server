import React from "react";
import {
  Flag,
  CalendarDays,
  MessageSquare,
  Paperclip,
  CheckSquare,
  Clock,
  Server,
  Link2,
} from "lucide-react";
import { initials } from "../../lib/api";
import {
  PRIORITY_COLOR,
  SOURCE_LABEL,
  isOverdue,
  fmtDuration,
  shortDate,
} from "./helpers";

export const Avatar = ({ name, size = 26 }) =>
  name ? (
    <span
      className="ck-avatar"
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      title={name}
    >
      {initials(name)}
    </span>
  ) : (
    <span
      className="ck-avatar empty"
      style={{ width: size, height: size }}
      title="Belum ditugaskan"
    />
  );

export const TaskCard = ({
  t,
  statuses,
  dragging,
  nodeRef,
  style,
  handle,
  dragListeners,
  onOpen,
}) => {
  const subs = t.subtasks || [],
    done = subs.filter((s) => s.done).length,
    overdue = isOverdue(statuses, t);
  return (
    <article
      ref={nodeRef}
      style={style}
      {...dragListeners}
      className={`ck-card ${dragging ? "dragging" : ""}`}
      data-testid={`task-card-${t.id}`}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(t.id); } }}
      onClick={() => !dragging && onOpen(t.id)}
    >
      {handle}
      {t.source !== "manual" && (
        <span className={`ck-source src-${t.source}`}>
          {SOURCE_LABEL[t.source]}
        </span>
      )}
      <h4 className="ck-card-title" data-testid={`task-title-${t.id}`}>{t.title}</h4>
      {t.milestone && <span className="pw-milestone-badge" data-testid={`task-milestone-${t.id}`}>◆ Milestone</span>}
      {t.blocked_count > 0 && <span className="ck-blocked" data-testid={`task-blocked-${t.id}`}><Link2 size={12} /> Menunggu {t.blocked_count} prasyarat</span>}
      {t.tags?.length > 0 && (
        <div className="ck-tags">
          {t.tags.map((g) => (
            <span className="ck-tag" key={g}>
              {g}
            </span>
          ))}
        </div>
      )}
      <div className="ck-card-foot">
        <span className="ck-avatar-stack" data-testid={`task-people-${t.id}`}>{t.assignees?.length ? t.assignees.slice(0, 3).map(person => <Avatar key={person.id} name={person.name} />) : <Avatar name={t.assigned_name} />}{t.assignees?.length > 3 && <small>+{t.assignees.length - 3}</small>}</span>
        <span
          className="ck-flag"
          title={`Prioritas ${t.priority}`}
          style={{ color: PRIORITY_COLOR[t.priority] }}
        >
          <Flag size={14} fill="currentColor" />
        </span>
        {t.due_date && (
          <span
            className={`ck-meta ${overdue ? "overdue" : ""}`}
            data-testid={`task-due-${t.id}`}
          >
            <CalendarDays size={13} /> {shortDate(t.due_date)}
          </span>
        )}
        {t.server !== "Belum Naik" && (
          <span className={`ck-meta srv-${t.server === "Production" ? "prod" : "dev"}`}>
            <Server size={12} /> {t.server === "Production" ? "Prod" : "Dev"}
          </span>
        )}
        <span className="ck-spacer" />
        {subs.length > 0 && (
          <span
            className={`ck-meta ${done === subs.length ? "ok" : ""}`}
            data-testid={`task-subtasks-${t.id}`}
          >
            <CheckSquare size={13} /> {done}/{subs.length}
          </span>
        )}
        {t.comment_count > 0 && (
          <span className="ck-meta">
            <MessageSquare size={13} /> {t.comment_count}
          </span>
        )}
        {t.document_count > 0 && (
          <span className="ck-meta">
            <Paperclip size={13} /> {t.document_count}
          </span>
        )}
        {(t.time_total > 0 || t.running_count > 0) && (
          <span className={`ck-meta ${t.running_count ? "running" : ""}`}>
            <Clock size={13} /> {fmtDuration(t.time_total)}
          </span>
        )}
      </div>
    </article>
  );
};
