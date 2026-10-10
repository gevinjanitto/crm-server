import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errorText, serverStages } from "../lib/api";
import { Modal, Field, SaveButton, SubtaskInput } from "./Common";
import { PRIORITIES } from "./kanban/helpers";
import { MultiAssigneeSelect } from "./kanban/MultiAssigneeSelect";
import { DraftDescription } from "./kanban/DraftDescription";
import { commitDraft, hasRichContent, htmlToText } from "./kanban/RichDescription";

const blank = (status) => ({
  title: "",
  description: "",
  status,
  server: "Belum Naik",
  priority: "Sedang",
  assigned_to: "",
  assignee_ids: [],
  start_date: "",
  due_date: "",
  estimate_hours: 0,
  tags: "",
  subtasks: [],
  list_id: '',
});

export const TaskForm = ({ open, onClose, projectId, team, statuses = [], onSaved, lists = [], defaultList = '' }) => {
  const [form, setForm] = useState(blank("")),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [desc, setDesc] = useState({ html: "", files: {} });
  useEffect(() => {
    if (open) {
      setError("");
      setDesc({ html: "", files: {} });
      setForm({ ...blank(statuses[0]?.name || "Belum Mulai"), list_id: defaultList });
    }
  }, [open, statuses, defaultList]);
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(`/projects/${projectId}/tasks`, {
        ...form,
        description: htmlToText(desc.html),
        estimate_hours: Number(form.estimate_hours) || 0,
        start_date: form.start_date || null,
        due_date: form.due_date || null,
        tags: form.tags.split(",").map((s) => s.trim()).filter(Boolean),
        subtasks: form.subtasks,
      });
      let task = r.data;
      if (hasRichContent(desc.html)) {
        task = await commitDraft(`/projects/${projectId}/tasks/${task.id}`, desc.html, desc.files)
          .catch((e) => { toast.error(errorText(e)); return task; });
      }
      toast.success("Task ditambahkan ke Kanban");
      onSaved(task);
      onClose();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="Task baru">
      <form onSubmit={save}>
        <div className="form-grid">
          <div className="form-full">
            <Field label="Judul task" name="title" value={form.title} onChange={change} required autoFocus />
          </div>
          <Field label="Status" name="status" as="select" options={statuses.map((s) => s.name)} value={form.status} onChange={change} />
          <Field label="Server" name="server" as="select" options={serverStages} value={form.server} onChange={change} />
          <div className="form-field"><span data-testid="create-assignees-label">Penanggung jawab</span><MultiAssigneeSelect testId="create-task-assignees" people={team} value={form.assignee_ids} onChange={ids => setForm(f => ({ ...f, assignee_ids: ids }))} /></div>
          <Field label="Prioritas" name="priority" as="select" options={PRIORITIES} value={form.priority} onChange={change} />
          {lists.length > 0 && <Field label="List" name="list_id" as="select" options={[{ value: '', label: 'Tanpa List' }, ...lists.map(n => ({ value: n.id, label: n.name }))]} value={form.list_id} onChange={change} />}
          <Field label="Tanggal mulai" name="start_date" type="date" value={form.start_date} onChange={change} />
          <Field label="Target selesai" name="due_date" type="date" value={form.due_date} onChange={change} />
          <Field label="Estimasi (jam)" name="estimate_hours" type="number" min="0" step="0.5" value={form.estimate_hours} onChange={change} />
          <Field label="Tag (pisahkan koma)" name="tags" placeholder="Frontend, API" value={form.tags} onChange={change} />
          <div className="form-full">
            <DraftDescription testid="create-task-description" value={desc} onChange={setDesc} />
          </div>
          <div className="form-full">
            <SubtaskInput
              label="Subtask"
              testid="task-subtask"
              value={form.subtasks}
              onChange={(l) => setForm((f) => ({ ...f, subtasks: l }))}
            />
          </div>
        </div>
        {error && (
          <p className="form-error" data-testid="task-form-error">
            {error}
          </p>
        )}
        <div className="form-actions">
          <SaveButton busy={busy} label="Buat task" />
        </div>
      </form>
    </Modal>
  );
};
