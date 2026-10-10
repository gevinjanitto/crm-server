import React, { useRef, useState } from "react";
import { CalendarDays, Pencil, Trash2, BellRing, BellPlus, Paperclip, FileText, Download, X } from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText, dateLabel, download } from "../lib/api";
import { Loading, ErrorState, Empty, AddButton, Modal, Field, SaveButton } from "./Common";
import { Switch } from "./ui/switch";
import { remainingLabel, urgency } from "../pages/Reminders";
import { COMMENT_ACCEPT } from "./workspace/CommentFiles";
import { DocPreview, PreviewButton } from "./DocPreview";

const MAX_SIZE = 10 * 1024 * 1024;
const QUICK_DAYS = [1, 3, 7];
const today = () => new Date().toISOString().slice(0, 10);
const blank = () => ({ name: "", description: "", start_date: today(), end_date: "", extra_notify: false, extra_notify_days: "" });
const fromItem = (i) => ({ name: i.name, description: i.description || "", start_date: i.start_date, end_date: i.end_date, extra_notify: !!i.extra_notify, extra_notify_days: i.extra_notify_days || "" });
export const fileSize = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
export const attachmentPath = (r, a) => `/projects/${r.project_id}/reminders/${r.id}/attachments/${a.id}`;

export const ReminderFiles = ({ r, onRemove }) => {
  const [preview, setPreview] = useState(null);
  if (!r.attachments?.length) return null;
  return (
  <>
  <div className="reminder-files" data-testid={`reminder-files-${r.id}`}>
    {r.attachments.map((a) => (
      <span key={a.id} className="reminder-file">
        <button type="button" onClick={() => download(attachmentPath(r, a), a.name)} data-testid={`reminder-file-download-${a.id}`} title="Unduh">
          <FileText size={13} /><span>{a.name}</span><small>{fileSize(a.size)}</small><Download size={12} />
        </button>
        <PreviewButton className="doc-preview-inline" size={13} testid={`reminder-file-preview-${a.id}`} onClick={() => setPreview({ name: a.name, path: attachmentPath(r, a), type: a.content_type })} />
        {onRemove && <button type="button" className="reminder-file-remove" title="Hapus dokumen" onClick={() => onRemove(a)} data-testid={`reminder-file-remove-${a.id}`}><X size={12} /></button>}
      </span>
    ))}
  </div>
  <DocPreview file={preview} onClose={() => setPreview(null)} />
  </>
  );
};

const ExtraNotify = ({ form, setForm }) => (
  <div className="reminder-extra" data-testid="reminder-extra">
    <div className="reminder-extra-head">
      <div><b>Notif tambahan?</b><small>Notifikasi 2 minggu (14 hari) sebelum tanggal akhir tetap dikirim.</small></div>
      <Switch checked={form.extra_notify} onCheckedChange={(v) => setForm({ ...form, extra_notify: v, extra_notify_days: v ? form.extra_notify_days || 3 : "" })} data-testid="reminder-extra-toggle" />
    </div>
    {form.extra_notify && (
      <div className="reminder-extra-body">
        <div className="reminder-extra-chips">
          {QUICK_DAYS.map((d) => (
            <button type="button" key={d} className={Number(form.extra_notify_days) === d ? "active" : ""} onClick={() => setForm({ ...form, extra_notify_days: d })} data-testid={`reminder-extra-chip-${d}`}>{d} hari</button>
          ))}
        </div>
        <label className="reminder-extra-input">
          <input type="number" min={1} max={365} required value={form.extra_notify_days} onChange={(e) => setForm({ ...form, extra_notify_days: e.target.value })} data-testid="reminder-extra-days" />
          <span>hari sebelum tanggal akhir</span>
        </label>
      </div>
    )}
  </div>
);

const FilePicker = ({ files, setFiles }) => {
  const input = useRef(null);
  const add = (list) => {
    const big = list.filter((f) => f.size > MAX_SIZE);
    if (big.length) toast.error(`Maksimal 10 MB per dokumen: ${big.map((f) => f.name).join(", ")}`);
    setFiles((f) => [...f, ...list.filter((x) => x.size <= MAX_SIZE)].slice(0, 5));
  };
  return (
    <div className="form-field">
      <span>Dokumen<small className="opt-mark">(opsional, maks 10 MB per file, 5 file sekali upload)</small></span>
      <button type="button" className="reminder-upload" onClick={() => input.current?.click()} data-testid="reminder-upload-button"><Paperclip size={15} />Pilih dokumen (PDF, DOC, Excel, gambar…)</button>
      <input ref={input} type="file" hidden multiple accept={COMMENT_ACCEPT} data-testid="reminder-file-input" onChange={(e) => { add([...e.target.files]); e.target.value = ""; }} />
      {!!files.length && (
        <div className="reminder-files">
          {files.map((f, i) => (
            <span key={`${f.name}-${i}`} className="reminder-file picked" data-testid={`reminder-picked-${i}`}>
              <span className="reminder-file-name"><FileText size={13} /><span>{f.name}</span><small>{fileSize(f.size)}</small></span>
              <button type="button" className="reminder-file-remove" onClick={() => setFiles(files.filter((_, j) => j !== i))} data-testid={`reminder-picked-remove-${i}`}><X size={12} /></button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

const ReminderForm = ({ open, onClose, pid, item, onSaved }) => {
  const [form, setForm] = useState(blank()), [files, setFiles] = useState([]), [current, setCurrent] = useState(null), [busy, setBusy] = useState(false);
  React.useEffect(() => { if (open) { setForm(item ? fromItem(item) : blank()); setFiles([]); setCurrent(item); } }, [open, item]);
  const set = (e) => setForm({ ...form, [e.target.name]: e.target.value });
  const removeFile = async (a) => {
    if (!window.confirm(`Hapus dokumen "${a.name}"?`)) return;
    try { const r = await api.delete(attachmentPath(current, a)); setCurrent(r.data); onSaved(); toast.success("Dokumen dihapus"); }
    catch (e) { toast.error(errorText(e)); }
  };
  const submit = async (e) => {
    e.preventDefault();
    if (form.end_date < form.start_date) return toast.error("Tanggal akhir tidak boleh sebelum tanggal mulai.");
    const days = Number(form.extra_notify_days);
    if (form.extra_notify && (!days || days < 1)) return toast.error("Isi jumlah hari notifikasi tambahan.");
    if (form.extra_notify && days === 14) return toast.error("14 hari sudah menjadi notifikasi utama. Pilih jumlah hari lain.");
    const body = { ...form, extra_notify_days: form.extra_notify ? days : null };
    setBusy(true);
    try {
      const r = await (item ? api.patch(`/projects/${pid}/reminders/${item.id}`, body) : api.post(`/projects/${pid}/reminders`, body));
      if (files.length) {
        const fd = new FormData();
        files.forEach((f) => fd.append("files", f));
        try { await api.post(`/projects/${pid}/reminders/${r.data.id}/attachments`, fd); }
        catch (err) { toast.error(`Reminder tersimpan, tetapi dokumen gagal diunggah: ${errorText(err)}`); }
      }
      toast.success(item ? "Reminder diperbarui" : "Reminder ditambahkan");
      onSaved(); onClose();
    } catch (err) { toast.error(errorText(err)); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title={item ? "Edit reminder" : "Reminder baru"} description="Admin menerima notifikasi WhatsApp 2 minggu sebelum tanggal akhir, plus notif tambahan bila diaktifkan.">
      <form className="reminder-form" onSubmit={submit} data-testid="reminder-form">
        <Field label="Nama" name="name" required maxLength={200} value={form.name} onChange={set} placeholder="mis. Perpanjangan domain & hosting" />
        <Field label="Deskripsi" name="description" as="textarea" rows={3} maxLength={3000} value={form.description} onChange={set} placeholder="Catatan, nomor kontrak, detail tagihan, dll." />
        <div className="reminder-date-fields">
          <Field label="Tanggal mulai" name="start_date" type="date" required value={form.start_date} onChange={set} />
          <Field label="Tanggal akhir" name="end_date" type="date" required min={form.start_date} value={form.end_date} onChange={set} />
        </div>
        <ExtraNotify form={form} setForm={setForm} />
        {current && <ReminderFiles r={current} onRemove={removeFile} />}
        <FilePicker files={files} setFiles={setFiles} />
        <SaveButton busy={busy} />
      </form>
    </Modal>
  );
};

const ReminderItem = ({ r, onDone, onEdit, onDelete }) => (
  <li className={`project-reminder ${urgency(r)}`} data-testid={`project-reminder-${r.id}`}>
    <label className="reminder-check" title="Tandai selesai">
      <input type="checkbox" checked={false} onChange={() => onDone(r)} data-testid={`reminder-done-${r.id}`} aria-label={`Tandai ${r.name} selesai`} />
      <span aria-hidden="true" />
    </label>
    <div className="project-reminder-body">
      <b data-testid={`reminder-name-${r.id}`}>{r.name}</b>
      {r.description && <p data-testid={`reminder-description-${r.id}`}>{r.description}</p>}
      <small><CalendarDays size={13} />{dateLabel(r.start_date)} — {dateLabel(r.end_date)}
        {r.extra_notify && <span className="reminder-notified extra" data-testid={`reminder-extra-badge-${r.id}`} title="Notifikasi tambahan"><BellPlus size={12} />Notif tambahan H-{r.extra_notify_days}{r.extra_notified_at ? " (terkirim)" : ""}</span>}
        {r.notified_at && <span className="reminder-notified" title="Notifikasi admin 2 minggu sudah dikirim"><BellRing size={12} />Admin diberi tahu</span>}</small>
      <ReminderFiles r={r} />
    </div>
    <span className={`reminder-left ${urgency(r)}`} data-testid={`project-reminder-left-${r.id}`}>{remainingLabel(r)}</span>
    <div className="project-reminder-actions">
      <button className="icon-button" title="Edit" onClick={() => onEdit(r)} data-testid={`reminder-edit-${r.id}`}><Pencil size={15} /></button>
      <button className="icon-button danger" title="Hapus" onClick={() => onDelete(r)} data-testid={`reminder-delete-${r.id}`}><Trash2 size={15} /></button>
    </div>
  </li>
);

export const ProjectReminders = ({ p }) => {
  const { data, loading, error, reload, setData } = useData(`/projects/${p.id}/reminders`),
    [form, setForm] = useState({ open: false, item: null });
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  const done = async (r) => {
    if (!window.confirm(`Tandai "${r.name}" selesai? Reminder akan hilang dari project, tetapi tetap tercatat di laporan Reminder.`)) return;
    try {
      await api.patch(`/projects/${p.id}/reminders/${r.id}`, { done: true });
      setData(data.filter((x) => x.id !== r.id));
      toast.success("Reminder selesai dan dipindahkan ke laporan");
    } catch (e) { toast.error(errorText(e)); }
  };
  const remove = async (r) => {
    if (!window.confirm(`Hapus reminder "${r.name}"? Data dan dokumennya juga terhapus dari laporan.`)) return;
    try { await api.delete(`/projects/${p.id}/reminders/${r.id}`); setData(data.filter((x) => x.id !== r.id)); toast.success("Reminder dihapus"); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <section className="project-reminders" data-testid="project-reminders">
      <div className="section-head">
        <div><h2 className="detail-heading">Reminder project</h2><p className="project-reminders-sub">Diurutkan dari tanggal akhir terdekat. Centang bila sudah selesai.</p></div>
        <AddButton id="add-reminder" onClick={() => setForm({ open: true, item: null })}>Reminder baru</AddButton>
      </div>
      {data.length ? (
        <ul className="project-reminder-list">
          {data.map((r) => <ReminderItem key={r.id} r={r} onDone={done} onDelete={remove} onEdit={(item) => setForm({ open: true, item })} />)}
        </ul>
      ) : <Empty message="Tidak ada reminder yang berjalan." />}
      <ReminderForm open={form.open} item={form.item} pid={p.id} onClose={() => setForm({ open: false, item: null })} onSaved={reload} />
    </section>
  );
};
