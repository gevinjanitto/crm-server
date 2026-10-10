import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import { api, useData, errorText } from "../lib/api";
import { WorkCard } from "./WorkCard";
import { useNavigate } from "react-router-dom";
import { TicketDetail } from '../pages/Tickets';
import { DraftDescription } from "./kanban/DraftDescription";
import { commitDraft, hasRichContent, htmlToText } from "./kanban/RichDescription";
import {
  Loading,
  ErrorState,
  Empty,
  AddButton,
  Modal,
  Field,
  SaveButton,
  SubtaskInput,
} from "./Common";
export const WorkForm = ({ open, onClose, onSaved, kind, project }) => {
  const [projects, setProjects] = useState([]),
    [team, setTeam] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [form, setForm] = useState({}),
    [file, setFile] = useState(null),
    [desc, setDesc] = useState({ html: "", files: {} });
  const revision = kind === "revisions",
    options = revision
      ? ["In-scope", "Out-of-scope", "Change Request"]
      : ["Adaptive", "Corrective", "Preventive", "Support", "Change Request"];
  useEffect(() => {
    if (!open) return;
    setError("");
    setForm({
      project_id: project?.id || "",
      title: "",
      description: "",
      kind: kind === "revisions" ? "In-scope" : "Adaptive",
      assigned_to: "",
      entry_date: new Date().toISOString().slice(0, 10),
      started_date: "",
      due_date: revision
        ? new Date(Date.now() + 604800000).toISOString().slice(0, 10)
        : "",
      priority: "Sedang",
      estimate: 0,
      subtasks: [],
    });
    setFile(null);
    setDesc({ html: "", files: {} });
    Promise.all([api.get("/projects"), api.get("/team")])
      .then(([p, t]) => {
        setProjects(p.data);
        setTeam(t.data);
      })
      .catch((e) => setError(errorText(e)));
  }, [open, project, kind, revision]);
  const selected = project || projects.find((p) => p.id === form.project_id),
    devs = team.filter((t) => t.role !== 'Developer' || selected?.assigned_to.includes(t.id));
  const change = (e) =>
    setForm({
      ...form,
      [e.target.name]:
        e.target.type === "number" ? Number(e.target.value) : e.target.value,
      ...(e.target.name === "project_id" ? { assigned_to: "" } : {}),
    });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const { project_id, subtasks, ...body } = form;
    try {
      const r = await api.post(`/projects/${project_id}/work/${kind}`, {
        ...body,
        description: htmlToText(desc.html),
        started_date: body.started_date || null,
        due_date: body.due_date || null,
        estimate: Number(body.estimate) || 0,
        subtasks: subtasks || [],
      });
      if (file && r.data.task_id) {
        const f = new FormData();
        f.append("file", file);
        await api
          .post(`/projects/${project_id}/tasks/${r.data.task_id}/documents`, f)
          .catch((e) => toast.error(errorText(e)));
      }
      if (r.data.task_id && hasRichContent(desc.html)) {
        await commitDraft(`/projects/${project_id}/tasks/${r.data.task_id}`, desc.html, desc.files)
          .catch((e) => toast.error(errorText(e)));
      }
      toast.success(
        `${revision ? "Revisi" : "Maintenance"} ditambahkan & masuk ke Kanban`,
      );
      onSaved();
      onClose();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={revision ? "Revisi baru" : "Maintenance baru"}
    >
      <form onSubmit={save}>
        <div className="form-grid">
          {!project && (
            <div className="form-full">
              <Field
                label="Project"
                name="project_id"
                as="select"
                options={[
                  { value: "", label: "Pilih project" },
                  ...projects.map((p) => ({ value: p.id, label: p.name })),
                ]}
                value={form.project_id || ""}
                onChange={change}
                required
              />
            </div>
          )}
          <div className="form-full">
            <Field
              label="Judul"
              name="title"
              value={form.title || ""}
              onChange={change}
              required
            />
          </div>
          <Field
            label="Klasifikasi"
            name="kind"
            as="select"
            options={options}
            value={form.kind || options[0]}
            onChange={change}
            required
          />
          <Field
            label="Prioritas"
            name="priority"
            as="select"
            options={["Rendah", "Sedang", "Tinggi", "Mendesak"]}
            value={form.priority || "Sedang"}
            onChange={change}
            required
          />
          <Field
            label="Tanggal masuk"
            name="entry_date"
            type="date"
            value={form.entry_date || ""}
            onChange={change}
            required
          />
          <Field
            label="Tanggal dikerjakan"
            name="started_date"
            type="date"
            min={form.entry_date}
            value={form.started_date || ""}
            onChange={change}
          />
          <Field
            label="Target selesai"
            name="due_date"
            type="date"
            min={form.entry_date}
            value={form.due_date || ""}
            onChange={change}
            required={revision}
          />
          <Field
            label="Penanggung jawab"
            name="assigned_to"
            as="select"
            options={[
              { value: "", label: "Belum ditugaskan" },
              ...devs.map((t) => ({ value: t.id, label: t.name })),
            ]}
            value={form.assigned_to || ""}
            onChange={change}
          />
          <Field
            label="Estimasi biaya tambahan (Rp)"
            name="estimate"
            as="money"
            value={form.estimate ?? 0}
            onChange={change}
          />
          <div className="form-full">
            <DraftDescription testid="work-description" value={desc} onChange={setDesc} />
          </div>
          <div className="form-full">
            <SubtaskInput
              label="Subtask Kanban"
              testid="work-subtask"
              value={form.subtasks || []}
              onChange={(l) => setForm((f) => ({ ...f, subtasks: l }))}
            />
          </div>
          <div className="form-full">
            <Field
              label="Lampiran dokumen (opsional, maks. 10 MB)"
              name="work_file"
              type="file"
              accept=".pdf,.docx,.xlsx,.txt,.csv,.png,.jpg,.jpeg,.webp"
              onChange={(e) => setFile(e.target.files[0])}
            />
          </div>
        </div>
        {error && (
          <p className="form-error" data-testid="work-form-error">
            {error}
          </p>
        )}
        <p className="form-legend">
          <em>*</em> wajib diisi
        </p>
        <div className="form-actions">
          <SaveButton busy={busy} />
        </div>
      </form>
    </Modal>
  );
};
export const WorkCards = ({ rows, user, kind, reload, showProject = true, filtered = false }) => {
  const [ticketId, setTicketId] = useState(null);
  const navigate = useNavigate();
  const [editing, setEditing] = useState(null),
    [status, setStatus] = useState(""),
    [approved, setApproved] = useState(false),
    [extra, setExtra] = useState({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const maintenance = kind === "maintenances",
    statusOptions = maintenance
      ? ["Belum dikerjakan", "Development", "Testing", "Selesai"]
      : ["Terbuka", "Dikerjakan", "Selesai"];
  const manager = ["Admin", "Admin Project"].includes(user.role);
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.patch(
        `/projects/${editing.project_id}/work/${kind}/${editing.id}`,
        {
          status,
          approved,
          started_date: extra.started_date || null,
          due_date: extra.due_date || null,
          priority: extra.priority || null,
          estimate: extra.estimate === "" ? null : Number(extra.estimate),
        },
      );
      toast.success("Pekerjaan diperbarui");
      setEditing(null);
      reload();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const remove = async (r) => {
    if (!window.confirm(`Pindahkan "${r.title}" ke arsip?`)) return;
    try {
      await api.delete(`/projects/${r.project_id}/work/${kind}/${r.id}`);
      toast.success("Dipindahkan ke arsip");
      reload();
    } catch (e) {
      toast.error(errorText(e));
    }
  };
  return (
    <>
      <div className="work-card-list">
        {rows.map((r) => (
          <WorkCard
            key={r.id}
            work={r}
            showProject={showProject}
            manager={manager}
            onOpenTicket={setTicketId}
            onOpen={r.task_id && !r.ticket_id ? () => navigate(`/projects/${r.project_id}/kanban?task=${r.task_id}`) : undefined}
            onRemove={remove}
            onEdit={(work) => {
              setEditing(work);
              setStatus(work.status);
              setApproved(work.approved || false);
              setExtra({
                started_date: work.started_date || "",
                due_date: work.due_date || "",
                priority: work.priority || "Sedang",
                estimate: work.estimate ?? 0,
              });
              setError("");
            }}
          />
        ))}
      </div>
      {!rows.length && (
        <Empty
          message={filtered ? "Tidak ada pekerjaan yang cocok. Coba kata kunci lain atau reset filter." : `Belum ada ${kind === "revisions" ? "revisi" : "maintenance"}.`}
        />
      )}
      {ticketId && <TicketDetail id={ticketId} user={user} onClose={() => setTicketId(null)} onSaved={reload} />}
      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title="Perbarui pekerjaan"
      >
        <form onSubmit={save}>
          <div className="form-grid">
            <Field
              label="Status pengerjaan"
              name="status"
              as="select"
              options={statusOptions}
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              required
            />
            <Field
              label="Prioritas"
              name="priority"
              as="select"
              options={["Rendah", "Sedang", "Tinggi", "Mendesak"]}
              value={extra.priority || "Sedang"}
              onChange={(e) => setExtra({ ...extra, priority: e.target.value })}
              required
            />
            <Field
              label="Tanggal dikerjakan"
              name="started_date"
              type="date"
              value={extra.started_date || ""}
              onChange={(e) => setExtra({ ...extra, started_date: e.target.value })}
            />
            <Field
              label="Target selesai"
              name="due_date"
              type="date"
              value={extra.due_date || ""}
              onChange={(e) => setExtra({ ...extra, due_date: e.target.value })}
            />
            <Field
              label="Estimasi biaya tambahan (Rp)"
              name="estimate"
              as="money"
              value={extra.estimate ?? 0}
              onChange={(e) => setExtra({ ...extra, estimate: e.target.value })}
            />
          </div>
          {["Out-of-scope", "Change Request"].includes(editing?.kind) && (
            <label className="checkbox-label" style={{ marginTop: 20 }}>
              <input
                data-testid="approve-work-estimate"
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
              />
              Estimasi biaya telah disetujui
            </label>
          )}
          {error && (
            <p className="form-error" data-testid="work-update-error">
              {error}
            </p>
          )}
          <div className="form-actions">
            <SaveButton busy={busy} />
          </div>
        </form>
      </Modal>
    </>
  );
};
