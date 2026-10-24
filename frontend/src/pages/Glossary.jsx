import React, { useState } from "react";
import { BookOpenText, Search, Pencil, Trash2, Download, FileText, Upload, RefreshCw, Check, X } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../App";
import { api, useData, errorText, download, dateLabel } from "../lib/api";
import { PageHead, AddButton, Loading, ErrorState, Empty, Modal, SaveButton, Field } from "../components/Common";
import RichTextEditor from "../components/RichTextEditor";
import { DocPreview, PreviewButton } from "../components/DocPreview";
import "./glossary.css";

const ACCEPT = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.png,.jpg,.jpeg,.webp,.gif,.zip,.rar";
const size = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const filesForm = (files) => {
  const f = new FormData();
  [...files].forEach((x) => f.append("files", x));
  return f;
};

const DocRow = ({ g, d, admin, onChange, onPreview }) => {
  const [name, setName] = useState(null);
  const base = `/glossary/${g.id}/documents/${d.id}`;
  const patch = async (form) => {
    try { onChange((await api.patch(base, form)).data); setName(null); toast.success("Dokumen diperbarui."); }
    catch (e) { toast.error(errorText(e)); }
  };
  const rename = () => { const f = new FormData(); f.append("name", name); patch(f); };
  const replace = (file) => { if (!file) return; const f = new FormData(); f.append("file", file); patch(f); };
  const remove = async () => {
    if (!window.confirm(`Hapus dokumen "${d.name}"?`)) return;
    try { await api.delete(base); onChange({ ...g, documents: g.documents.filter((x) => x.id !== d.id) }); toast.success("Dokumen dihapus."); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <li className="gl-doc" data-testid={`glossary-doc-${d.id}`}>
      <FileText size={16} />
      {name !== null ? (
        <input className="gl-doc-rename" autoFocus value={name} data-testid={`glossary-doc-rename-input-${d.id}`}
          onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), rename())} />
      ) : (
        <span className="gl-doc-name"><b>{d.name}</b><small>{size(d.size)} · {d.uploaded_by}</small></span>
      )}
      <div className="gl-doc-actions">
        {name !== null ? <>
          <button type="button" className="icon-button" title="Simpan nama" data-testid={`glossary-doc-rename-save-${d.id}`} onClick={rename}><Check size={15} /></button>
          <button type="button" className="icon-button" title="Batal" data-testid={`glossary-doc-rename-cancel-${d.id}`} onClick={() => setName(null)}><X size={15} /></button>
        </> : <>
          <PreviewButton testid={`glossary-doc-preview-${d.id}`} onClick={() => onPreview({ name: d.filename, path: `${base}/download`, type: d.content_type })} />
          <button type="button" className="icon-button" title="Unduh" data-testid={`glossary-doc-download-${d.id}`} onClick={() => download(`${base}/download`, d.filename)}><Download size={15} /></button>
          {admin && <>
            <button type="button" className="icon-button" title="Ubah nama" data-testid={`glossary-doc-rename-${d.id}`} onClick={() => setName(d.name)}><Pencil size={15} /></button>
            <label className="icon-button" title="Ganti file" data-testid={`glossary-doc-replace-${d.id}`}>
              <RefreshCw size={15} /><input type="file" hidden accept={ACCEPT} data-testid={`glossary-doc-replace-input-${d.id}`} onChange={(e) => replace(e.target.files[0])} />
            </label>
            <button type="button" className="icon-button danger" title="Hapus" data-testid={`glossary-doc-delete-${d.id}`} onClick={remove}><Trash2 size={15} /></button>
          </>}
        </>}
      </div>
    </li>
  );
};

const Documents = ({ g, admin, onChange }) => {
  const [busy, setBusy] = useState(false), [preview, setPreview] = useState(null);
  const upload = async (files) => {
    if (!files.length) return;
    setBusy(true);
    try { onChange((await api.post(`/glossary/${g.id}/documents`, filesForm(files))).data); toast.success(`${files.length} dokumen diunggah.`); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(false); }
  };
  return (
    <div className="gl-docs" data-testid="glossary-documents">
      <div className="gl-docs-head">
        <span>Dokumen ({g.documents.length})</span>
        {admin && <label className={`gl-upload ${busy ? "busy" : ""}`} data-testid="glossary-doc-upload">
          <Upload size={14} /> {busy ? "Mengunggah..." : "Unggah dokumen"}
          <input type="file" multiple hidden accept={ACCEPT} disabled={busy} data-testid="glossary-doc-upload-input" onChange={(e) => { upload([...e.target.files]); e.target.value = ""; }} />
        </label>}
      </div>
      {g.documents.length ? <ul>{g.documents.map((d) => <DocRow key={d.id} g={g} d={d} admin={admin} onChange={onChange} onPreview={setPreview} />)}</ul>
        : <p className="gl-muted" data-testid="glossary-no-docs">Belum ada dokumen.</p>}
      <DocPreview file={preview} onClose={() => setPreview(null)} />
    </div>
  );
};

const EntryForm = ({ entry, onClose, onSaved }) => {
  const [title, setTitle] = useState(entry?.title || ""), [desc, setDesc] = useState(entry?.description || "");
  const [files, setFiles] = useState([]), [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const body = { title, description: desc };
      let g = (entry ? await api.patch(`/glossary/${entry.id}`, body) : await api.post("/glossary", body)).data;
      if (files.length) g = (await api.post(`/glossary/${g.id}/documents`, filesForm(files))).data;
      toast.success(entry ? "Glosarium diperbarui." : "Glosarium ditambahkan.");
      onSaved(g);
    } catch (err) { toast.error(errorText(err)); }
    finally { setBusy(false); }
  };
  return (
    <form className="modal-form gl-form" onSubmit={submit} data-testid="glossary-form">
      <Field label="Judul" name="glossary-title" required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
      <div className="form-field"><span>Deskripsi</span>
        <RichTextEditor value={desc} onChange={setDesc} placeholder="Tulis penjelasan istilah..." testid="glossary-description" />
      </div>
      {!entry && <label className="form-field"><span>Dokumen <small className="opt-mark">(opsional, bisa lebih dari satu)</small></span>
        <input type="file" multiple accept={ACCEPT} data-testid="glossary-form-files" onChange={(e) => setFiles([...e.target.files])} />
        {files.length > 0 && <small className="gl-muted" data-testid="glossary-form-files-count">{files.length} file dipilih</small>}
      </label>}
      <div className="modal-actions">
        <button type="button" className="secondary-button" data-testid="glossary-form-cancel" onClick={onClose}>Batal</button>
        <SaveButton busy={busy} />
      </div>
    </form>
  );
};

const Entry = ({ g, admin, onEdit, onChange, onDelete }) => (
  <article className="gl-entry" data-testid={`glossary-entry-${g.id}`}>
    <header>
      <div>
        <h2 data-testid={`glossary-title-${g.id}`}>{g.title}</h2>
        <small>Diperbarui {dateLabel(g.updated_at)} oleh {g.updated_by}</small>
      </div>
      {admin && <div className="gl-entry-actions">
        <button type="button" className="icon-button" title="Edit" data-testid={`glossary-edit-${g.id}`} onClick={onEdit}><Pencil size={16} /></button>
        <button type="button" className="icon-button danger" title="Hapus" data-testid={`glossary-delete-${g.id}`} onClick={onDelete}><Trash2 size={16} /></button>
      </div>}
    </header>
    {g.description ? <div className="gl-desc ticket-description" data-testid={`glossary-desc-${g.id}`} dangerouslySetInnerHTML={{ __html: g.description }} />
      : <p className="gl-muted">Belum ada deskripsi.</p>}
    <Documents g={g} admin={admin} onChange={onChange} />
  </article>
);

export default function Glossary() {
  const { user } = useAuth(), admin = user.role === "Admin";
  const { data, loading, error, reload, setData } = useData("/glossary");
  const [q, setQ] = useState(""), [active, setActive] = useState(null), [form, setForm] = useState(null);
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const rows = data.filter((g) => (g.title + " " + (g.description_text || "")).toLowerCase().includes(q.toLowerCase()));
  const current = data.find((g) => g.id === active) || rows[0];
  const replace = (g) => setData((list) => (list.some((x) => x.id === g.id) ? list.map((x) => (x.id === g.id ? g : x)) : [...list, g].sort((a, b) => a.title.localeCompare(b.title))));
  const remove = async (g) => {
    if (!window.confirm(`Hapus glosarium "${g.title}" beserta semua dokumennya?`)) return;
    try { await api.delete(`/glossary/${g.id}`); setData((list) => list.filter((x) => x.id !== g.id)); toast.success("Glosarium dihapus."); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <>
      <PageHead eyebrow="KNOWLEDGE BASE" title="Glosarium" description={`${data.length} istilah & referensi bersama tim.`}>
        {admin && <AddButton id="add-glossary" onClick={() => setForm({})}>Glosarium baru</AddButton>}
      </PageHead>
      {!data.length ? <Empty message="Belum ada glosarium." /> : (
        <div className="gl-layout">
          <aside className="gl-index">
            <div className="list-search"><Search size={15} /><input data-testid="glossary-search" placeholder="Cari istilah..." value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <nav data-testid="glossary-list">
              {rows.map((g) => (
                <button key={g.id} type="button" className={current?.id === g.id ? "on" : ""} data-testid={`glossary-item-${g.id}`} onClick={() => setActive(g.id)}>
                  <BookOpenText size={15} /><span>{g.title}</span>{g.documents.length > 0 && <em>{g.documents.length}</em>}
                </button>
              ))}
              {!rows.length && <p className="gl-muted" data-testid="glossary-search-empty">Tidak ada yang cocok.</p>}
            </nav>
          </aside>
          {current && <Entry key={current.id} g={current} admin={admin} onEdit={() => setForm(current)} onChange={replace} onDelete={() => remove(current)} />}
        </div>
      )}
      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Edit glosarium" : "Glosarium baru"}>
        {form && <EntryForm entry={form.id ? form : null} onClose={() => setForm(null)} onSaved={(g) => { replace(g); setActive(g.id); setForm(null); }} />}
      </Modal>
    </>
  );
}
