import React from "react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { AtSign, SquareCheck, FileText, MessageSquare, Ticket, X } from "lucide-react";
import { api, errorText, useData } from "../lib/api";

const rowStyle = { display: "flex", gap: 12, alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--line)", color: "inherit" };
const ICON = { notes: FileText, task_comment: MessageSquare, ticket_comment: Ticket };
const Wrap = ({ m, children }) => m.can_open
  ? <Link to={m.link} data-testid={`mention-note-link-${m.id}`} style={rowStyle}>{children}</Link>
  : <div data-testid={`mention-note-static-${m.id}`} title="Anda tidak punya akses membuka notes ini" style={rowStyle}>{children}</div>;

const MentionRow = ({ m, onRemove }) => {
  const Icon = m.checklist ? SquareCheck : ICON[m.source] || FileText;
  return (
    <li data-testid={`mention-note-${m.id}`} style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}><Wrap m={m}>
        <Icon size={16} color={m.checklist ? "#2563eb" : "#87909e"} />
        <span style={{ flex: 1, minWidth: 0 }}>
          <b style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.text}</b>
          <small className="note-meta">{m.project_name} · {m.location}{m.updated_by ? ` · oleh ${m.updated_by}` : ""}</small>
        </span>
        <span className="note-badge" data-testid={`mention-source-${m.id}`}>{m.source_label}</span>
        {!m.can_open && <span className="note-badge" data-testid={`mention-note-noaccess-${m.id}`}>Tanpa akses notes</span>}
        {m.checklist && <span className="note-badge" data-testid={`mention-note-badge-${m.id}`}>Checklist</span>}
      </Wrap></div>
      {m.source !== "notes" && (
        <button type="button" className="icon-button danger" title="Hapus mention" data-testid={`mention-remove-${m.id}`} onClick={() => onRemove(m)}><X size={15} /></button>
      )}
    </li>
  );
};

export const MentionNotes = () => {
  const { data, loading, reload } = useData("/mentions/mine");
  const [removed, setRemoved] = React.useState([]);
  const rows = (data || []).filter((m) => !removed.includes(m.id));
  const remove = async (m) => {
    setRemoved((r) => [...r, m.id]);
    try { await api.delete(`/mentions/mine/${encodeURIComponent(m.id)}`); toast.success("Mention dihapus"); }
    catch (e) { setRemoved((r) => r.filter((x) => x !== m.id)); toast.error(errorText(e)); reload(); }
  };
  return (
    <section className="panel panel-padding" data-testid="dashboard-mention-notes" style={{ marginBottom: 18 }}>
      <div className="section-heading">
        <div>
          <h2 data-testid="mention-notes-title">Mention <span className="sample-tag" style={{ marginLeft: 8 }} data-testid="mention-notes-count">{rows.length} mention</span></h2>
          <p>Semua tempat Anda di-mention: notes, komentar task dan komentar tiket.</p>
        </div>
      </div>
      {loading ? <p className="form-note">Memuat mention...</p> : !rows.length ? (
        <p className="form-note" data-testid="mention-notes-empty"><AtSign size={14} style={{ verticalAlign: "-2px" }} /> Tidak ada mention.</p>
      ) : (
        <ul data-testid="mention-notes-list" className="dash-list-3" style={{ overflow: "auto", margin: 0, padding: 0, listStyle: "none" }}>
          {rows.map((m) => <MentionRow key={m.id} m={m} onRemove={remove} />)}
        </ul>
      )}
    </section>
  );
};
