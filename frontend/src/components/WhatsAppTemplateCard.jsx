import React, { useState } from 'react';
import { MessageCircle, RefreshCw, UploadCloud } from 'lucide-react';
import { toast } from 'sonner';
import { api, errorText, useData } from '../lib/api';
import { Button } from './ui/button';

const tone = s => (s === 'approved' ? 'is-approved' : ['rejected', 'disabled', 'paused'].includes(s) ? 'is-rejected' : ['pending', 'received'].includes(s) ? 'is-pending' : '');

export const WhatsAppTemplateCard = () => {
  const state = useData('/admin/whatsapp-template');
  const [busy, setBusy] = useState('');
  const run = async (kind) => {
    setBusy(kind);
    try { await api.post(`/admin/whatsapp-template/${kind}`); toast.success(kind === 'sync' ? 'Template dikirim ke Twilio' : 'Status template diperbarui'); await state.reload(); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(''); }
  };
  const t = state.data;
  if (!t) return state.error ? <p className="form-error" data-testid="wa-template-error">{state.error}</p> : null;
  if (t.sandbox) return <div className="wa-template" data-testid="wa-template-card">
    <div className="wa-template-head"><MessageCircle size={15}/><b>WhatsApp (Twilio Trial)</b>
      <span className={`wa-template-badge ${t.trial_content_sid ? 'is-approved' : 'is-pending'}`} data-testid="wa-template-status">{t.trial_content_sid ? 'Template Trial terpasang' : 'ContentSid belum diisi'}</span></div>
    {t.trial_content_sid && <p data-testid="wa-template-sid">Pengirim {t.sender} · {t.trial_content_sid}</p>}
    <p data-testid="wa-template-note">Akun Trial hanya bisa mengirim template bawaan Twilio (isi pesan mengikuti template itu, bukan teks CRM). Buka Twilio Console → Try it out → <b>Send a WhatsApp message</b>, salin <b>ContentSid</b> (HX...) ke <b>TWILIO_CONTENT_SID</b> dan, bila ada, <b>ContentVariables</b> ke <b>TWILIO_CONTENT_VARIABLES</b> di backend/.env, lalu restart backend. Nomor penerima wajib terverifikasi dan sudah mengirim pesan join ke {t.sender}. Setelah upgrade, isi pesan CRM lengkap memakai template sendiri.</p>
  </div>;
  return <div className="wa-template" data-testid="wa-template-card">
    <div className="wa-template-head"><MessageCircle size={15}/><b>Template WhatsApp (Twilio)</b>
      <span className={`wa-template-badge ${tone(t.status)}`} data-testid="wa-template-status">{t.status_label}</span></div>
    {t.content_sid && <p data-testid="wa-template-sid">{t.name} · {t.content_sid}</p>}
    {t.rejection_reason && <p data-testid="wa-template-rejection">Alasan ditolak: {t.rejection_reason}</p>}
    {t.category && <p data-testid="wa-template-category">Kategori dari Meta: <b>{t.category}</b>{t.category.toUpperCase() === 'MARKETING' ? ' — tekan "Sinkronkan ke Twilio" untuk membuat template UTILITY baru (template lama tetap dipakai sampai yang baru disetujui).' : ''}</p>}
    {t.outdated && <p data-testid="wa-template-outdated">Isi template di aplikasi berubah — sinkronkan ulang.{t.status === 'approved' ? ' Template lama tetap dipakai sampai template baru disetujui.' : ''}</p>}
    {t.pending_content_sid && <p data-testid="wa-template-pending">Template baru: <span className={`wa-template-badge ${tone(t.pending_status)}`} data-testid="wa-template-pending-status">{t.pending_status_label}</span> {t.pending_name} · {t.pending_content_sid}. {['rejected', 'disabled'].includes(t.pending_status) ? `Ditolak${t.pending_rejection_reason ? ': ' + t.pending_rejection_reason : ''} — template lama tetap dipakai.` : 'Template lama tetap dipakai; template baru dipasang otomatis begitu disetujui.'}</p>}
    <p data-testid="wa-template-note">{t.status === 'approved' ? 'WhatsApp dikirim memakai template ini.' : 'WhatsApp di luar jendela 24 jam (dan akun Twilio Trial) wajib memakai template yang disetujui. Persetujuan Meta bisa memakan waktu menit hingga 1–2 hari.'}</p>
    <div className="wa-template-actions">
      <Button type="button" variant="outline" data-testid="wa-template-sync" disabled={!!busy} onClick={() => run('sync')}><UploadCloud size={14}/>{busy === 'sync' ? 'Menyinkronkan...' : 'Sinkronkan ke Twilio'}</Button>
      {t.content_sid && <Button type="button" variant="outline" data-testid="wa-template-refresh" disabled={!!busy} onClick={() => run('refresh')}><RefreshCw size={14}/>Periksa status</Button>}
    </div>
  </div>;
};
