import React, { useEffect, useState } from "react";
import { FileDown, Pencil, Plus, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { api, useData, errorText, dateLabel, download } from "../lib/api";
import { Loading, ErrorState, Field, SaveButton, Empty, AddButton } from "./Common";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";
import { ItemsEditor, receiptTotals, rp } from "./ReceiptsTab";
import { DocPreview, ImagePicker, SignatureFields, SizeFields, setPath, uploadDocImages, useDocImages, usePreview } from "./docs/DocEditor";
import "./receipts.css";

const EMPTY_BANK = { bank_name: "", branch: "", account_number: "", account_holder: "" };

const BankAccountPicker = ({ form, setForm }) => {
  const { data, reload } = useData("/bank-accounts");
  const [adding, setAdding] = useState(false), [nb, setNb] = useState(EMPTY_BANK), [busy, setBusy] = useState(false);
  const accounts = data || [];
  const choose = (b) => setForm((f) => ({ ...f, bank_account_id: b?.id || "", bank_name: b?.bank_name || "", bank_branch: b?.branch || "",
    account_number: b?.account_number || "", account_holder: b?.account_holder || "" }));
  const add = async () => {
    if (!nb.bank_name.trim() || !nb.account_number.trim() || !nb.account_holder.trim()) { toast.error("Nama bank, no. rekening, dan atas nama wajib diisi."); return; }
    setBusy(true);
    try { const r = await api.post("/bank-accounts", nb); await reload(); choose(r.data); setNb(EMPTY_BANK); setAdding(false); toast.success("Rekening ditambahkan"); }
    catch (e) { toast.error(errorText(e)); }
    setBusy(false);
  };
  const remove = async (b) => {
    if (!window.confirm(`Hapus rekening ${b.bank_name} ${b.account_number} dari master?`)) return;
    try { await api.delete(`/bank-accounts/${b.id}`); reload(); toast.success("Rekening dihapus dari master"); }
    catch (e) { toast.error(errorText(e)); }
  };
  return (
    <div className="doc-bank" data-testid="invoice-bank-section">
      <span className="receipt-label">No. rekening pembayaran</span>
      <div className="doc-bank-row">
        <select value={form.bank_account_id || ""} data-testid="invoice-bank-select"
          onChange={(e) => choose(accounts.find((a) => a.id === e.target.value))}>
          <option value="">{form.bank_account_id || !form.account_number ? "— Pilih rekening —" : `${form.bank_name} · ${form.account_number} (tersimpan)`}</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.bank_name}{a.branch ? ` (${a.branch})` : ""} · {a.account_number} · a/n {a.account_holder}</option>)}
        </select>
        <button type="button" className="secondary-button receipt-add-item" data-testid="invoice-bank-add-toggle" onClick={() => setAdding(!adding)}>
          {adding ? <X size={14} /> : <Plus size={14} />} {adding ? "Batal" : "Tambah rekening"}
        </button>
      </div>
      {adding && (
        <div className="doc-bank-new" data-testid="invoice-bank-new">
          {[["bank_name", "Nama bank"], ["branch", "Cabang (opsional)"], ["account_number", "No. rekening"], ["account_holder", "Atas nama"]].map(([k, ph]) => (
            <input key={k} placeholder={ph} value={nb[k]} data-testid={`bank-new-${k}`} onChange={(e) => setNb({ ...nb, [k]: e.target.value })} />
          ))}
          <button type="button" className="primary-button" disabled={busy} data-testid="bank-new-save" onClick={add}>Simpan ke master</button>
        </div>
      )}
      {adding && accounts.length > 0 && (
        <div className="doc-bank-list" data-testid="invoice-bank-list">
          {accounts.map((a) => (
            <div key={a.id}><span>{a.bank_name} · {a.account_number}</span>
              <button type="button" className="icon-button danger" title="Hapus dari master" data-testid={`bank-delete-${a.id}`} onClick={() => remove(a)}><Trash2 size={14} /></button>
            </div>
          ))}
        </div>
      )}
      <small className="form-note">Pilih dari master rekening. Teks bank juga bisa diubah langsung di preview khusus untuk invoice ini.</small>
    </div>
  );
};

const InvoiceForm = ({ p, invoice, open, onClose, onSaved }) => {
  const [form, setForm] = useState(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const base = `/projects/${p.id}/invoices`;
  const imgs = useDocImages(base, invoice, form?.show_signature);
  const { elements, loading } = usePreview(`${base}/preview`, form, imgs.extra);
  useEffect(() => {
    if (!open) return;
    setErr(""); imgs.reset(); setForm(null);
    if (invoice) setForm({ ...invoice });
    else api.get(`${base}/new`).then((r) => setForm(r.data)).catch((e) => setErr(errorText(e)));
  }, [open, invoice, base]);
  const change = (e) => setForm({ ...form, [e.target.name]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const setField = (path, value) => setForm((f) => setPath(f, path, value));
  const save = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    const body = { ...form, items: form.items.map((i) => ({ ...i, qty: Number(i.qty), price: Number(i.price) })),
      ppn_rate: Number(form.ppn_rate), pph_rate: Number(form.pph_rate), remove_logo: imgs.logoRemoved, remove_signature: imgs.signRemoved };
    let r;
    try { r = invoice ? await api.patch(`${base}/${invoice.id}`, body) : await api.post(base, body); }
    catch (e) { setErr(errorText(e)); setBusy(false); return; }
    await uploadDocImages(base, r.data.id, imgs, (label, e) => toast.error(`Invoice tersimpan, tapi ${label} gagal diunggah: ${errorText(e)}`));
    toast.success(invoice ? "Invoice diperbarui" : "Invoice dibuat");
    setBusy(false); onSaved(); onClose();
  };
  const t = form ? receiptTotals(form) : null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent onEscapeKeyDown={(e) => { if (document.activeElement?.closest(".doc-inline")) e.preventDefault(); }} className="app-modal receipt-modal doc-modal" data-testid="invoice-form-modal">
        <DialogHeader>
          <DialogTitle data-testid="modal-title">{invoice ? "Edit invoice" : "Buat invoice"}</DialogTitle>
          <DialogDescription>Data diambil dari project bila ada; lengkapi atau ubah langsung di form maupun di preview.</DialogDescription>
        </DialogHeader>
        {!form ? (err ? <p className="form-error" data-testid="invoice-form-error">{err}</p> : <Loading />) : (
          <div className="doc-editor">
            <form onSubmit={save} className="receipt-form" data-testid="invoice-form">
              <div className="form-grid">
                <Field label="Nomor invoice" name="number" value={form.number} onChange={change} hint={false} />
                <Field label="Tanggal invoice" name="date" type="date" required value={form.date} onChange={change} />
              </div>
              <Field label="Kepada (nama perusahaan / instansi)" name="to_name" required maxLength={200} placeholder="Nama instansi / klien" value={form.to_name} onChange={change} />
              <ImagePicker label="Logo penerima" testid="invoice-logo" url={imgs.logo} hasOwn={Boolean(imgs.logo)} onFile={imgs.pickLogo} onRemove={imgs.dropLogo}
                note='Tampil di kiri nama perusahaan pada bagian "Kepada". PNG/JPG/WEBP, maks 3 MB.' />
              <div className="form-grid">
                <Field label="Jabatan / bagian" name="to_title" maxLength={200} placeholder="mis. Pejabat Pemutus Pengadaan" value={form.to_title} onChange={change} />
                <Field label="Alamat" name="to_address" as="textarea" rows={2} maxLength={400} value={form.to_address} onChange={change} />
              </div>
              <ItemsEditor items={form.items} setItems={(items) => setForm({ ...form, items })} />
              <div className="receipt-taxes">
                <label className="receipt-tax" data-testid="invoice-ppn">
                  <input type="checkbox" name="ppn_enabled" checked={form.ppn_enabled} onChange={change} data-testid="field-ppn_enabled" /> PPN
                  <input type="number" name="ppn_rate" min="0" max="50" step="any" value={form.ppn_rate} onChange={change} disabled={!form.ppn_enabled} data-testid="field-ppn_rate" />%
                </label>
                <label className="receipt-tax" data-testid="invoice-pph">
                  <input type="checkbox" name="pph_enabled" checked={form.pph_enabled} onChange={change} data-testid="field-pph_enabled" /> PPh 23
                  <input type="number" name="pph_rate" min="0" max="49" step="any" value={form.pph_rate} onChange={change} disabled={!form.pph_enabled} data-testid="field-pph_rate" />%
                </label>
              </div>
              <div className="receipt-summary" data-testid="invoice-summary">
                <span>Subtotal <b>{rp(t.sub)}</b></span>
                {form.ppn_enabled && <span>PPN <b>{rp(t.ppn)}</b></span>}
                {form.pph_enabled && <span>PPh 23 <b>{rp(t.pph)}</b></span>}
                <span className="receipt-total">Total <b data-testid="invoice-total">{rp(t.total)}</b></span>
              </div>
              <BankAccountPicker form={form} setForm={setForm} />
              <div className="form-grid">
                <Field label="Nama perusahaan" name="company_name" required value={form.company_name} onChange={change} />
                <Field label="Penandatangan" name="signer_name" required value={form.signer_name} onChange={change} />
                <Field label="Jabatan" name="signer_title" value={form.signer_title} onChange={change} />
              </div>
              <SignatureFields form={form} setField={setField} imgs={imgs} prefix="invoice" />
              <SizeFields form={form} setField={setField} imgs={imgs} />
              {err && <p className="form-error" data-testid="invoice-form-error">{err}</p>}
              <div className="form-actions"><SaveButton busy={busy} label={invoice ? "Simpan perubahan" : "Buat invoice"} /></div>
            </form>
            <DocPreview elements={elements} images={imgs.urls} form={form} onChange={setField} editable loading={loading} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export const InvoicesTab = ({ p, user }) => {
  const { data, loading, error, reload } = useData(`/projects/${p.id}/invoices`);
  const [edit, setEdit] = useState(undefined);
  const canWrite = ["Admin", "Accounting", "Admin Project"].includes(user.role);
  const fileName = (r, ext) => `Invoice-${r.number.replace(/[^A-Za-z0-9_-]+/g, "-")}.${ext}`;
  const remove = async (r) => {
    if (!window.confirm(`Hapus invoice ${r.number}?`)) return;
    try { await api.delete(`/projects/${p.id}/invoices/${r.id}`); toast.success("Invoice dihapus"); reload(); }
    catch (e) { toast.error(errorText(e)); }
  };
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} reload={reload} />;
  return (
    <div data-testid="invoices-tab">
      <div className="receipt-head">
        <div>
          <h2 className="detail-heading">Invoice</h2>
          <p className="form-note">Buat invoice sesuai template CV Mai Harta, lalu unduh sebagai DOCX atau PDF.</p>
        </div>
        {canWrite && <AddButton id="invoice-create" onClick={() => setEdit(null)}>Buat invoice</AddButton>}
      </div>
      {!data.length ? <Empty message="Belum ada invoice untuk project ini." /> : (
        <div className="table-wrap">
          <table className="data-table" data-testid="invoices-table">
            <thead><tr><th>Nomor</th><th>Tanggal</th><th>Kepada</th><th>Total</th><th /></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.id} data-testid={`invoice-row-${r.id}`}>
                  <td data-testid="invoice-number">{r.number}</td>
                  <td>{dateLabel(r.date)}</td>
                  <td>{r.to_name}</td>
                  <td><b>{rp(r.total)}</b></td>
                  <td className="receipt-actions">
                    <button className="secondary-button" data-testid={`invoice-docx-${r.id}`} onClick={() => download(`/projects/${p.id}/invoices/${r.id}/docx`, fileName(r, "docx"))}><FileDown size={14} /> DOCX</button>
                    <button className="secondary-button" data-testid={`invoice-pdf-${r.id}`} onClick={() => download(`/projects/${p.id}/invoices/${r.id}/pdf`, fileName(r, "pdf"))}><FileDown size={14} /> PDF</button>
                    {canWrite && <button className="icon-button" title="Edit" data-testid={`invoice-edit-${r.id}`} onClick={() => setEdit(r)}><Pencil size={15} /></button>}
                    {canWrite && <button className="icon-button danger" title="Hapus" data-testid={`invoice-delete-${r.id}`} onClick={() => remove(r)}><Trash2 size={15} /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <InvoiceForm p={p} invoice={edit || null} open={edit !== undefined} onClose={() => setEdit(undefined)} onSaved={reload} />
    </div>
  );
};
