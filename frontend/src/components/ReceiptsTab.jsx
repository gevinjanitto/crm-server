import React, { useEffect, useState } from "react";
import { FileDown, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText, dateLabel, download } from "../lib/api";
import { Loading, ErrorState, Field, MoneyInput, SaveButton, Empty, AddButton } from "./Common";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { DocPreview, ImagePicker, SignatureFields, SizeFields, setPath, uploadDocImages, useDocImages, usePreview } from "./docs/DocEditor";
import "./receipts.css";

export const rp = (n) => "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(n || 0)) + ",00";
const r0 = (x) => Math.floor(x + 0.5);
export const receiptTotals = (f) => {
  const sub = f.items.reduce((s, i) => s + r0(Number(i.qty || 0) * Number(i.price || 0)), 0);
  const ppn = f.ppn_enabled ? r0((sub * Number(f.ppn_rate || 0)) / 100) : 0;
  const pph = f.pph_enabled ? r0((sub * Number(f.pph_rate || 0)) / (100 - Number(f.pph_rate || 0))) : 0;
  return { sub, ppn, pph, total: sub + ppn + pph };
};

export const ItemsEditor = ({ items, setItems }) => {
  const set = (i, k, v) => setItems(items.map((it, j) => (j === i ? { ...it, [k]: v } : it)));
  return (
    <div className="receipt-items" data-testid="receipt-items">
      <span className="receipt-label">Rincian <em className="req-mark">*</em></span>
      {items.map((it, i) => (
        <div className="receipt-item-row" key={i} data-testid={`receipt-item-${i}`}>
          <textarea rows={2} required placeholder="Deskripsi" value={it.description} data-testid={`receipt-item-desc-${i}`}
            onChange={(e) => set(i, "description", e.target.value)} />
          <input type="number" min="0.01" step="any" required value={it.qty} title="Qty" data-testid={`receipt-item-qty-${i}`}
            onChange={(e) => set(i, "qty", e.target.value)} />
          <MoneyInput name={`receipt-item-price-${i}`} value={it.price} onChange={(e) => set(i, "price", e.target.value)} />
          <button type="button" className="icon-button danger" disabled={items.length === 1} title="Hapus baris"
            data-testid={`receipt-item-remove-${i}`} onClick={() => setItems(items.filter((_, j) => j !== i))}><Trash2 size={15} /></button>
        </div>
      ))}
      {items.length < 6 && (
        <button type="button" className="secondary-button receipt-add-item" data-testid="receipt-item-add"
          onClick={() => setItems([...items, { description: "", qty: 1, price: 0 }])}><Plus size={14} /> Tambah baris</button>
      )}
    </div>
  );
};

const ReceiptForm = ({ p, receipt, open, onClose, onSaved }) => {
  const [form, setForm] = useState(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const base = `/projects/${p.id}/receipts`;
  const imgs = useDocImages(base, receipt, form?.show_signature);
  const { elements, loading } = usePreview(`${base}/preview`, form, imgs.extra);
  useEffect(() => {
    if (!open) return;
    setErr(""); imgs.reset(); setForm(null);
    if (receipt) setForm({ show_signature: false, logo_scale: 100, client_logo_scale: 100, sign_scale: 100, ...receipt });
    else api.get(`${base}/new`).then((r) => setForm(r.data)).catch((e) => setErr(errorText(e)));
  }, [open, receipt, base]);
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const setField = (path, value) => setForm((f) => setPath(f, path, value));
  const save = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    const body = { ...form, items: form.items.map((i) => ({ ...i, qty: Number(i.qty), price: Number(i.price) })),
      ppn_rate: Number(form.ppn_rate), pph_rate: Number(form.pph_rate), remove_logo: imgs.logoRemoved, remove_signature: imgs.signRemoved };
    let r;
    try {
      r = receipt ? await api.patch(`${base}/${receipt.id}`, body) : await api.post(base, body);
    } catch (e) { setErr(errorText(e)); setBusy(false); return; }
    await uploadDocImages(base, r.data.id, imgs, (label, e) => toast.error(`Kwitansi tersimpan, tapi ${label} gagal diunggah: ${errorText(e)}`));
    toast.success(receipt ? "Kwitansi diperbarui" : "Kwitansi dibuat");
    setBusy(false); onSaved(); onClose();
  };
  const t = form ? receiptTotals(form) : null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent onEscapeKeyDown={(e) => { if (document.activeElement?.closest(".doc-inline")) e.preventDefault(); }} className="app-modal receipt-modal doc-modal" data-testid="receipt-form-modal">
        <DialogHeader>
          <DialogTitle data-testid="modal-title">{receipt ? "Edit kwitansi" : "Buat kwitansi"}</DialogTitle>
          <DialogDescription>Data diambil dari project bila ada; lengkapi atau ubah langsung di form maupun di preview.</DialogDescription>
        </DialogHeader>
        {!form ? (err ? <p className="form-error" data-testid="receipt-form-error">{err}</p> : <Loading />) : (
          <div className="doc-editor">
            <form onSubmit={save} className="receipt-form" data-testid="receipt-form">
              <div className="form-grid">
                <Field label="Nomor kwitansi" name="number" value={form.number} onChange={change} hint={false} />
                <Field label="Tanggal" name="date" type="date" required value={form.date} onChange={change} />
              </div>
              <Field label="Diterima dari" name="received_from" required maxLength={200} placeholder="Nama instansi / klien" value={form.received_from} onChange={change} />
              <ImagePicker label="Logo penerima" testid="receipt-logo" url={imgs.logo} hasOwn={Boolean(imgs.logo)} onFile={imgs.pickLogo} onRemove={imgs.dropLogo}
                note='Tampil di samping nama pada bagian "Diterima dari". PNG/JPG/WEBP, maks 3 MB.' />
              <ItemsEditor items={form.items} setItems={(items) => setForm({ ...form, items })} />
              <div className="receipt-taxes">
                <label className="receipt-tax" data-testid="receipt-ppn">
                  <input type="checkbox" name="ppn_enabled" checked={form.ppn_enabled} onChange={change} data-testid="field-ppn_enabled" /> PPN
                  <input type="number" name="ppn_rate" min="0" max="50" step="any" value={form.ppn_rate} onChange={change} disabled={!form.ppn_enabled} data-testid="field-ppn_rate" />%
                </label>
                <label className="receipt-tax" data-testid="receipt-pph">
                  <input type="checkbox" name="pph_enabled" checked={form.pph_enabled} onChange={change} data-testid="field-pph_enabled" /> PPh 23
                  <input type="number" name="pph_rate" min="0" max="49" step="any" value={form.pph_rate} onChange={change} disabled={!form.pph_enabled} data-testid="field-pph_rate" />%
                </label>
              </div>
              <div className="receipt-summary" data-testid="receipt-summary">
                <span>Subtotal <b>{rp(t.sub)}</b></span>
                {form.ppn_enabled && <span>PPN <b>{rp(t.ppn)}</b></span>}
                {form.pph_enabled && <span>PPh 23 <b>{rp(t.pph)}</b></span>}
                <span className="receipt-total">Total <b data-testid="receipt-total">{rp(t.total)}</b></span>
              </div>
              <div className="form-grid">
                <Field label="Nama perusahaan" name="company_name" required value={form.company_name} onChange={change} />
                <Field label="Penandatangan" name="signer_name" required value={form.signer_name} onChange={change} />
                <Field label="Jabatan" name="signer_title" value={form.signer_title} onChange={change} />
              </div>
              <SignatureFields form={form} setField={setField} imgs={imgs} prefix="receipt" />
              <SizeFields form={form} setField={setField} imgs={imgs} />
              {err && <p className="form-error" data-testid="receipt-form-error">{err}</p>}
              <div className="form-actions"><SaveButton busy={busy} label={receipt ? "Simpan perubahan" : "Buat kwitansi"} /></div>
            </form>
            <DocPreview elements={elements} images={imgs.urls} form={form} onChange={setField} editable loading={loading} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export const ReceiptsTab = ({ p, user }) => {
  const { data, loading, error, reload } = useData(`/projects/${p.id}/receipts`);
  const [edit, setEdit] = useState(undefined);
  const canWrite = ["Admin", "Accounting", "Admin Project"].includes(user.role);
  const fileName = (r, ext) => `Kwitansi-${r.number.replace(/[^A-Za-z0-9_-]+/g, "-")}.${ext}`;
  const remove = async (r) => {
    if (!window.confirm(`Hapus kwitansi ${r.number}?`)) return;
    try { await api.delete(`/projects/${p.id}/receipts/${r.id}`); toast.success("Kwitansi dihapus"); reload(); }
    catch (e) { toast.error(errorText(e)); }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <div data-testid="receipts-tab">
      <div className="receipt-head">
        <div>
          <h2 className="detail-heading">Kwitansi</h2>
          <p className="form-note">Buat kwitansi sesuai template CV Mai Harta, lalu unduh sebagai DOCX atau PDF.</p>
        </div>
        {canWrite && <AddButton id="receipt-create" onClick={() => setEdit(null)}>Buat kwitansi</AddButton>}
      </div>
      {!data.length ? <Empty message="Belum ada kwitansi untuk project ini." /> : (
        <div className="table-wrap">
          <table className="data-table" data-testid="receipts-table">
            <thead><tr><th>Nomor</th><th>Tanggal</th><th>Diterima dari</th><th>Total</th><th /></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} data-testid={`receipt-row-${r.id}`}>
                  <td data-testid="receipt-number">{r.number}</td>
                  <td>{dateLabel(r.date)}</td>
                  <td>{r.received_from}</td>
                  <td><b>{rp(r.total)}</b></td>
                  <td className="receipt-actions">
                    <button className="secondary-button" data-testid={`receipt-docx-${r.id}`} onClick={() => download(`/projects/${p.id}/receipts/${r.id}/docx`, fileName(r, "docx"))}><FileDown size={14} /> DOCX</button>
                    <button className="secondary-button" data-testid={`receipt-pdf-${r.id}`} onClick={() => download(`/projects/${p.id}/receipts/${r.id}/pdf`, fileName(r, "pdf"))}><FileDown size={14} /> PDF</button>
                    {canWrite && <button className="icon-button" title="Edit" data-testid={`receipt-edit-${r.id}`} onClick={() => setEdit(r)}><Pencil size={15} /></button>}
                    {canWrite && <button className="icon-button danger" title="Hapus" data-testid={`receipt-delete-${r.id}`} onClick={() => remove(r)}><Trash2 size={15} /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <ReceiptForm p={p} receipt={edit || null} open={edit !== undefined} onClose={() => setEdit(undefined)} onSaved={reload} />
    </div>
  );
};
