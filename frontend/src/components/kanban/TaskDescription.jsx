import React from "react";
import { toast } from "sonner";
import { api, errorText } from "../../lib/api";
import { RichDescription, textToHtml, imageForm } from "./RichDescription";

const legacyHtml = (t) => textToHtml(t.description) + (t.description_images || []).map((i) => `<p><img data-image-id="${i.id}"></p>`).join("");
const IDS = { root: "task-description-editor", input: "task-description-input", view: "task-description", tool: "task-desc", file: "task-image-input" };

export const TaskDescription = ({ task, base, manager, onChange }) => {
  const upload = async (files) => {
    try {
      const r = await api.post(`${base}/images`, imageForm(files));
      onChange(r.data);
      return r.data.description_images.slice(-files.length).map((i) => i.id);
    } catch (e) { toast.error(errorText(e)); return []; }
  };
  const save = async (html) => {
    try { onChange((await api.patch(base, { description_html: html })).data); toast.success("Deskripsi disimpan"); }
    catch (e) { toast.error(errorText(e)); return false; }
  };
  return (
    <RichDescription docKey={task.id} html={task.description_html ?? legacyHtml(task)} editable={manager} ids={IDS}
      imagePath={(id) => `${base}/images/${id}`} upload={upload} onSave={save}
      placeholder="Tulis deskripsi task… tempel (Ctrl+V) atau seret foto langsung ke sini" />
  );
};
