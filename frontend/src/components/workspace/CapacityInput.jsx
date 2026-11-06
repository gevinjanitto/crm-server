import React, { useEffect, useState } from 'react';

export const CapacityInput = ({ person, save }) => {
  const [value, setValue] = useState(String(person.capacity));
  const [busy, setBusy] = useState(false);
  useEffect(() => setValue(String(person.capacity)), [person.capacity]);
  const commit = async event => {
    if (busy) return;
    const input = event.currentTarget;
    if (!input.checkValidity() || !value.trim()) {
      input.reportValidity();
      setValue(String(person.capacity));
      return;
    }
    const hours = Number(value);
    if (hours === person.capacity) return;
    setBusy(true);
    const saved = await save(hours);
    if (!saved) setValue(String(person.capacity));
    setBusy(false);
  };
  return <input type="number" min="0" max="168" step="0.5" required
    data-testid={`capacity-input-${person.id}`} aria-label={`Kapasitas ${person.name}`}
    value={value} disabled={busy} onChange={event => setValue(event.target.value)}
    onBlur={commit} onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur(); }} />;
};