import React, { useState } from "react";
import { Trash2, AlignLeft, ChevronDown, Plus } from "lucide-react";
import { api } from "../../lib/api";
import { RichDescription, textToHtml, htmlToText, imageForm } from "./RichDescription";
import { MAX_SUBTASK_LEVEL } from "./SubtaskTreeInput";

const hasDescription = (s) => !!((s.description || "").trim() || htmlToText(s.description_html || "").trim() || (s.images || []).length);

export const SubtaskItem = ({ s, subs = [], level = 1, base, task, team, manager, editable, run }) => {
  const [open, setOpen] = useState(() => hasDescription(s)),
    [adding, setAdding] = useState(false),
    [text, setText] = useState("");
  const path = `${base}/subtasks/${s.id}`;
  const children = subs.filter((x) => x.parent_id === s.id);
  const upload = async (files) => {
    const r = await run(() => api.post(`${path}/images`, imageForm(files)));
    const sub = r?.data?.subtasks?.find((x) => x.id === s.id);
    return sub ? (sub.images || []).slice(-files.length).map((i) => i.id) : [];
  };
  const save = async (html) => !!(await run(() => api.patch(path, { description_html: html }), "Deskripsi subtask disimpan"));
  const remove = () => {
    if (children.length && !window.confirm(`Hapus subtask "${s.title}" beserta ${children.length} sub di dalamnya?`)) return;
    run(() => api.delete(path).then((r) => {
      const gone = new Set(r.data.deleted_ids || [s.id]);
      return { data: { ...task, subtasks: task.subtasks.filter((x) => !gone.has(x.id)) } };
    }));
  };
  const addChild = async (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    const r = await run(() => api.post(`${base}/subtasks`, { title: text.trim(), parent_id: s.id }), "Sub-subtask ditambahkan");
    if (r) setText("");
  };
  return (
    <div className={`ck-subtask-wrap level-${level}`} data-testid={`subtask-${s.id}`}>
      <div className={`ck-subtask ${s.done ? "done" : ""}`}>
        <input type="checkbox" data-testid={`subtask-toggle-${s.id}`} checked={s.done} disabled={!editable}
          onChange={(e) => run(() => api.patch(path, { done: e.target.checked }))} />
        <button type="button" className="ck-subtask-title ck-subtask-open" data-testid={`subtask-open-${s.id}`} onClick={() => setOpen(!open)}>
          {s.title}
          {hasDescription(s) && <AlignLeft size={12} className="ck-subtask-has-desc" />}
          <ChevronDown size={13} className={`ck-subtask-chevron ${open ? "open" : ""}`} />
        </button>
        {editable && level < MAX_SUBTASK_LEVEL && (
          <button type="button" className="ck-icon" title="Tambah sub di dalam subtask ini" data-testid={`subtask-add-child-${s.id}`} onClick={() => setAdding(!adding)}>
            <Plus size={13} />
          </button>
        )}
        {manager ? (
          <select className="ck-inline small" data-testid={`subtask-assignee-${s.id}`} value={s.assigned_to || ""}
            onChange={(e) => run(() => api.patch(path, { assigned_to: e.target.value }), "PIC subtask diperbarui")}>
            <option value="">PIC —</option>
            {team.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        ) : <small>{s.assigned_name}</small>}
        {editable && (
          <button className="ck-icon danger" data-testid={`delete-subtask-${s.id}`} onClick={remove}>
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
      {(children.length > 0 || adding) && (
        <div className="ck-subtask-children">
          {children.map((c) => (
            <SubtaskItem key={c.id} s={c} subs={subs} level={level + 1} base={base} task={task} team={team} manager={manager} editable={editable} run={run} />
          ))}
          {adding && (
            <form className="ck-add-row" onSubmit={addChild}>
              <Plus size={14} />
              <input autoFocus data-testid={`subtask-child-input-${s.id}`} placeholder={`Tambah subtask tingkat ${level + 1}, Enter untuk simpan`} value={text} onChange={(e) => setText(e.target.value)} />
            </form>
          )}
        </div>
      )}
    </div>
  );
};
