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
  return <div className="wa-template" data-testid="wa-template-card">
    <div className="wa-template-head"><MessageCircle size={15}/><b>Template WhatsApp (Twilio)</b>
      <span className={`wa-template-badge ${tone(t.status)}`} data-testid="wa-template-status">{t.status_label}</span></div>
    {t.content_sid && <p data-testid="wa-template-sid">{t.name} · {t.content_sid}</p>}
    {t.rejection_reason && <p data-testid="wa-template-rejection">Alasan ditolak: {t.rejection_reason}</p>}
    {t.outdated && <p data-testid="wa-template-outdated">Isi template di aplikasi berubah — sinkronkan ulang.</p>}
    <p data-testid="wa-template-note">{t.status === 'approved' ? 'WhatsApp dikirim memakai template ini.' : 'WhatsApp di luar jendela 24 jam (dan akun Twilio Trial) wajib memakai template yang disetujui. Persetujuan Meta bisa memakan waktu menit hingga 1–2 hari.'}</p>
    <div className="wa-template-actions">
      <Button type="button" variant="outline" data-testid="wa-template-sync" disabled={!!busy} onClick={() => run('sync')}><UploadCloud size={14}/>{busy === 'sync' ? 'Menyinkronkan...' : 'Sinkronkan ke Twilio'}</Button>
      {t.content_sid && <Button type="button" variant="outline" data-testid="wa-template-refresh" disabled={!!busy} onClick={() => run('refresh')}><RefreshCw size={14}/>Periksa status</Button>}
    </div>
  </div>;
};
