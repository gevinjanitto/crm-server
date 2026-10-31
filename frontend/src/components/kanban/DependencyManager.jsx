import React, { useState } from 'react';
import { Link2, X, CircleCheck, Clock3, ArrowUpRight } from 'lucide-react';
import { isDone } from './helpers';

export const DependencyManager = ({ task, tasks, statuses, manager, patch, onOpen }) => {
  const [choice, setChoice] = useState('');
  const [busy, setBusy] = useState(false);
  const ids = task.dependencies || [];
  const waiting = tasks.filter(t => ids.includes(t.id));
  const blocking = tasks.filter(t => (t.dependencies || []).includes(task.id));
  const options = tasks.filter(t => t.id !== task.id && !ids.includes(t.id));
  const add = async (e) => {
    e.preventDefault();
    if (!choice) return;
    setBusy(true);
    try { const result = await patch({ dependencies: [...ids, choice] }, 'Dependensi ditambahkan'); if (result) setChoice(''); }
    finally { setBusy(false); }
  };
  return <section className="ck-section ck-dependencies" data-testid="task-dependencies">
    <h4 data-testid="dependencies-heading"><Link2 size={15} /> Dependensi <span>{waiting.length}</span></h4>
    <p className="ck-relation-label" data-testid="waiting-label">Menunggu penyelesaian</p>
    {!waiting.length && <p className="ck-muted" data-testid="dependencies-empty">Tidak ada prasyarat.</p>}
    {waiting.map(t => <div className="ck-relation" key={t.id} data-testid={`dependency-${t.id}`}>
      {isDone(statuses, t) ? <CircleCheck size={16} className="ck-dep-done" /> : <Clock3 size={16} className="ck-dep-pending" />}
      <button type="button" className="ck-relation-link" data-testid={`open-dependency-${t.id}`} onClick={() => onOpen(t.id)}>{t.title}<small>{t.status}</small></button>
      {manager && <button className="ck-icon" type="button" title="Hapus dependensi" data-testid={`remove-dependency-${t.id}`} onClick={() => patch({ dependencies: ids.filter(id => id !== t.id) }, 'Dependensi dihapus')}><X size={14} /></button>}
    </div>)}
    {manager && <form className="ck-dependency-add" onSubmit={add}><select className="ck-select" data-testid="dependency-select" aria-label="Pilih task prasyarat" value={choice} onChange={e => setChoice(e.target.value)}><option value="">Pilih task prasyarat…</option>{options.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select><button type="submit" className="ck-clear" disabled={!choice || busy} data-testid="dependency-add"><Link2 size={14} /> Hubungkan</button></form>}
    {blocking.length > 0 && <><p className="ck-relation-label" data-testid="blocking-label">Menjadi prasyarat untuk</p>{blocking.map(t => <button className="ck-relation ck-relation-link" key={t.id} data-testid={`blocking-task-${t.id}`} onClick={() => onOpen(t.id)}><ArrowUpRight size={15} />{t.title}</button>)}</>}
  </section>;
};