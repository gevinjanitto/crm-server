import React, { useEffect, useState } from 'react';
import { Bell, Mail, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';
import { api, errorText, useData } from '../lib/api';
import { Field, Loading, ErrorState } from './Common';
import { Button } from './ui/button';
import { Switch } from './ui/switch';
import { NotificationTestDialog } from './NotificationTestDialog';
import { useAuth } from '../App';
import './notification-settings.css';

export const NotificationSettings = () => {
  const settings = useData('/account/notifications');
  const isAdmin = useAuth().user?.role === 'Admin';
  const [form, setForm] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState('');
  useEffect(() => { if (settings.data) setForm(settings.data); }, [settings.data]);
  const save = async e => {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const { in_app, email, whatsapp, whatsapp_number } = form;
      await api.patch('/account/notifications', { in_app, email, whatsapp, whatsapp_number });
      toast.success('Preferensi notifikasi disimpan'); await settings.reload();
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  if (settings.loading) return <Loading/>;
  if (settings.error) return <ErrorState error={settings.error} reload={settings.reload}/>;
  if (!form) return null;
  return <section className="panel panel-padding notification-settings" data-testid="notification-settings">
    <div className="section-heading"><div><h2 data-testid="notification-settings-heading">Notifikasi akun</h2><p data-testid="notification-settings-subtitle">Tetap terhubung dengan pekerjaan Anda.</p></div><Bell size={18}/></div>
    <form onSubmit={save} data-testid="notification-settings-form">
      <p className="form-note" data-testid="notification-registered-email">Email terdaftar: {form.registered_email}</p>
      <div className="notification-channel-list">
        {[['in_app','Dalam aplikasi',Bell], ['email','Email',Mail], ['whatsapp','WhatsApp',MessageCircle]].map(([key,label,Icon]) => <label className="notification-channel" key={key} data-testid={`notification-channel-${key}`}>
          <span className="notification-channel-name"><Icon size={17}/>{label}</span><Switch data-testid={`notification-toggle-${key}`} checked={form[key]} onCheckedChange={value => setForm({...form,[key]:value})} aria-label={`Notifikasi ${label}`}/>
        </label>)}
      </div>
      <Field label="Nomor WhatsApp terdaftar" name="notification_whatsapp_number" data-testid="notification-whatsapp-number" type="tel" autoComplete="tel" value={form.whatsapp_number} placeholder="+628123456789" onChange={e => setForm({...form,whatsapp_number:e.target.value})} required={form.whatsapp}/>
      {form.whatsapp && <p className="form-note" data-testid="notification-whatsapp-consent">Saya menyetujui notifikasi akun pada nomor ini dan dapat menonaktifkannya kapan saja.</p>}
      {isAdmin && <NotificationTestDialog disabled={busy}/>}
      {isAdmin && <div className="notification-providers" data-testid="notification-provider-status">
        {[['email',form.email_provider || 'Gmail via n8n'],['whatsapp','n8n + WAHA']].map(([channel,label]) => <div className="notification-provider" key={channel} data-testid={`notification-provider-${channel}`}>
          <span><i className={form[`${channel}_configured`] ? 'provider-ready' : ''}/><b data-testid={`notification-provider-name-${channel}`}>{label}</b><small data-testid={`notification-provider-state-${channel}`}>{form[`${channel}_configured`] ? 'Konfigurasi tersedia' : 'Belum aktif'}</small></span>
          <p data-testid={`notification-provider-note-${channel}`}>{form[`${channel}_configuration_note`] || 'Koneksi pengiriman dapat diperiksa melalui tombol Uji notifikasi.'}</p>
        </div>)}
      </div>}
      {error && <p className="form-error" role="alert" data-testid="notification-settings-error">{error}</p>}
      <div className="form-actions"><Button className="primary-button" data-testid="notification-save" type="submit" disabled={busy}>{busy ? 'Menyimpan...' : 'Simpan notifikasi'}</Button></div>
    </form>
  </section>;
};