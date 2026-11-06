import React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, CalendarDays, CheckCheck, Flag, Inbox, Pencil, Play, Trash2, UserRound } from "lucide-react";
import { Badge } from "./Common";
import { dateLabel, money } from "../lib/api";
import { RichDescription } from "./kanban/RichDescription";

const skip = "a,button,input,select,textarea,label";

export const WorkCard = ({ work: r, showProject, manager, onEdit, onRemove, onOpenTicket, onOpen }) => {
  const dates = [
    ["entry", "Tanggal masuk", r.entry_date || r.created_at, Inbox],
    ["started", "Dikerjakan", r.started_date, Play],
    ["due", "Target selesai", r.due_date, CalendarDays],
  ];
  return (
    <article className={`work-card ${onOpen ? "is-clickable" : ""}`} data-testid={`work-card-${r.id}`}
      role={onOpen ? "link" : undefined} tabIndex={onOpen ? 0 : undefined} title={onOpen ? "Buka detail di Kanban" : undefined}
      onClick={onOpen ? (e) => !e.target.closest(skip) && onOpen() : undefined}
      onKeyDown={onOpen ? (e) => e.key === "Enter" && e.target === e.currentTarget && onOpen() : undefined}>
      <header className="work-card-header">
        <div className="work-card-tags">
          <Badge id={`work-status-${r.id}`}>{r.status}</Badge>
          <span className="work-kind" data-testid={`work-kind-${r.id}`}>{r.kind}</span>
          {r.ticket_id && <Badge id={`work-ticket-status-${r.ticket_id}`}>{r.ticket_status}</Badge>}
        </div>
        {r.priority && <span className="work-priority" data-priority={r.priority} data-testid={`work-priority-${r.id}`}>
          <Flag size={12} aria-hidden="true" />{r.priority}
        </span>}
      </header>
      <div className="work-card-body">
        {showProject && <Link to={`/projects/${r.project_id}`} className="work-project-link" data-testid={`work-project-${r.id}`}>
          <span>{r.project_name}</span><ArrowUpRight size={13} aria-hidden="true" />
        </Link>}
        <h3 data-testid={`work-title-${r.id}`}>{r.title}</h3>
        {r.description_html && r.task_id ? (
          <div className="work-description work-description-rich" data-testid={`work-description-${r.id}`}>
            <RichDescription docKey={r.id} html={r.description_html} editable={false} preview={false}
              imagePath={(id) => `/projects/${r.project_id}/tasks/${r.task_id}/images/${id}`}
              ids={{ root: `work-description-view-${r.id}`, view: `work-description-content-${r.id}` }} />
          </div>
        ) : <p className="work-description" data-testid={`work-description-${r.id}`}>{r.description || "Belum ada deskripsi."}</p>}
      </div>
      <dl className="work-date-grid" data-testid={`work-dates-${r.id}`}>
        {dates.map(([key, label, value, Icon]) => <div key={key} data-testid={`work-date-${key}-${r.id}`}>
          <dt><Icon size={13} aria-hidden="true" />{label}</dt>
          <dd>{value ? dateLabel(value) : "Belum ditentukan"}</dd>
        </div>)}
      </dl>
      <footer className="work-card-footer">
        <div className="work-card-summary">
          <div className="work-assignee" data-testid={`work-assignee-${r.id}`}>
            <span className={`work-assignee-icon ${r.assigned_to ? "is-assigned" : ""}`} aria-hidden="true"><UserRound size={15} /></span>
            <span><small>Penanggung jawab</small><b data-testid={`work-assignee-name-${r.id}`}>{r.assignees?.length ? r.assignees.map((a) => a.name).join(", ") : r.assigned_to ? (r.assigned_name || "PIC ditugaskan") : "Belum ada PIC"}</b></span>
          </div>
          {r.estimate > 0 && <div className="work-estimate" data-testid={`work-estimate-${r.id}`}>
            <small>Estimasi biaya</small><b>{money(r.estimate)}</b>
          </div>}
        </div>
        {r.ticket_id && <button type="button" className="link-button" data-testid={`work-open-ticket-${r.ticket_id}`} onClick={() => onOpenTicket(r.ticket_id)}>{r.ticket_code} <ArrowUpRight size={14} /></button>}
        {manager && !r.ticket_id && <div className="work-card-actions">
          <button type="button" className="icon-button" data-testid={`edit-work-${r.id}`} title="Perbarui pekerjaan" aria-label={`Perbarui ${r.title}`} onClick={() => onEdit(r)}><Pencil size={15} /></button>
          <button type="button" className="icon-button danger" data-testid={`delete-work-${r.id}`} title="Pindahkan ke arsip" aria-label={`Arsipkan ${r.title}`} onClick={() => onRemove(r)}><Trash2 size={15} /></button>
        </div>}
      </footer>
      {r.completed_at && <div className="work-completed" data-testid={`work-completed-${r.id}`}><CheckCheck size={14} />Selesai pada {dateLabel(r.completed_at)}</div>}
    </article>
  );
};