import React, { useState } from 'react';
import { CheckCircle2, Clock3, Mail, MessageCircle, RefreshCw, Send, XCircle, MinusCircle } from 'lucide-react';
import { api, errorText, useData } from '../lib/api';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';

const statusInfo = {
  accepted: ['Diterima layanan', 'ok', CheckCircle2], failed: ['Gagal', 'fail', XCircle],
  skipped: ['Tidak dikirim', 'skip', MinusCircle], unknown: ['Perlu diperiksa', 'wait', Clock3],
};

const DeliveryRow = ({ row }) => {
  const [label, tone, Icon] = statusInfo[row.status] || [row.status, 'skip', MinusCircle];
  const Channel = row.channel === 'email' ? Mail : MessageCircle;
  return <li className={`test-delivery tone-${tone}`} data-testid={`delivery-${row.id}`}>
    <span className="test-delivery-channel"><Channel size={16}/></span>
    <div><b>{row.channel === 'email' ? 'Email' : 'WhatsApp'} <em><Icon size={13}/>{label}</em></b>
      <small>{row.reason || new Date(row.created_at).toLocaleString('id-ID')}</small></div>
  </li>;
};

const DailyStats = ({ data }) => <div className="notification-daily" data-testid="notification-daily-stats">
  <div data-testid="notification-daily-email"><Mail size={15}/><span>Email terkirim hari ini</span><b>{data?.email ?? '-'}<small> / {data?.email_daily_limit ?? 500}</small></b></div>
  <div data-testid="notification-daily-whatsapp"><MessageCircle size={15}/><span>WhatsApp terkirim hari ini</span><b>{data?.whatsapp ?? '-'}</b></div>
  <p>Semua akun · dihitung ulang setiap pukul 00.00 WITA</p>
</div>;

export const NotificationTestDialog = ({ disabled }) => {
  const history = useData('/account/notifications/deliveries');
  const stats = useData('/account/notifications/daily-stats');
  const [open, setOpen] = useState(false), [testing, setTesting] = useState(false), [result, setResult] = useState(null);
  const run = async () => {
    setTesting(true); setResult(null);
    try { const r = await api.post('/account/notifications/test'); setResult({ ok: true, text: r.data.message }); }
    catch (e) { setResult({ ok: false, text: errorText(e) }); }
    finally { setTesting(false); history.reload(); stats.reload(); }
  };
  const openDialog = () => { setOpen(true); setResult(null); history.reload(); stats.reload(); };
  return <>
    <div className="notification-test-row" data-testid="notification-test-row">
      <Button type="button" variant="outline" data-testid="notification-test-open" disabled={disabled} onClick={openDialog}><Send size={14}/>Uji notifikasi</Button>
      <small>Kirim pesan uji ke email & WhatsApp yang sudah disimpan.</small>
    </div>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="notification-test-dialog" data-testid="notification-test-dialog">
        <DialogHeader>
          <DialogTitle data-testid="notification-test-title">Uji notifikasi</DialogTitle>
          <DialogDescription>Pengujian memakai pengaturan yang sudah disimpan. Maksimal satu uji per menit.</DialogDescription>
        </DialogHeader>
        <DailyStats data={stats.data}/>
        <div className="notification-test-actions">
          <Button className="primary-button" data-testid="notification-test" disabled={testing} onClick={run}><Send size={14}/>{testing ? 'Mengirim...' : 'Kirim uji sekarang'}</Button>
          <button type="button" className="icon-button" data-testid="notification-refresh-history" title="Muat ulang pengiriman" onClick={history.reload}><RefreshCw size={15}/></button>
        </div>
        {result && <p className={`notification-test-result ${result.ok ? 'is-ok' : 'is-fail'}`} role="status" data-testid="notification-test-result">{result.text}</p>}
        <h3 className="notification-test-subhead" data-testid="notification-history-heading">Pengiriman terakhir</h3>
        {history.error && <p className="form-error" data-testid="notification-history-error">{history.error}</p>}
        <ul className="notification-test-list" data-testid="notification-deliveries">{(history.data || []).slice(0, 6).map(row => <DeliveryRow row={row} key={row.id}/>)}</ul>
        {!history.data?.length && <p className="form-note" data-testid="notification-deliveries-empty">Belum ada pengiriman eksternal.</p>}
        <p className="form-note" data-testid="notification-acceptance-note">Diterima layanan berarti Gmail/WAHA sudah menerima pesan untuk dikirim.</p>
      </DialogContent>
    </Dialog>
  </>;
};
