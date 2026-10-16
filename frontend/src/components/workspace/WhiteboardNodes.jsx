import React from 'react';
import { getStroke } from 'perfect-freehand';
import { Handle, Position } from '@xyflow/react';
import { StickyNote, Trash2, CheckSquare, ExternalLink } from 'lucide-react';

export const drawingPath = (points, width) => {
  const outline = getStroke(points, { size: width, thinning: 0, smoothing: 0.6, streamline: 0.4, last: true });
  return outline.length ? `M${outline.map(point => point.join(',')).join('L')}Z` : '';
};
export const drawingBounds = data => ({
  width: Math.max(16, ...data.points.map(point => point[0] + data.width)),
  height: Math.max(16, ...data.points.map(point => point[1] + data.width)),
});
export const createDrawing = (points, color, width) => {
  const x = Math.min(...points.map(point => point[0])) - width;
  const y = Math.min(...points.map(point => point[1])) - width;
  return { id: crypto.randomUUID(), type: 'drawing', position: { x, y },
    data: { points: points.map(point => [+(point[0] - x).toFixed(2), +(point[1] - y).toFixed(2)]), color, width } };
};
export const serializeNode = node => ({
  id: node.id, type: node.type, position: node.position,
  data: node.type === 'drawing'
    ? { points: node.data.points, color: node.data.color, width: node.data.width }
    : { label: node.data.label, color: node.data.color, task_id: node.data.task_id || '' },
});
const Drawing = ({ id, data, selected }) => {
  const bounds = drawingBounds(data);
  return <svg {...bounds} className={`pw-whiteboard-drawing ${selected ? 'selected' : ''}`}
    data-testid={`whiteboard-drawing-${id}`} role="img" aria-label="Gambar tangan">
    <path d={drawingPath(data.points, data.width)} fill={data.color} />
  </svg>;
};
const Note = ({ id, data, selected, isConnectable }) => (
  <div className={`pw-whiteboard-note ${selected ? 'selected' : ''}`} style={{ background: data.color }} data-testid={`whiteboard-note-${id}`}>
    <Handle type="target" position={Position.Top} isConnectable={isConnectable} data-testid={`whiteboard-target-${id}`} title="Tujuan koneksi" aria-label="Tujuan koneksi" />
    <header><span>{data.task_id ? <CheckSquare size={14} /> : <StickyNote size={14} />}{data.task_id ? 'TASK' : 'CATATAN'}</span>
      <button type="button" className="nodrag" disabled={data.busy} data-testid={`whiteboard-remove-${id}`} title="Hapus catatan" aria-label="Hapus catatan" onClick={() => data.remove(id)}><Trash2 size={13} /></button>
    </header>
    <textarea className="nodrag nowheel" data-testid={`whiteboard-text-${id}`} aria-label="Isi catatan whiteboard" readOnly={data.busy}
      value={data.label} maxLength={2000} placeholder="Tulis ide…" onChange={event => data.change(id, event.target.value)} />
    {data.task_id && <button type="button" className="pw-note-task nodrag" data-testid={`whiteboard-task-${id}`} onClick={() => data.open(data.task_id)}>Buka task <ExternalLink size={12} /></button>}
    <Handle type="source" position={Position.Bottom} isConnectable={isConnectable} data-testid={`whiteboard-source-${id}`} title="Tarik koneksi" aria-label="Tarik koneksi" />
  </div>
);
export const whiteboardNodeTypes = { note: Note, drawing: Drawing };