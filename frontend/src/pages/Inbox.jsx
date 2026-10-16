import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, Search, ChevronDown, Trash2, Paperclip } from "lucide-react";
import { toast } from "sonner";
import { api, useData, initials, errorText } from "../lib/api";
import { PageHead, Loading, ErrorState, Empty } from "../components/Common";

const DAY = 86400000;
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
const groupOf = (iso) => {
  const d = new Date(iso), today = startOfDay(new Date());
  if (startOfDay(d) === today) return "Hari ini";
  if (today - startOfDay(d) < 7 * DAY) return "7 hari terakhir";
  return d.toLocaleDateString("id-ID", { month: "long", year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
};
const timeOf = (iso) => {
  const d = new Date(iso);
  return startOfDay(d) === startOfDay(new Date())
    ? d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("id-ID", { day: "numeric", month: "short" });
};

const StatusIcon = ({ item }) => item.status_kind === "done"
  ? <CheckCircle2 size={16} className="inbox-status done" style={{ color: item.status_color }} aria-label={item.task_status} />
  : <span className="inbox-status" style={{ "--status": item.status_color }} title={item.task_status} aria-label={item.task_status} />;

const Message = ({ text }) => (text || "").split(/(@[\w.-]+)/g).map((part, i) =>
  part.startsWith("@") ? <mark key={i} className="inbox-mention">{part}</mark> : part);

const Thread = ({ item, onOpen }) => (
  <div className="inbox-thread" data-testid={`inbox-thread-${item.task_id}`}>
    {item.comments.map((c) => (
      <button type="button" key={c.id} className="inbox-thread-item" data-testid={`inbox-thread-comment-${c.id}`} onClick={() => onOpen(item, c.id)}>
        <span className="avatar small inbox-avatar" title={c.author_name}>{initials(c.author_name)}</span>
        <span className="inbox-thread-body">
          <b>{c.author_name} <time dateTime={c.created_at}>{new Date(c.created_at).toLocaleString("id-ID", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</time></b>
          <span><Message text={c.message} />{!c.message && c.files > 0 && <em>Lampiran</em>}</span>
          {c.files > 0 && <small><Paperclip size={11} /> {c.files} lampiran</small>}
        </span>
      </button>
    ))}
  </div>
);

const InboxRow = ({ item, onOpen, onDelete, expanded, onToggle }) => (
  <div className={`inbox-item ${expanded ? "expanded" : ""}`}>
    <div className="inbox-row-line">
      <button type="button" className={`inbox-row ${item.unread ? "unread" : ""}`} onClick={() => onOpen(item)} data-testid={`inbox-row-${item.task_id}`}>
        <span className="inbox-task">
          <StatusIcon item={item} />
          <span><b data-testid={`inbox-task-title-${item.task_id}`}>{item.task_title}</b><small>{item.project_name}</small></span>
        </span>
        <span className="inbox-comment">
          <span className="avatar small inbox-avatar" title={item.author_name}>{initials(item.author_name)}</span>
          <span className="inbox-message" data-testid={`inbox-message-${item.task_id}`}><Message text={item.message} /></span>
        </span>
        <span className="inbox-count" title={`${item.count} komentar`} data-testid={`inbox-count-${item.task_id}`}>{item.count}</span>
        <time className="inbox-time" dateTime={item.created_at}>{timeOf(item.created_at)}</time>
      </button>
      <div className="inbox-actions">
        <button type="button" className="icon-button" title={expanded ? "Tutup semua komentar" : "Lihat semua komentar"} aria-expanded={expanded} data-testid={`inbox-expand-${item.task_id}`} onClick={onToggle}>
          <ChevronDown size={15} className={expanded ? "inbox-chevron open" : "inbox-chevron"} />
        </button>
        <button type="button" className="icon-button danger" title="Hapus dari inbox" data-testid={`inbox-delete-${item.task_id}`} onClick={() => onDelete(item)}>
          <Trash2 size={15} />
        </button>
      </div>
    </div>
    {expanded && <Thread item={item} onOpen={onOpen} />}
  </div>
);

export default function Inbox() {
  const { data, loading, error, reload, setData } = useData("/inbox"),
    [filter, setFilter] = useState("semua"),
    [q, setQ] = useState(""),
    [expanded, setExpanded] = useState({}),
    navigate = useNavigate();
  const groups = useMemo(() => {
    const rows = (data?.items || []).filter((r) => (filter === "semua" || r.unread) &&
      `${r.task_title} ${r.project_name} ${(r.comments || []).map((c) => `${c.author_name} ${c.message}`).join(" ")}`.toLowerCase().includes(q.toLowerCase()));
    return rows.reduce((acc, r) => {
      const g = groupOf(r.created_at);
      (acc.find((x) => x[0] === g) || acc[acc.push([g, []]) - 1])[1].push(r);
      return acc;
    }, []);
  }, [data, filter, q]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const open = (item, commentId = item.comment_id) => {
    api.post(`/inbox/${item.task_id}/read`).catch(() => {});
    navigate(`/projects/${item.project_id}/kanban?task=${item.task_id}&comment=${commentId}`);
  };
  const remove = async (item) => {
    if (!window.confirm(`Hapus "${item.task_title}" dari inbox? Komentar baru akan muncul lagi.`)) return;
    try {
      await api.delete(`/inbox/${item.task_id}`);
      const items = data.items.filter((r) => r.task_id !== item.task_id);
      setData ? setData({ items, unread: items.filter((r) => r.unread).length }) : reload();
      toast.success("Dihapus dari inbox");
    } catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div className="inbox-page" data-testid="inbox-page">
      <PageHead eyebrow="AKTIVITAS" title="Inbox"
        description={data.unread ? `${data.unread} task memiliki komentar baru.` : "Komentar terbaru dari semua task yang dapat Anda akses."} />
      <div className="list-toolbar">
        <div className="filter-tabs">
          {[["semua", "Semua"], ["baru", "Belum dibaca"]].map(([key, label]) => (
            <button key={key} className={`filter-tab ${filter === key ? "active" : ""}`} onClick={() => setFilter(key)} data-testid={`inbox-filter-${key}`}>
              {label}{key === "semua" && <span className="inbox-tab-count" data-testid="inbox-total-count">{data.items.length}</span>}{key === "baru" && data.unread > 0 && <span className="inbox-tab-count">{data.unread}</span>}
            </button>
          ))}
        </div>
        <div className="list-search">
          <Search size={15} />
          <input data-testid="inbox-search" placeholder="Cari task / komentar..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {groups.length ? groups.map(([label, rows]) => (
        <section key={label} className="inbox-group" data-testid={`inbox-group-${label.replace(/\s+/g, "-").toLowerCase()}`}>
          <h2>{label}</h2>
          <div className="inbox-list">{rows.map((item) => (
            <InboxRow key={item.task_id} item={item} onOpen={open} onDelete={remove}
              expanded={!!expanded[item.task_id]} onToggle={() => setExpanded((x) => ({ ...x, [item.task_id]: !x[item.task_id] }))} />
          ))}</div>
        </section>
      )) : <Empty message={filter === "baru" ? "Tidak ada komentar baru." : "Belum ada komentar di task."} />}
    </div>
  );
}
