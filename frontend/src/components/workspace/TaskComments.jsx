import React, { useState, useEffect, useRef } from 'react';
import { Send, X, AtSign, UserCheck, CheckCircle2, Circle } from 'lucide-react';
import { api, useData, errorText } from '../../lib/api';
import { toast } from 'sonner';
import { useSearchParams } from 'react-router-dom';
import { Avatar } from '../kanban/TaskCard';
import { isManager } from '../kanban/helpers';
import { CommentFiles, AttachPicker, PickedFiles } from './CommentFiles';

export const TaskComments = ({ task, user, onChange }) => {
  const base = `/projects/${task.project_id}/tasks/${task.id}`, workspace = `/projects/${task.project_id}/workspace`;
  const comments = useData(`${base}/comments`), meta = useData(`${workspace}/meta`);
  const updateRef = useRef(onChange); updateRef.current = onChange;
  const [params] = useSearchParams(), focusId = params.get('comment');
  useEffect(() => {
    if (!focusId || !comments.data) return;
    const el = document.querySelector(`[data-testid="comment-${focusId}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('pw-comment-focus');
    const timer = setTimeout(() => el.classList.remove('pw-comment-focus'), 2600);
    return () => clearTimeout(timer);
  }, [focusId, comments.data]);
  useEffect(() => { if (comments.data) updateRef.current({ id: task.id, comment_count: comments.data.length }); }, [comments.data, task.id]);
  const [message, setMessage] = useState(''), [assigned, setAssigned] = useState(''), [busy, setBusy] = useState(false), [files, setFiles] = useState([]);
  const internal = ['Admin', 'Admin Project', 'Developer'].includes(user.role);
  const people = meta.data?.people || [], match = message.match(/(?:^|\s)@([\w.-]*)$/);
  const suggestions = match ? people.filter(p => (p.username || '').toLowerCase().includes(match[1].toLowerCase()) || p.name.toLowerCase().includes(match[1].toLowerCase())).slice(0, 5) : [];
  const run = async (method, path, body) => { try { await api[method](path, body); await comments.reload(); return true; } catch (e) { toast.error(errorText(e)); return false; } };
  const send = async e => {
    e.preventDefault(); if ((!message.trim() && !files.length) || busy) return; setBusy(true);
    let body = { message, assigned_to: assigned, mention_ids: [] }, path = `${base}/comments`;
    if (files.length) { body = new FormData(); body.append('message', message); body.append('assigned_to', assigned); files.forEach(f => body.append('files', f)); path = `${base}/comments/upload`; }
    if (await run('post', path, body)) { setMessage(''); setAssigned(''); setFiles([]); }
    setBusy(false);
  };
  return <section className="ck-side-block ck-activity" data-testid="task-comments"><h4 data-testid="comments-heading">Komentar <span>{comments.data?.length || 0}</span></h4><div className="ck-feed">{comments.data?.map(c => <div className={`ck-comment ${c.resolved ? 'pw-comment-resolved' : ''}`} key={c.id} data-testid={`comment-${c.id}`}><Avatar name={c.author_name} size={28} /><div><header><b>{c.author_name}</b><small>{new Date(c.created_at).toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</small>{(isManager(user) || c.author_id === user.id) && <button className="ck-icon danger" data-testid={`delete-comment-${c.id}`} title="Hapus komentar" onClick={() => run('delete', `${base}/comments/${c.id}`)}><X size={12} /></button>}</header>{c.message && <p data-testid={`comment-message-${c.id}`}>{c.message.split(/(@[\w.-]+)/g).map((text, i) => text.startsWith('@') ? <mark className="pw-mention" key={i}>{text}</mark> : text)}</p>}<CommentFiles comment={c} base={base} />{c.assigned_to && <div className="pw-assigned-comment"><UserCheck size={13} /><span data-testid={`comment-assignee-${c.id}`}>{c.assigned_name}</span>{(isManager(user) || [c.author_id, c.assigned_to].includes(user.id)) ? <button data-testid={`resolve-comment-${c.id}`} title={c.resolved ? 'Buka kembali' : 'Tandai selesai'} onClick={() => run('patch', `${workspace}/tasks/${task.id}/comments/${c.id}`, { resolved: !c.resolved })}>{c.resolved ? <CheckCircle2 size={15} /> : <Circle size={15} />}{c.resolved ? 'Selesai' : 'Selesaikan'}</button> : <small>{c.resolved ? 'Selesai' : 'Belum selesai'}</small>}</div>}</div></div>)}{!comments.data?.length && <p className="ck-muted" data-testid="comments-empty">Belum ada komentar.</p>}{comments.error && <button data-testid="comments-retry" onClick={comments.reload} className="pw-small-button">Gagal memuat. Coba lagi</button>}</div>
    <form className="pw-comment-compose" onSubmit={send}><div className="pw-mention-container"><textarea data-testid="comment-input" placeholder="Tulis komentar…" value={message} maxLength={3000} onChange={e => setMessage(e.target.value)} onKeyDown={e => e.key === 'Enter' && (e.ctrlKey || e.metaKey) && send(e)} />{!!suggestions.length && <div className="pw-mention-menu" data-testid="mention-suggestions">{suggestions.map(p => <button type="button" key={p.id} data-testid={`mention-person-${p.id}`} onClick={() => setMessage(message.replace(/@[\w.-]*$/, `@${p.username} `))}><Avatar name={p.name} size={23} /><span>{p.name}<small>@{p.username}</small></span></button>)}</div>}</div><PickedFiles files={files} setFiles={setFiles} /><div className="pw-compose-bottom"><AttachPicker files={files} setFiles={setFiles} /><button type="button" className="pw-icon" data-testid="mention-insert" title="Sebut anggota" onClick={() => setMessage(s => s + (s.endsWith(' ') || !s ? '@' : ' @'))}><AtSign size={16} /></button>{internal && <select data-testid="comment-assign" aria-label="Tugaskan komentar" value={assigned} onChange={e => setAssigned(e.target.value)}><option value="">Tanpa penugasan</option>{people.filter(p => p.role !== 'Client').map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select>}<button className="ck-primary" type="submit" data-testid="comment-send" disabled={(!message.trim() && !files.length) || busy}><Send size={15} /></button></div></form>
  </section>;
};