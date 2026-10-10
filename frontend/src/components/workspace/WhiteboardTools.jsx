import React from 'react';
import { MousePointer2, Pencil, Eraser, Undo2, Redo2, StickyNote, CheckSquare } from 'lucide-react';
import { Action } from './WorkspaceUI';

export const noteColors = ['#fff5cd', '#e6f0ff', '#e4f8ec', '#ffe7ef', '#ffffff'];
const inks = [['#253858', 'Gelap'], ['#2c63e8', 'Biru'], ['#10a776', 'Hijau'], ['#e5484d', 'Merah'], ['#d5a230', 'Kuning']];
export const WhiteboardTools = ({ tool, setTool, ink, setInk, width, setWidth, color, setColor, history, busy, tasks, taskId, setTaskId, add }) => (
  <div className="pw-board-tools" data-testid="whiteboard-toolbar" role="toolbar" aria-label="Alat whiteboard">
    <div className="pw-draw-modes" role="group" aria-label="Mode whiteboard">
      {[[MousePointer2, 'select', 'Pilih / geser'], [Pencil, 'pen', 'Pena'], [Eraser, 'eraser', 'Hapus goresan']].map(([Icon, id, label]) => (
        <button type="button" key={id} className={`pw-draw-button ${tool === id ? 'active' : ''}`} title={label} aria-label={label}
          aria-pressed={tool === id} disabled={busy} data-testid={`whiteboard-tool-${id}`} onClick={() => setTool(id)}><Icon size={17} /></button>
      ))}
    </div>
    <div className="pw-swatches pw-ink-swatches" role="group" aria-label="Warna pena">
      {inks.map(([value, name], index) => <button type="button" key={value} style={{ background: value }}
        className={ink === value ? 'active' : ''} disabled={busy} title={`Pena ${name.toLowerCase()}`} aria-label={`Pena ${name.toLowerCase()}`}
        aria-pressed={ink === value} data-testid={`whiteboard-ink-${index}`} onClick={() => { setInk(value); setTool('pen'); }} />)}
    </div>
    <label className="pw-pen-width"><Pencil size={13} aria-hidden="true" />
      <input type="range" min="2" max="16" step="1" value={width} disabled={busy} aria-label="Ketebalan pena" data-testid="whiteboard-pen-width" onChange={event => setWidth(Number(event.target.value))} />
      <output data-testid="whiteboard-pen-width-value">{width}</output>
    </label>
    <div className="pw-draw-modes" role="group" aria-label="Riwayat whiteboard">
      <button type="button" className="pw-draw-button" data-testid="whiteboard-undo" title="Urungkan" aria-label="Urungkan" disabled={busy || !history.canUndo} onClick={history.undo}><Undo2 size={17} /></button>
      <button type="button" className="pw-draw-button" data-testid="whiteboard-redo" title="Ulangi" aria-label="Ulangi" disabled={busy || !history.canRedo} onClick={history.redo}><Redo2 size={17} /></button>
    </div>
    <Action id="whiteboard-add-note" secondary icon={StickyNote} disabled={busy} onClick={() => add()}>Catatan</Action>
    <div className="pw-swatches" role="group" aria-label="Warna catatan">{noteColors.map((value, index) => <button type="button" key={value}
      data-testid={`whiteboard-color-${index}`} title={`Warna catatan ${index + 1}`} aria-label={`Warna catatan ${index + 1}`}
      aria-pressed={color === value} className={color === value ? 'active' : ''} disabled={busy} style={{ background: value }} onClick={() => setColor(value)} />)}</div>
    <select data-testid="whiteboard-task-select" aria-label="Pilih task" disabled={busy} value={taskId} onChange={event => setTaskId(event.target.value)}>
      <option value="">Pilih task…</option>{tasks.map(task => <option key={task.id} value={task.id}>{task.title}</option>)}
    </select>
    <Action id="whiteboard-add-task" icon={CheckSquare} secondary disabled={busy || !taskId} onClick={() => { add(tasks.find(task => task.id === taskId)); setTaskId(''); }}>Task</Action>
  </div>
);