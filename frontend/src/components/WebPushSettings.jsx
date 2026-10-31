import React, { useEffect, useState } from 'react';
import { BellRing, Download, Share } from 'lucide-react';
import { toast } from 'sonner';
import { api, errorText } from '../lib/api';
import { pushSupported, isIOS, isStandalone, syncSubscription, enablePush, disablePush } from '../lib/push';
import { Button } from './ui/button';
import { Switch } from './ui/switch';

const InstallApp = () => {
  const [prompt, setPrompt] = useState(window.__installPrompt || null);
  useEffect(() => {
    const on = () => setPrompt(window.__installPrompt);
    window.addEventListener('install-available', on);
    return () => window.removeEventListener('install-available', on);
  }, []);
  if (isStandalone()) return <p className="form-note" data-testid="install-app-installed">Aplikasi CRM sudah terpasang di perangkat ini.</p>;
  if (isIOS()) return <p className="form-note" data-testid="install-app-ios-hint"><Share size={14}/> iPhone/iPad: buka di Safari, ketuk <b>Bagikan</b> → <b>Tambah ke Layar Utama</b>, lalu buka CRM dari ikon tersebut untuk mengaktifkan notifikasi.</p>;
  if (!prompt) return <p className="form-note" data-testid="install-app-hint">Pasang sebagai aplikasi: pakai menu browser <b>Install / Tambahkan ke layar utama</b> (Chrome, Edge, Safari macOS).</p>;
  const install = async () => { prompt.prompt(); await prompt.userChoice; window.__installPrompt = null; setPrompt(null); };
  return <Button type="button" variant="outline" onClick={install} data-testid="install-app-button"><Download size={15}/> Pasang aplikasi CRM</Button>;
};

export const WebPushSettings = () => {
  const [on, setOn] = useState(false), [busy, setBusy] = useState(false), [ready, setReady] = useState(false);
  const supported = pushSupported();
  useEffect(() => { syncSubscription().then(setOn).catch(() => setOn(false)).finally(() => setReady(true)); }, []);
  const toggle = async (value) => {
    setBusy(true);
    try { value ? await enablePush() : await disablePush(); setOn(value); toast.success(value ? 'Notifikasi web aktif di perangkat ini' : 'Notifikasi web dimatikan di perangkat ini'); }
    catch (e) { toast.error(e.response ? errorText(e) : e.message); }
    finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true);
    try { toast.success((await api.post('/push/test')).data.message); } catch (e) { toast.error(errorText(e)); } finally { setBusy(false); }
  };
  return <div className="notification-webpush" data-testid="webpush-settings">
    <label className="notification-channel" data-testid="notification-channel-webpush">
      <span className="notification-channel-name"><BellRing size={17}/>Notifikasi web di perangkat ini</span>
      <Switch data-testid="notification-toggle-webpush" checked={on} disabled={!supported || busy || !ready} onCheckedChange={toggle} aria-label="Notifikasi web"/>
    </label>
    <p className="form-note" data-testid="webpush-note">{supported ? 'Muncul langsung di Windows, macOS, Android dan iOS walau tab CRM tertutup. Nyalakan di setiap perangkat yang dipakai.' : 'Browser ini belum mendukung notifikasi web. Di iPhone/iPad, pasang CRM ke Layar Utama dulu (iOS 16.4+).'}</p>
    <div className="notification-webpush-actions">
      <InstallApp/>
      {on && <Button type="button" variant="outline" onClick={test} disabled={busy} data-testid="webpush-test-button">Uji notifikasi web</Button>}
    </div>
  </div>;
};
