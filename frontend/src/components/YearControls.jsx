import React, { useState } from 'react';
import { CalendarDays } from 'lucide-react';
import { yearLabel } from '../lib/projectYears';

export const YearSelect = ({ value, years, onChange, testid, allLabel = 'Semua tahun' }) => (
  <label className="year-select" data-testid={`${testid}-wrap`}>
    <CalendarDays size={14} aria-hidden="true" />
    <select className="filter-select" data-testid={testid} aria-label="Pilih tahun" value={value} onChange={e => onChange(e.target.value)}>
      {years.map(y => <option key={y} value={y}>{yearLabel(y)}</option>)}
      <option value="all">{allLabel}</option>
    </select>
  </label>
);

const PRESETS = [10, 25, 50];

// 10 / 25 / 50 / Semua, or a custom number typed by the user (0 = semua).
export const PageSizeSelect = ({ value, onChange, testid }) => {
  const [custom, setCustom] = useState(!PRESETS.includes(value) && value !== 0);
  const mode = custom ? 'custom' : String(value);
  return (
    <span className="page-size-select" data-testid={testid}>
      <span>Tampilkan</span>
      <select className="filter-select" data-testid={`${testid}-select`} aria-label="Jumlah data per halaman" value={mode}
        onChange={e => { const v = e.target.value; if (v === 'custom') { setCustom(true); return; } setCustom(false); onChange(Number(v)); }}>
        {PRESETS.map(n => <option key={n} value={n}>{n}</option>)}
        <option value="0">Semua</option>
        <option value="custom">Atur sendiri…</option>
      </select>
      {custom && <input type="number" min="1" max="1000" className="page-size-input" data-testid={`${testid}-custom`} aria-label="Jumlah data per halaman"
        defaultValue={PRESETS.includes(value) || !value ? '' : value} placeholder="mis. 15"
        onChange={e => { const n = Math.floor(Number(e.target.value)); if (n > 0) onChange(Math.min(n, 1000)); }} />}
      <span>per halaman</span>
    </span>
  );
};
