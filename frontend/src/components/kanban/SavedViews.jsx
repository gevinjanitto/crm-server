import React, { useState } from 'react';
import { Bookmark, Plus, X, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { api, errorText, useData } from '../../lib/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

export const SavedViews = ({ projectId, filters, view, onApply }) => {
  const base = `/projects/${projectId}/task-views`;
  const { data, error, reload } = useData(base);
  const [open, setOpen] = useState(false), [name, setName] = useState(''), [busy, setBusy] = useState(false);
  const save = async (e) => {
    e.preventDefault(); if (!name.trim()) return;
    setBusy(true);
    try { await api.post(base, { name: name.trim(), filters, view }); await reload(); setOpen(false); setName(''); toast.success('Tampilan pribadi disimpan'); }
    catch (e) { toast.error(errorText(e)); }
    finally { setBusy(false); }
  };
  const remove = async (id) => {
    if (!window.confirm('Hapus tampilan tersimpan ini? Task tidak akan dihapus.')) return;
    try { await api.delete(`${base}/${id}`); await reload(); toast.success('Tampilan dihapus'); }
    catch (e) { toast.error(errorText(e)); }
  };
  return <div className="ck-saved-views" data-testid="saved-views">
    <span className="ck-saved-label" data-testid="saved-views-label"><Bookmark size={14} /> Tampilan pribadi</span>
    {(data || []).map(item => <span className="ck-saved-item" key={item.id}><button type="button" data-testid={`saved-view-${item.id}`} onClick={() => onApply(item)}>{item.name}</button><button type="button" title="Hapus tampilan" data-testid={`delete-view-${item.id}`} onClick={() => remove(item.id)}><X size={12} /></button></span>)}
    <button className="ck-clear" data-testid="save-view-open" onClick={() => setOpen(true)}><Plus size={14} /> Simpan tampilan</button>
    {error && <button className="ck-clear ck-overdue" data-testid="saved-views-retry" onClick={reload}>Gagal memuat. Coba lagi</button>}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="app-modal" data-testid="save-view-dialog"><DialogHeader><DialogTitle data-testid="save-view-title">Simpan tampilan pribadi</DialogTitle><DialogDescription data-testid="save-view-description">{view === 'timeline' ? 'Timeline' : view === 'board' ? 'Board' : view === 'list' ? 'List' : view === 'calendar' ? 'Kalender' : 'Dashboard'} · Hanya untuk akun Anda</DialogDescription></DialogHeader><form onSubmit={save}><label className="form-field"><span>Nama tampilan</span><Input autoFocus required maxLength={60} data-testid="saved-view-name" placeholder="Contoh: Prioritas minggu ini" value={name} onChange={e => setName(e.target.value)} /></label><div className="form-actions"><Button type="button" variant="outline" data-testid="save-view-cancel" onClick={() => setOpen(false)}>Batal</Button><Button type="submit" data-testid="save-view-submit" disabled={busy || !name.trim()}>{busy ? <Loader2 size={15} className="spin" /> : <Bookmark size={15} />} Simpan</Button></div></form></DialogContent></Dialog>
  </div>;
};