import React, { useEffect, useRef, useState } from "react";
import { Bold, Italic, List, ListOrdered, Link2, ImagePlus, Loader2 } from "lucide-react";
import { api } from "../../lib/api";
import { ImageLightbox } from "./AuthImage";
import { ImageTools, applyLayout } from "./ImageTools";

const PENDING = "pending-";
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const textToHtml = (text) => esc(text || "").replace(/\n/g, "<br>");
export const hasRichContent = (html) => /<[a-z]/i.test(html || "");
export const htmlToText = (html) => {
  const marked = (html || "").replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|div|li|h[1-3]|blockquote)>/gi, "$&\n");
  return new DOMParser().parseFromString(marked, "text/html").body.textContent.replace(/\n{3,}/g, "\n\n").trim();
};
export const imageForm = (files) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name || "foto.png"));
  return form;
};
// Upload photos pasted into a not-yet-saved form, then store the final description on the task.
export const commitDraft = async (taskBase, html, files) => {
  let out = html;
  const pending = Object.keys(files).filter((id) => out.includes(`"${id}"`));
  for (let i = 0; i < pending.length; i += 5) {
    const batch = pending.slice(i, i + 5);
    const r = await api.post(`${taskBase}/images`, imageForm(batch.map((id) => files[id])));
    const added = r.data.description_images.slice(-batch.length);
    batch.forEach((id, j) => { out = out.split(`"${id}"`).join(`"${added[j].id}"`); });
  }
  return (await api.patch(taskBase, { description_html: out })).data;
};

// Keep only safe attributes: href on links, id/size/alignment on images.
const tidy = (root) => root.querySelectorAll("*").forEach((n) => {
  if (n.tagName === "IMG" && !n.dataset.imageId) return n.remove();
  const keep = n.tagName === "A" ? ["href"] : n.tagName === "IMG" ? ["data-image-id", "data-width", "data-align"] : [];
  [...n.attributes].forEach((a) => !keep.includes(a.name) && n.removeAttribute(a.name));
});
const serialize = (el) => {
  const c = el.cloneNode(true);
  tidy(c);
  const html = c.innerHTML.trim();
  return html === "<br>" ? "" : html;
};
const caretRange = (el, e) => {
  const r = e && document.caretRangeFromPoint ? document.caretRangeFromPoint(e.clientX, e.clientY) : window.getSelection()?.rangeCount && window.getSelection().getRangeAt(0);
  return r && el.contains(r.startContainer) ? r.cloneRange() : null;
};

/* Rich description with paste/drop photos. `upload` = save photos now; without it photos wait in `onDraft` until the form is saved. */
export const RichDescription = ({ docKey, html, editable, imagePath, upload, onSave, onDraft, placeholder, ids, preview = true, className = "" }) => {
  const ref = useRef(null), saved = useRef(null), lastId = useRef(null), urls = useRef({}), local = useRef({}), range = useRef(null), input = useRef(null), busyRef = useRef(0), wrap = useRef(null);
  const [busy, setBusy] = useState(0), [open, setOpen] = useState(null), [sel, setSel] = useState(null);
  const hydrate = () => ref.current?.querySelectorAll("img[data-image-id]").forEach(async (img) => {
    const id = img.dataset.imageId;
    applyLayout(img);
    if (img.getAttribute("src")) return;
    img.className = "ck-inline-img"; img.alt = "Foto";
    if (id.startsWith(PENDING)) return local.current[id] ? (img.src = local.current[id].url) : img.remove();
    urls.current[id] ||= api.get(imagePath(id), { responseType: "blob" }).then((r) => URL.createObjectURL(r.data)).catch(() => "");
    const url = await urls.current[id];
    if (url) img.src = url; else img.classList.add("broken");
  });
  useEffect(() => {
    const sameDoc = lastId.current === docKey;
    lastId.current = docKey;
    if (sameDoc && html === saved.current) return;
    saved.current = html;
    if (sameDoc && document.activeElement === ref.current) return;
    ref.current.innerHTML = html;
    hydrate();
  }, [docKey, html]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => {
    Object.values(urls.current).forEach((p) => p.then((u) => u && URL.revokeObjectURL(u)));
    Object.values(local.current).forEach((l) => URL.revokeObjectURL(l.url));
  }, []);
  const save = async () => {
    if (!editable || busyRef.current) return;
    const out = serialize(ref.current);
    if (out === saved.current) return;
    saved.current = out;
    if (onDraft) return onDraft(out, Object.fromEntries(Object.entries(local.current).filter(([id]) => out.includes(`"${id}"`)).map(([id, l]) => [id, l.file])));
    if ((await onSave(out)) === false) saved.current = null;
  };
  const putHtml = (snippet, at) => {
    const el = ref.current, s = window.getSelection();
    el.focus();
    const r = at || document.createRange();
    if (!at) { r.selectNodeContents(el); r.collapse(false); }
    s.removeAllRanges(); s.addRange(r);
    document.execCommand("insertHTML", false, snippet);
  };
  const tag = (id) => `<img data-image-id="${id}">`;
  const addImages = async (files, at) => {
    const images = [...files].filter((f) => f.type.startsWith("image/"));
    if (!images.length) return;
    if (!upload) {
      const made = images.map((file) => {
        const id = PENDING + Math.random().toString(36).slice(2, 12);
        local.current[id] = { file, url: URL.createObjectURL(file) };
        return id;
      });
      putHtml(made.map(tag).join("") + "<br>", at);
      hydrate();
      return save();
    }
    busyRef.current++; setBusy((b) => b + 1);
    const added = await upload(images);
    if (added?.length) { putHtml(added.map(tag).join("") + "<br>", at); hydrate(); }
    busyRef.current--; setBusy((b) => b - 1);
    save();
  };
  const onPaste = (e) => {
    if ([...e.clipboardData.files].some((f) => f.type.startsWith("image/"))) { e.preventDefault(); return addImages(e.clipboardData.files, caretRange(ref.current)); }
    setTimeout(() => { tidy(ref.current); hydrate(); if (onDraft) save(); }, 0);
  };
  const onDrop = (e) => {
    if (![...e.dataTransfer.files].length) return;
    e.preventDefault();
    addImages(e.dataTransfer.files, caretRange(ref.current, e));
  };
  const showImage = (id) => preview && !id.startsWith(PENDING) && setOpen({ name: "Foto deskripsi", path: imagePath(id) });
  const onClick = (e) => {
    const id = e.target.dataset?.imageId;
    if (editable) setSel(id ? e.target : null);
    if (id && (!editable || e.detail === 2)) showImage(id);
  };
  useEffect(() => {
    if (!sel) return;
    const away = (e) => !wrap.current?.contains(e.target) && setSel(null);
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [sel]);
  const exec = (cmd, arg) => { ref.current.focus(); document.execCommand(cmd, false, arg); if (onDraft) save(); };
  const link = () => { const url = window.prompt("Masukkan URL (https://...)"); if (url && /^https?:\/\//i.test(url)) exec("createLink", url); };
  const tools = [["bold", Bold, () => exec("bold"), "Tebal"], ["italic", Italic, () => exec("italic"), "Miring"], ["ul", List, () => exec("insertUnorderedList"), "Daftar poin"], ["ol", ListOrdered, () => exec("insertOrderedList"), "Daftar angka"], ["link", Link2, link, "Tautan"]];
  return (
    <div ref={wrap} className={`rte ck-rich ${editable ? "" : "readonly"} ${className}`} data-testid={ids.root}>
      {editable && (
        <div className="rte-toolbar" role="toolbar">
          {tools.map(([k, Icon, fn, t]) => <button key={k} type="button" title={t} data-testid={`${ids.tool}-${k}`} onMouseDown={(e) => e.preventDefault()} onClick={fn}><Icon size={15} /></button>)}
          <i />
          <button type="button" title="Sisipkan foto" data-testid={`${ids.tool}-image`} onMouseDown={(e) => { e.preventDefault(); range.current = caretRange(ref.current); }} onClick={() => input.current?.click()}>
            {busy ? <Loader2 size={15} className="spin" /> : <ImagePlus size={15} />} {busy ? "Mengunggah…" : "Foto"}
          </button>
          <input ref={input} type="file" hidden multiple accept="image/png,image/jpeg,image/gif,image/webp" data-testid={ids.file} onChange={(e) => { addImages(e.target.files, range.current); e.target.value = ""; }} />
        </div>
      )}
      <div ref={ref} className="rte-editor ck-rich-editor" contentEditable={editable} suppressContentEditableWarning
        data-placeholder={editable ? placeholder : "Belum ada deskripsi."}
        data-testid={editable ? ids.input : ids.view}
        onBlur={save} onInput={onDraft ? save : undefined} onPaste={editable ? onPaste : undefined} onDrop={editable ? onDrop : undefined} onClick={onClick} />
      {editable && sel && <ImageTools img={sel} editor={ref.current} wrap={wrap.current} onDone={save} onPreview={() => showImage(sel.dataset.imageId)} />}
      <ImageLightbox image={open} onClose={() => setOpen(null)} />
    </div>
  );
};
