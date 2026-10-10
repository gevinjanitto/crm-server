import React, { useState } from "react";
import { Trash2, AlignLeft, ChevronDown } from "lucide-react";
import { api } from "../../lib/api";
import { RichDescription, textToHtml, imageForm } from "./RichDescription";

export const SubtaskItem = ({ s, base, task, team, manager, editable, run }) => {
  const [open, setOpen] = useState(false);
  const path = `${base}/subtasks/${s.id}`;
  const upload = async (files) => {
    const r = await run(() => api.post(`${path}/images`, imageForm(files)));
    const sub = r?.data?.subtasks?.find((x) => x.id === s.id);
    return sub ? (sub.images || []).slice(-files.length).map((i) => i.id) : [];
  };
  const save = async (html) => !!(await run(() => api.patch(path, { description_html: html }), "Deskripsi subtask disimpan"));
  return (
    <div className="ck-subtask-wrap" data-testid={`subtask-${s.id}`}>
      <div className={`ck-subtask ${s.done ? "done" : ""}`}>
        <input type="checkbox" data-testid={`subtask-toggle-${s.id}`} checked={s.done} disabled={!editable}
          onChange={(e) => run(() => api.patch(path, { done: e.target.checked }))} />
        <button type="button" className="ck-subtask-title ck-subtask-open" data-testid={`subtask-open-${s.id}`} onClick={() => setOpen(!open)}>
          {s.title}
          {(s.description || s.description_html) && <AlignLeft size={12} className="ck-subtask-has-desc" />}
          <ChevronDown size={13} className={`ck-subtask-chevron ${open ? "open" : ""}`} />
        </button>
        {manager ? (
          <select className="ck-inline small" data-testid={`subtask-assignee-${s.id}`} value={s.assigned_to || ""}
            onChange={(e) => run(() => api.patch(path, { assigned_to: e.target.value }), "PIC subtask diperbarui")}>
            <option value="">PIC —</option>
            {team.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        ) : <small>{s.assigned_name}</small>}
        {editable && (
          <button className="ck-icon danger" data-testid={`delete-subtask-${s.id}`}
            onClick={() => run(() => api.delete(path).then(() => ({ data: { ...task, subtasks: task.subtasks.filter((x) => x.id !== s.id) } })))}>
            <Trash2 size={13} />
          </button>
        )}
      </div>
      {open && (
        <div className="ck-subtask-desc">
          <RichDescription docKey={s.id} html={s.description_html ?? textToHtml(s.description)} editable={editable} className="compact"
            imagePath={(id) => `${path}/images/${id}`} upload={upload} onSave={save}
            placeholder="Tulis deskripsi subtask… tempel (Ctrl+V) atau seret foto ke sini"
            ids={{ root: `subtask-description-editor-${s.id}`, input: `subtask-description-input-${s.id}`, view: `subtask-description-${s.id}`, tool: `subtask-desc-${s.id}`, file: `subtask-image-input-${s.id}` }} />
        </div>
      )}
    </div>
  );
};
