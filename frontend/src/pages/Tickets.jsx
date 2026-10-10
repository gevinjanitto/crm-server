import React, { useState, useEffect } from "react";
import { Link, useSearchParams } from 'react-router-dom';
import {
  Search,
  Ticket,
  Clock3,
  CheckCheck,
  ArrowUpRight,
  Send,
  ArrowLeft,
  Paperclip,
  RefreshCw,
  Download,
  X,
  Mail,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../App";
import {
  useData,
  api,
  errorText,
  dateLabel,
  initials,
  money,
  download,
  ticketStatuses,
} from "../lib/api";
import RichTextEditor from "../components/RichTextEditor";
import { DocPreview, PreviewButton } from "../components/DocPreview";
import {
  PageHead,
  AddButton,
  Loading,
  ErrorState,
  Empty,
  Badge,
  Modal,
  Field,
  SaveButton,
} from "../components/Common";
import { Button } from "../components/ui/button";
const categories = [
  "Bug / Problem",
  "Maintenance",
  "Preventive",
  "Support",
  "Change Request",
  "Out of Scope",
];
const GROUPS = {
  active: ["Belum selesai", ["Baru", "Ditinjau", "Menunggu Klarifikasi", "Diterima", "Menunggu Estimasi Biaya", "Menunggu Persetujuan", "Dikerjakan"]],
  open: ["Open", ["Baru", "Ditinjau", "Menunggu Klarifikasi", "Diterima", "Menunggu Estimasi Biaya", "Menunggu Persetujuan"]],
  closed: ["Selesai / Closed", ["Selesai", "Ditutup", "Ditolak"]],
};
export default function Tickets({ project, onTicketsChanged }) {
  const { user } = useAuth(),
    [params, setParams] = useSearchParams(),
    group = !project && GROUPS[params.get("group")],
    { data, loading, error, reload } = useData(project ? `/projects/${project.id}/tickets` : '/tickets'),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState(project ? "" : params.get("status") || ""),
    [show, setShow] = useState(false),
    [selected, setSelected] = useState(null);
  const refresh = () => { reload(); onTicketsChanged?.(); };
  useEffect(() => {
    if (!project?.id) return;
    const update = () => { if (!document.hidden) reload(); };
    const timer = setInterval(update, 30000);
    window.addEventListener('focus', update);
    return () => { clearInterval(timer); window.removeEventListener('focus', update); };
  }, [project?.id, reload]);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  if (show)
    return (
      <TicketCreate
        user={user}
        fixedProject={project}
        onClose={() => setShow(false)}
        onSaved={() => {
          refresh();
          setShow(false);
        }}
      />
    );
  const rows = data.filter(
    (t) =>
      (t.title + " " + t.project_name + " " + t.code)
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (!filter || t.status === filter) &&
      (!group || group[1].includes(t.status)),
  );
  return (
    <>
      {!project ? <PageHead
        eyebrow="CLIENT SUPPORT"
        title={user.role === "Client" ? "Tiket saya" : "Tiket client"}
        description="Dengarkan, tindak lanjuti, dan hadirkan solusi terbaik."
      >
        {user.role === "Client" && (
          <AddButton id="add-ticket" onClick={() => setShow(true)}>
            Buat tiket
          </AddButton>
        )}
      </PageHead> : <div className="section-heading project-tickets-head">
        <h2 data-testid="project-tickets-title">Tiket project</h2>
        {user.role === 'Client' && !project.tickets_closed && <AddButton id="add-project-ticket" onClick={() => setShow(true)}>Buat tiket</AddButton>}
      </div>}
      {project?.tickets_closed && <p className="form-note" data-testid="project-tickets-closed">Penerimaan tiket baru untuk project ini sudah ditutup.</p>}
      <div className="mini-stats">
        {[
          ["Total tiket", data.length, Ticket],
          [
            "Menunggu tindak lanjut",
            data.filter(
              (t) => !["Selesai", "Ditutup", "Ditolak"].includes(t.status),
            ).length,
            Clock3,
          ],
          [
            "Tiket terselesaikan",
            data.filter((t) => ["Selesai", "Ditutup"].includes(t.status))
              .length,
            CheckCheck,
          ],
        ].map(([n, v, Icon], i) => (
          <div className="mini-stat" key={n} data-testid={`ticket-stat-${i}`}>
            <Icon size={24} />
            <div>
              <small>{n}</small>
              <b>{v}</b>
            </div>
          </div>
        ))}
      </div>
      <div className="list-toolbar">
        <span className="tooltip-text" data-testid="tickets-count">
          {rows.length} tiket
        </span>
        {group && (
          <button type="button" className="ticket-group-chip" data-testid="ticket-group-clear" onClick={() => setParams({})}>
            {group[0]} <X size={12} />
          </button>
        )}
        <div className="toolbar-right">
          {project && <button className="icon-button" data-testid="refresh-project-tickets" title="Muat ulang tiket" onClick={refresh}><RefreshCw size={16} /></button>}
          <div className="list-search">
            <Search size={15} />
            <input
              data-testid="ticket-search"
              placeholder={project ? 'Cari tiket project...' : 'Cari tiket atau project...'}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="filter-select"
            data-testid="ticket-status-filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">Semua status</option>
            {ticketStatuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="panel table-wrap">
        {rows.length ? (
          <table className="data-table" data-testid="tickets-table">
            <thead>
              <tr>
                <th>Tiket</th>
                {!project && <th className="hide-mobile">Project</th>}
                <th>Prioritas</th>
                <th>Status</th>
                <th className="hide-mobile">Tanggal</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} data-testid={`ticket-row-${t.id}`}>
                  <td>
                    <button
                      data-testid={`open-ticket-${t.id}`}
                      onClick={() => setSelected(t.id)}
                      style={{
                        background: "none",
                        border: 0,
                        textAlign: "left",
                        color: "var(--text)",
                      }}
                    >
                      <b style={{ fontWeight: 550 }}>{t.title}</b>
                      <small
                        style={{
                          display: "block",
                          fontSize: 9,
                          color: "var(--muted-text)",
                          marginTop: 6,
                        }}
                      >
                        {t.code} · {t.category}
                      </small>
                    </button>
                  </td>
                  {!project && <td className="hide-mobile"><Link className="link-button" to={`/projects/${t.project_id}`} data-testid={`ticket-project-link-${t.id}`}>{t.project_name}</Link></td>}
                  <td>
                    <Badge id={`ticket-priority-${t.id}`}>{t.priority}</Badge>
                  </td>
                  <td>
                    <Badge id={`ticket-status-${t.id}`}>{t.status}</Badge>
                  </td>
                  <td className="hide-mobile">{dateLabel(t.created_at)}</td>
                  <td>
                    <button
                      className="icon-button"
                      data-testid={`ticket-details-${t.id}`}
                      title="Detail tiket"
                      onClick={() => setSelected(t.id)}
                    >
                      <ArrowUpRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty message="Belum ada tiket yang sesuai." />
        )}
      </div>
      {selected && (
        <TicketDetail
          id={selected}
          user={user}
          onClose={() => setSelected(null)}
          onSaved={refresh}
        />
      )}
    </>
  );
}
const ATTACH_EXT = [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".csv", ".txt", ".log", ".tar", ".gz"];
const fmtSize = (n) => (n > 1024 * 1024 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const stripHtml = (html) => {
  const el = document.createElement("div");
  el.innerHTML = (html || "").replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|li|div|blockquote)>/gi, "\n");
  return (el.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
};
const TicketCreate = ({ user, onClose, onSaved, fixedProject }) => {
  const [projects, setProjects] = useState([]),
    [form, setForm] = useState({
      project_id: fixedProject?.id || "",
      title: "",
      category: "Bug / Problem",
      priority: "Sedang",
      cc: "",
    }),
    [html, setHtml] = useState(""),
    [files, setFiles] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const fileRef = React.useRef(null);
  useEffect(() => {
    if (fixedProject) { setProjects([fixedProject]); return; }
    api
      .get("/ticket-projects")
      .then((r) => setProjects(r.data))
      .catch((e) => setError(errorText(e)));
  }, [fixedProject]);
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const addFiles = (list) => {
    const next = [...files];
    for (const f of Array.from(list)) {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      if (!ATTACH_EXT.includes(ext)) return setError(`Format ${ext} tidak didukung.`);
      if (f.size > 5 * 1024 * 1024) return setError(`${f.name} melebihi 5 MB.`);
      if (next.length >= 5) return setError("Maksimal 5 berkas per tiket.");
      next.push(f);
    }
    setError("");
    setFiles(next);
  };
  const project = projects.find((p) => p.id === form.project_id);
  const save = async (e) => {
    e.preventDefault();
    setError("");
    const text = stripHtml(html);
    if (text.length < 5) return setError("Pesan minimal 5 karakter.");
    const cc = form.cc.split(",").map((x) => x.trim()).filter(Boolean);
    const badCc = cc.find((x) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(x));
    if (badCc) return setError(`Alamat CC tidak valid: ${badCc}`);
    setBusy(true);
    try {
      const r = await api.post("/tickets", {
        project_id: form.project_id,
        title: form.title,
        category: form.category,
        priority: form.priority,
        description: text.slice(0, 5000),
        description_html: html,
        cc_emails: cc,
      });
      if (files.length) {
        const fd = new FormData();
        files.forEach((f) => fd.append("files", f));
        await api.post(`/tickets/${r.data.id}/attachments`, fd);
      }
      toast.success("Tiket terkirim dan menunggu peninjauan tim MaiHarta");
      onSaved();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="ticket-create" data-testid="ticket-create">
      <div className="ticket-create-head">
        <button
          type="button"
          className="ticket-create-back"
          onClick={onClose}
          title="Kembali ke daftar tiket"
          data-testid="ticket-create-back"
        >
          <ArrowLeft size={17} />
        </button>
        <h1 data-testid="ticket-create-title">Buka tiket baru</h1>
      </div>
      <div className="ticket-steps" data-testid="ticket-steps">
        <span>1</span> Jelaskan kebutuhan Anda
      </div>
      <form className="panel" onSubmit={save} data-testid="ticket-create-form">
        <div className="panel-note">
          <span>
            Project: <b>{project ? project.name : "belum dipilih"}</b>
          </span>
          <span>
            Pelapor: <b>{user.name}</b>
          </span>
        </div>
        <div className="ticket-grid">
          <div className="form-full">
            <Field
              label="Subjek"
              name="title"
              placeholder="Ringkas kendala atau permintaan Anda"
              value={form.title}
              onChange={change}
              required
              minLength={3}
              maxLength={200}
            />
          </div>
          <Field
            label="Layanan / project terkait"
            name="project_id"
            as="select"
            options={[
              { value: "", label: "Pilih project" },
              ...projects.map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` })),
            ]}
            value={form.project_id}
            disabled={Boolean(fixedProject)}
            onChange={change}
            required
          />
          <Field
            label="Prioritas"
            name="priority"
            as="select"
            options={["Rendah", "Sedang", "Tinggi", "Mendesak"]}
            value={form.priority}
            onChange={change}
          />
          {user.role !== "Client" && (
            <div className="form-full">
              <Field
                label="Kategori permintaan"
                name="category"
                as="select"
                options={categories}
                value={form.category}
                onChange={change}
              />
            </div>
          )}
          <div className="form-full">
            <Field
              label="CC email"
              name="cc"
              type="text"
              placeholder="rekan@perusahaan.com, tim@perusahaan.com"
              value={form.cc}
              onChange={change}
            />
          </div>
          <p className="form-hint form-full" data-testid="ticket-cc-hint">
            Pisahkan dengan koma. Gunakan email akun terdaftar yang memiliki akses
            project; pengiriman mengikuti preferensi akun penerima.
          </p>
          <label className="form-field form-full">
            <span>
              Pesan<em className="req-mark">*</em>
            </span>
            <RichTextEditor
              value={html}
              onChange={setHtml}
              testid="ticket-message"
              placeholder="Jelaskan kendala, langkah yang sudah dicoba, dan pesan galat bila ada. Jangan kirim sandi di sini."
            />
          </label>
          <div className="form-field form-full">
            <span>
              Lampiran<small className="opt-mark">(opsional)</small>
            </span>
            <div className="attach-row">
              <button
                type="button"
                className="attach-btn"
                onClick={() => fileRef.current?.click()}
                data-testid="ticket-attach-button"
              >
                <Paperclip size={14} /> + Lampiran
              </button>
              <input
                ref={fileRef}
                type="file"
                multiple
                hidden
                accept={ATTACH_EXT.join(",")}
                data-testid="ticket-attach-input"
                onChange={(e) => {
                  addFiles(e.target.files);
                  e.target.value = "";
                }}
              />
              <span className="attach-hint">
                Maksimal 5 berkas, 5 MB per berkas ({ATTACH_EXT.join(", ")}).
              </span>
            </div>
            {files.length > 0 && (
              <div className="attach-list" data-testid="ticket-attach-list">
                {files.map((f, i) => (
                  <span className="attach-chip" key={f.name + i}>
                    <Paperclip size={12} />
                    <span>{f.name}</span>
                    <small>{fmtSize(f.size)}</small>
                    <button
                      type="button"
                      aria-label="Hapus lampiran"
                      onClick={() => setFiles(files.filter((_, j) => j !== i))}
                      data-testid={`ticket-attach-remove-${i}`}
                    >
                      <X size={13} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        {error && (
          <p className="form-error" data-testid="ticket-form-error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <SaveButton busy={busy} label="Kirim tiket" />
          <Button
            type="button"
            className="secondary-button"
            onClick={onClose}
            data-testid="ticket-create-cancel"
          >
            Batal
          </Button>
        </div>
      </form>
    </div>
  );
};
const transitions = {
  Baru: ["Ditinjau", "Ditolak"],
  Ditinjau: [
    "Menunggu Klarifikasi",
    "Diterima",
    "Ditolak",
    "Menunggu Estimasi Biaya",
  ],
  "Menunggu Klarifikasi": ["Ditinjau", "Ditolak"],
  "Menunggu Estimasi Biaya": ["Menunggu Persetujuan", "Ditolak"],
  "Menunggu Persetujuan": ["Diterima", "Ditolak"],
  Diterima: ["Dikerjakan"],
  Dikerjakan: ["Selesai"],
  Selesai: ["Ditutup"],
  Ditolak: ["Ditutup"],
  Ditutup: [],
};
export const TicketDetail = ({ id, user, onClose, onSaved }) => {
  const { data: t, loading, error, reload } = useData(`/tickets/${id}`),
    { data: comments, reload: reloadComments } = useData(
      `/tickets/${id}/comments`,
    ),
    [team, setTeam] = useState([]),
    [form, setForm] = useState({}),
    [busy, setBusy] = useState(false),
    [updateError, setUpdateError] = useState(""),
    [message, setMessage] = useState(""),
    [internal, setInternal] = useState(false),
    [sending, setSending] = useState(false),
    [preview, setPreview] = useState(null);
  const manager = ["Admin", "Admin Project"].includes(user.role);
  useEffect(() => {
    if (t) {
      setForm({
        status: t.status,
        category: t.category,
        assigned_to: t.assigned_to || "",
        estimate: t.estimate || 0,
      });
      if (manager)
        Promise.all([api.get("/team"), api.get(`/projects/${t.project_id}`)])
          .then(([team, p]) =>
            setTeam(team.data.filter((d) => d.role !== 'Developer' || p.data.assigned_to.includes(d.id))),
          )
          .catch(() => {});
    }
  }, [t, manager]);
  const change = (e) =>
    setForm({
      ...form,
      [e.target.name]:
        e.target.type === "number" ? Number(e.target.value) : e.target.value,
    });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setUpdateError("");
    try {
      await api.patch(
        `/tickets/${id}`,
        manager ? form : { status: form.status },
      );
      toast.success("Tiket diperbarui");
      reload();
      reloadComments();
      onSaved();
    } catch (e) {
      setUpdateError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const send = async (e) => {
    e.preventDefault();
    if (!message.trim()) return;
    setSending(true);
    try {
      await api.post(`/tickets/${id}/comments`, { message, internal });
      setMessage("");
      reloadComments();
    } catch (e) {
      toast.error(errorText(e));
    } finally {
      setSending(false);
    }
  };
  let options = t ? [t.status, ...(transitions[t.status] || [])] : [];
  if (user.role === "Developer")
    options =
      t?.status === "Diterima"
        ? ["Diterima", "Dikerjakan"]
        : t?.status === "Dikerjakan"
          ? ["Dikerjakan", "Selesai"]
          : [];
  if (user.role === "Client")
    options =
      t?.status === "Menunggu Persetujuan"
        ? ["Menunggu Persetujuan", "Diterima", "Ditolak"]
        : [];
  return (
    <Modal
      open
      onClose={onClose}
      title={t?.title || "Detail tiket"}
      description={t?.code}
    >
      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState error={error} reload={reload} />
      ) : (
        <>
          <div className="ticket-info">
            <Badge id="ticket-detail-status">{t.status}</Badge>
            <Badge id="ticket-detail-priority">{t.priority}</Badge>
            <Link className="link-button" to={`/projects/${t.project_id}`} data-testid="ticket-detail-project">{t.project_name}</Link>
          </div>
          {t.description_html ? (
            <div
              className="ticket-description"
              data-testid="ticket-description"
              dangerouslySetInnerHTML={{ __html: t.description_html }}
            />
          ) : (
            <p className="ticket-description" data-testid="ticket-description">
              {t.description}
            </p>
          )}
          {t.cc_emails?.length > 0 && (
            <p className="ticket-meta-line" data-testid="ticket-cc">
              <Mail size={12} style={{ display: "inline", marginRight: 5 }} />
              CC: {t.cc_emails.join(", ")}
            </p>
          )}
          {t.attachments?.length > 0 && (
            <div className="attach-list" data-testid="ticket-attachments">
              <DocPreview file={preview} onClose={() => setPreview(null)} />
              {t.attachments.map((a) => (
                <span className="attach-chip" key={a.id}>
                  <Paperclip size={12} />
                  <span>{a.name}</span>
                  <small>{fmtSize(a.size)}</small>
                  <a
                    href="#unduh"
                    title="Unduh lampiran"
                    data-testid={`ticket-attachment-${a.id}`}
                    onClick={(e) => {
                      e.preventDefault();
                      download(`/tickets/${id}/attachments/${a.id}/download`, a.name);
                    }}
                  >
                    <Download size={13} />
                  </a>
                  <PreviewButton className="doc-preview-inline" size={13} testid={`ticket-attachment-preview-${a.id}`} onClick={() => setPreview({ name: a.name, path: `/tickets/${id}/attachments/${a.id}/download`, type: a.content_type })} />
                </span>
              ))}
            </div>
          )}
          {t.estimate > 0 && (
            <p className="note-block" data-testid="ticket-estimate">
              Estimasi biaya: <b>{money(t.estimate)}</b>
              {t.approved ? " · Disetujui" : ""}
            </p>
          )}
          {options.length > 0 && (
            <form
              onSubmit={save}
              style={{
                borderTop: "1px solid var(--line)",
                paddingTop: 19,
                marginTop: 21,
              }}
            >
              <h3 className="detail-heading">
                {manager
                  ? "Triase & penugasan"
                  : user.role === "Client"
                    ? "Persetujuan estimasi"
                    : "Progres pekerjaan"}
              </h3>
              <div className="form-grid">
                <Field
                  label="Status tiket"
                  name="status"
                  as="select"
                  options={options}
                  value={form.status || t.status}
                  onChange={change}
                />
                {manager && (
                  <>
                    <Field
                      label="Klasifikasi akhir"
                      name="category"
                      as="select"
                      options={categories}
                      value={form.category || t.category}
                      onChange={change}
                    />
                    <Field
                      label="Penanggung jawab"
                      name="assigned_to"
                      as="select"
                      options={[
                        { value: "", label: "Belum ditugaskan" },
                        ...team.map((d) => ({ value: d.id, label: d.name })),
                      ]}
                      value={form.assigned_to || ""}
                      onChange={change}
                    />
                    <Field
                      label="Estimasi biaya (Rp)"
                      name="estimate"
                      as="money"
                      value={form.estimate ?? 0}
                      onChange={change}
                    />
                  </>
                )}
              </div>
              {updateError && (
                <p className="form-error" data-testid="ticket-update-error">
                  {updateError}
                </p>
              )}
              {manager && form.status === "Diterima" && !t.task_id && (
                <p className="hint-text" data-testid="ticket-kanban-hint">
                  Saat diterima, tiket otomatis masuk ke Kanban project dan PIC
                  menerima notifikasi email.
                </p>
              )}
              {t.task_id && (
                <p className="hint-text" data-testid="ticket-kanban-linked">
                  Tiket ini sudah terhubung ke task Kanban project.
                </p>
              )}
              <div className="form-actions">
                <SaveButton busy={busy} label="Perbarui tiket" />
              </div>
            </form>
          )}
          <h3 className="detail-heading" style={{ marginTop: 25 }}>
            Percakapan
          </h3>
          <div className="comments-list">
            {(comments || []).map((c) => (
              <div
                className={`comment-item ${c.system ? "system" : ""}`}
                data-testid={`comment-${c.id}`}
                key={c.id}
              >
                <span className="avatar">{initials(c.author_name)}</span>
                <div className="comment-body">
                  <header>
                    <b>{c.author_name}</b>
                    <span>
                      {c.internal ? "Internal · " : ""}
                      {dateLabel(c.created_at)}
                    </span>
                  </header>
                  <p>{c.message}</p>
                </div>
              </div>
            ))}
            {!comments?.length && (
              <p className="form-note">Belum ada percakapan.</p>
            )}
          </div>
          <form onSubmit={send}>
            <div className="comment-compose">
              <textarea
                data-testid="ticket-comment-input"
                placeholder="Tulis pesan..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
              />
              <Button
                type="submit"
                data-testid="send-ticket-comment"
                className="primary-button"
                disabled={sending || !message.trim()}
                title="Kirim pesan"
              >
                <Send size={16} />
              </Button>
            </div>
            {user.role !== "Client" && (
              <label className="checkbox-label" style={{ marginTop: 12 }}>
                <input
                  data-testid="comment-internal-checkbox"
                  type="checkbox"
                  checked={internal}
                  onChange={(e) => setInternal(e.target.checked)}
                />
                Catatan internal tim
              </label>
            )}
          </form>
        </>
      )}
    </Modal>
  );
};
