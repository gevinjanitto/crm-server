import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { FileText, Save, History, RefreshCw, Bold, Italic, Heading2, List, ListOrdered, Quote, Undo2, Redo2 } from 'lucide-react';
import { api, useData, errorText } from '../../lib/api';
import { toast } from 'sonner';
import { Loading, ErrorState } from '../Common';
import { WorkspaceHead, Action, DeleteAction, EmptyWorkspace, WorkspaceModal, FormField, Submit, useMutation } from './WorkspaceUI';
import { useUnsavedGuard } from './useUnsavedGuard';

const DocEditor = ({ doc, editable, onSaved, base, onDirty, onSaving }) => {
  const [title, setTitle] = useState(doc.title), [visibility, setVisibility] = useState(doc.visibility), [version, setVersion] = useState(doc.version), [dirty, setDirty] = useState(false), [busy, setBusy] = useState(false), [history, setHistory] = useState(null);
  const mark = () => { setDirty(true); onDirty(true); };
  const editor = useEditor({ extensions: [StarterKit], content: doc.content, editable, editorProps: { attributes: { class: 'pw-doc-editor', 'data-testid': 'doc-editor', 'aria-label': 'Isi dokumen' } }, onUpdate: ({ transaction }) => { if (transaction.docChanged) mark(); } });
  useEffect(() => { editor?.setEditable(editable && !busy, false); }, [editor, editable, busy]);
  useEffect(() => { const prevent = e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } }; window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent); }, [dirty]);
  const save = async (content = editor?.getHTML(), restoredTitle = title) => {
    if (busy || !restoredTitle.trim() || !editor) return;
    setBusy(true);
    onSaving(true);
    try { const r = await api.patch(`${base}/${doc.id}`, { title: restoredTitle, content, visibility, version }); setVersion(r.data.version); setTitle(r.data.title); setDirty(false); onDirty(false); onSaved(r.data); editor?.commands.setContent(r.data.content, { emitUpdate: false }); setHistory(null); toast.success('Dokumen disimpan'); }
    catch (e) { toast.error(errorText(e)); } finally { setBusy(false); onSaving(false); }
  };
  const tools = [[Bold, 'Tebal', () => editor.chain().focus().toggleBold().run(), 'bold'], [Italic, 'Miring', () => editor.chain().focus().toggleItalic().run(), 'italic'], [Heading2, 'Judul', () => editor.chain().focus().toggleHeading({ level: 2 }).run(), 'heading'], [List, 'Daftar', () => editor.chain().focus().toggleBulletList().run(), 'bulletList'], [ListOrdered, 'Daftar bernomor', () => editor.chain().focus().toggleOrderedList().run(), 'orderedList'], [Quote, 'Kutipan', () => editor.chain().focus().toggleBlockquote().run(), 'blockquote'], [Undo2, 'Urungkan', () => editor.chain().focus().undo().run(), 'undo'], [Redo2, 'Ulangi', () => editor.chain().focus().redo().run(), 'redo']];
  return <div className="pw-document" data-testid="doc-detail"><div className="pw-doc-top"><span className={`pw-save-state ${dirty ? 'dirty' : ''}`} data-testid="doc-save-state">{dirty ? 'Belum disimpan' : `Tersimpan · v${version}`}</span><span className="pw-muted" data-testid="doc-author">{doc.updated_by}</span><div className="pw-actions">{editable && <><button className="pw-icon" data-testid="doc-history" title="Riwayat versi" onClick={async () => { try { setHistory((await api.get(`${base}/${doc.id}/versions`)).data); } catch (e) { toast.error(errorText(e)); } }}><History size={16} /></button><button className="pw-icon" data-testid="doc-refresh" title="Muat versi terbaru" onClick={async () => { if (dirty && !window.confirm('Buang perubahan lokal dan muat versi terbaru?')) return; try { const latest = (await api.get(base)).data.find(d => d.id === doc.id); if (!latest) return; setVersion(latest.version); setTitle(latest.title); setVisibility(latest.visibility); editor.commands.setContent(latest.content, { emitUpdate: false }); onSaved(latest); setDirty(false); onDirty(false); } catch (e) { toast.error(errorText(e)); } }}><RefreshCw size={16} /></button><Action id="doc-save" icon={Save} busy={busy} onClick={() => save()} disabled={busy || !title.trim()}>Simpan</Action></>}</div></div>
    <input className="pw-doc-title" data-testid="doc-title-input" data-document-id={doc.id} aria-label="Judul dokumen" readOnly={!editable || busy} value={title} maxLength={150} onChange={e => { setTitle(e.target.value); mark(); }} />
    <div className="pw-doc-meta"><FileText size={14} /><span data-testid="doc-updated">{new Date(doc.updated_at).toLocaleString('id-ID')}</span><select data-testid="doc-visibility" disabled={!editable || busy} value={visibility} onChange={e => { setVisibility(e.target.value); mark(); }}><option value="Internal">Internal</option><option value="Client">Dibagikan ke klien</option></select></div>
    {editable && editor && <div className="pw-editor-toolbar">{tools.map(([Icon, label, run, key]) => <button key={key} data-testid={`doc-tool-${key}`} title={label} className={editor.isActive(key) ? 'active' : ''} onClick={run}><Icon size={17} /></button>)}</div>}
    <EditorContent editor={editor} />
    <WorkspaceModal id="doc-versions" open={!!history} onClose={() => setHistory(null)} title="Riwayat dokumen"><div className="pw-version-list">{history?.map(v => <div key={v.id} data-testid={`doc-version-${v.version}`}><span><b>Versi {v.version} · {v.title}</b><small>{v.updated_by} · {new Date(v.updated_at).toLocaleString('id-ID')}</small></span><button className="pw-small-button" data-testid={`doc-restore-${v.version}`} disabled={busy} onClick={() => window.confirm('Pulihkan versi ini sebagai versi baru?') && save(v.content, v.title)}>Pulihkan</button></div>)}</div></WorkspaceModal>
  </div>;
};
export const DocsPage = ({ p, user }) => {
  const base = `/projects/${p.id}/workspace/docs`; const docs = useData(base);
  const [params, setParams] = useSearchParams();
  const selected = params.get('doc');
  const setSelected = id => setParams(previous => { const next = new URLSearchParams(previous); if (id) next.set('doc', id); else next.delete('doc'); return next; }, { replace: true });
  const [creating, setCreating] = useState(false), [name, setName] = useState(''), [dirty, setDirty] = useState(false), [saving, setSaving] = useState(false);
  useUnsavedGuard(dirty || saving);
  const editable = ['Admin', 'Admin Project', 'Developer'].includes(user.role);
  const { run, busy } = useMutation();
  if (docs.loading && !docs.data) return <Loading />; if (docs.error) return <ErrorState error={docs.error} reload={docs.reload} />;
  const current = docs.data?.find(d => d.id === selected) || docs.data?.[0];
  const canLeave = () => !saving && (!dirty || window.confirm('Perubahan belum disimpan. Tetap pindah dokumen?'));
  return <div data-testid="docs-page"><WorkspaceHead id="docs" title="Notes" subtitle={`${docs.data?.length || 0} dokumen project`}>{editable && <Action id="create-doc" disabled={saving} onClick={() => { if (canLeave()) { setCreating(true); setName(''); } }}>Dokumen baru</Action>}</WorkspaceHead>
    {!docs.data?.length ? <EmptyWorkspace title="Belum ada dokumen" id="docs-empty" /> : <div className="pw-doc-layout"><aside className="pw-doc-list">{docs.data.map(d => <div key={d.id} className={d.id === current?.id ? 'active' : ''}><button data-testid={`open-doc-${d.id}`} aria-current={d.id === current?.id ? 'page' : undefined} disabled={saving} onClick={() => { if (d.id !== current?.id && canLeave()) { setSelected(d.id); setDirty(false); } }}><FileText size={16} /><span>{d.title}<small>{d.visibility === 'Client' ? 'Tim & klien' : 'Internal'}</small></span></button>{!saving && (user.role === 'Admin' || user.role === 'Admin Project' || d.created_by === user.id) && <DeleteAction id={`delete-doc-${d.id}`} onClick={async () => { if (window.confirm('Hapus dokumen beserta riwayatnya?') && await run('delete', `${base}/${d.id}`)) { setDirty(false); setSelected(null); await docs.reload(); } }} />}</div>)}</aside>{current && <DocEditor key={current.id} doc={current} base={base} editable={editable} onDirty={setDirty} onSaving={setSaving} onSaved={d => docs.setData(rows => rows.map(r => r.id === d.id ? d : r))} />}</div>}
    <WorkspaceModal id="new-doc" open={creating} onClose={() => setCreating(false)} title="Dokumen baru"><form className="pw-form" onSubmit={async e => { e.preventDefault(); const d = await run('post', base, { title: name, content: '', visibility: 'Internal' }, 'Dokumen dibuat'); if (d) { docs.setData([d, ...(docs.data || [])]); setSelected(d.id); setDirty(false); setCreating(false); } }}><FormField id="new-doc-title" label="Judul" required autoFocus maxLength={150} value={name} onChange={e => setName(e.target.value)} /><Submit id="new-doc-save" busy={busy}>Buat dokumen</Submit></form></WorkspaceModal>
  </div>;
};