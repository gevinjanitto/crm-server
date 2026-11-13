import React, { useState } from 'react';
import { Users, Check } from 'lucide-react';
import { Popover, PopoverTrigger, PopoverContent } from '../ui/popover';
import { Avatar } from './TaskCard';

export const MultiAssigneeSelect = ({ people = [], value = [], selectedPeople = [], onChange, disabled = false, testId = 'task-assignees' }) => {
  const [busy, setBusy] = useState(false);
  const names = new Map([...selectedPeople, ...people].map(p => [p.id, p.name]));
  const options = [...new Map([...selectedPeople, ...people].map(p => [p.id, p])).values()];
  const change = async (id) => {
    setBusy(true);
    try { await onChange(value.includes(id) ? value.filter(x => x !== id) : [...value, id]); }
    finally { setBusy(false); }
  };
  const content = <><span className="ck-avatar-stack">{value.slice(0, 3).map(id => <Avatar key={id} name={names.get(id) || '?'} size={23} />)}</span><span className="ck-person-label">{value.length ? value.length === 1 ? names.get(value[0]) || 'Pengguna' : `${value.length} penanggung jawab` : 'Belum ditugaskan'}</span></>;
  if (disabled) return <span className="ck-multi-trigger" data-testid={testId}>{content}</span>;
  return <Popover><PopoverTrigger asChild><button type="button" className="ck-multi-trigger" data-testid={testId} title="Pilih penanggung jawab">{!value.length && <Users size={15} />}{content}</button></PopoverTrigger>
    <PopoverContent align="start" className="ck-people-popover" data-testid={`${testId}-popover`}>
      <b data-testid={`${testId}-heading`}>Penanggung jawab</b>
      {!options.length && <p data-testid={`${testId}-empty`}>Belum ada anggota tim yang dapat ditugaskan.</p>}
      {options.map(person => <label key={person.id} className="ck-person-option"><input type="checkbox" data-testid={`${testId}-option-${person.id}`} checked={value.includes(person.id)} disabled={busy} onChange={() => change(person.id)} /><Avatar name={person.name} size={26} /><span data-testid={`${testId}-person-${person.id}`} style={{overflowWrap:'anywhere'}}>{person.name}{person.role && <small style={{display:'block',color:'var(--ck-muted)'}}>{person.role}</small>}</span>{value.includes(person.id) && <Check size={14} />}</label>)}
    </PopoverContent>
  </Popover>;
};