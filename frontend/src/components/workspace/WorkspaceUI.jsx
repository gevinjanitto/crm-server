import React, { useState } from 'react';
import { Plus, Loader2, Trash2, X, FolderOpen } from 'lucide-react';
import { toast } from 'sonner';
import { api, errorText } from '../../lib/api';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';

export const useMutation = (reload) => {
  const [busy, setBusy] = useState(false);
  const run = async (method, path, body, message = 'Perubahan disimpan') => {
    setBusy(true);
    try { const r = await api[method](path, body); if (reload) await reload(); if (message) toast.success(message); return r.data; }
    catch (e) { toast.error(errorText(e)); return null; }
    finally { setBusy(false); }
  };
  return { run, busy };
};
export const WorkspaceHead = ({ title, subtitle, children, id = 'workspace' }) => <header className="pw-head"><div><h2 data-testid={`${id}-title`}>{title}</h2>{subtitle && <p data-testid={`${id}-subtitle`}>{subtitle}</p>}</div><div className="pw-actions">{children}</div></header>;
export const EmptyWorkspace = ({ title, children, id = 'workspace-empty' }) => <div className="pw-empty" data-testid={id}><FolderOpen size={30} strokeWidth={1.3} /><h3>{title}</h3>{children}</div>;
export const Action = ({ id, onClick, children, busy, secondary = false, icon: Icon = Plus, ...props }) => <Button type="button" data-testid={id} onClick={onClick} disabled={busy} className={secondary ? 'secondary-button' : 'primary-button'} {...props}>{busy ? <Loader2 size={15} className="spin" /> : <Icon size={15} />}{children}</Button>;
export const DeleteAction = ({ id, onClick, title = 'Hapus' }) => <button type="button" className="pw-icon danger" data-testid={id} title={title} onClick={onClick}><Trash2 size={15} /></button>;
export const WorkspaceModal = ({ open, onClose, title, children, id }) => <Dialog open={open} onOpenChange={v => !v && onClose()}><DialogContent className="app-modal pw-modal" data-testid={`${id}-dialog`}><DialogHeader><DialogTitle data-testid={`${id}-heading`}>{title}</DialogTitle><DialogDescription className="sr-only">{title}</DialogDescription></DialogHeader>{children}</DialogContent></Dialog>;
export const FormField = ({ id, label, children, as = 'input', ...props }) => { const Element = as; return <label className="pw-field"><span>{label}</span><Element data-testid={id} {...props}>{children}</Element></label>; };
export const Submit = ({ id, busy, children = 'Simpan' }) => <Button type="submit" data-testid={id} className="primary-button" disabled={busy}>{busy && <Loader2 size={15} className="spin" />}{children}</Button>;
export const TaskPicker = ({ tasks, value, onChange, id }) => <div className="pw-task-picker" data-testid={id}>{tasks.map(t => <label key={t.id}><input type="checkbox" data-testid={`${id}-${t.id}`} checked={value.includes(t.id)} onChange={e => onChange(e.target.checked ? [...value, t.id] : value.filter(x => x !== t.id))} /><span>{t.title}<small>{t.status}</small></span></label>)}{!tasks.length && <p>Belum ada task.</p>}</div>;