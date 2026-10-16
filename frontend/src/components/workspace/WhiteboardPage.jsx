import React, { useEffect, useRef, useState } from 'react';
import '@xyflow/react/dist/style.css';
import { Save, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { api, useData, errorText } from '../../lib/api';
import { Loading, ErrorState } from '../Common';
import { WorkspaceHead, Action } from './WorkspaceUI';
import { useUnsavedGuard } from './useUnsavedGuard';
import { useWhiteboardHistory } from './useWhiteboardHistory';
import { WhiteboardCanvas } from './WhiteboardCanvas';
import { WhiteboardTools, noteColors } from './WhiteboardTools';
import { serializeNode } from './WhiteboardNodes';
import './whiteboard.css';

export const WhiteboardPage = ({ p, tasks }) => {
  const base = `/projects/${p.id}/workspace/whiteboard`, board = useData(base), navigate = useNavigate();
  const history = useWhiteboardHistory(), { reset } = history;
  const canvasRef = useRef(null), flowRef = useRef(null);
  const [version, setVersion] = useState(0), [busy, setBusy] = useState(false), [drawing, setDrawing] = useState(false);
  const [color, setColor] = useState(noteColors[0]), [taskId, setTaskId] = useState('');
  const [tool, setTool] = useState('pen'), [ink, setInk] = useState('#253858'), [width, setWidth] = useState(4);
  useUnsavedGuard(history.dirty || drawing);
  useEffect(() => {
    if (board.data) { reset({ nodes: board.data.nodes, edges: board.data.edges }); setVersion(board.data.version); }
  }, [board.data, reset]);
  const change = (id, label) => history.update(state => ({ ...state, nodes: state.nodes.map(node => node.id === id ? { ...node, data: { ...node.data, label } } : node) }));
  const remove = (id, remember = true) => history.update(state => !state.nodes.some(node => node.id === id) ? state : ({
    nodes: state.nodes.filter(node => node.id !== id), edges: state.edges.filter(edge => edge.source !== id && edge.target !== id),
  }), { remember });
  const add = (task = null) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const flow = flowRef.current, zoom = flow?.getZoom() || 1;
    const origin = rect && flow ? flow.screenToFlowPosition({ x: rect.left + 30, y: rect.top + 35 }) : { x: 70, y: 60 };
    const columns = Math.max(1, Math.floor(((rect?.width || 600) / zoom - 60) / 260));
    let position = origin;
    for (let index = 0; index <= history.nodes.length * 4 + 10; index++) {
      position = { x: origin.x + (index % columns) * 260, y: origin.y + Math.floor(index / columns) * 215 };
      if (!history.nodes.some(node => node.type === 'note' && Math.abs(node.position.x - position.x) < 250 && Math.abs(node.position.y - position.y) < 195)) break;
    }
    history.update(state => ({ ...state, nodes: [...state.nodes, { id: crypto.randomUUID(), type: 'note', position, data: { label: task?.title || '', task_id: task?.id || '', color } }] }));
    setTool('select');
    if (rect && flow && position.y + 190 > origin.y + rect.height / zoom) flow.setCenter(position.x + 115, position.y + 95, { zoom });
  };
  const save = async () => {
    if (busy || drawing) return;
    setBusy(true);
    try {
      const result = await api.patch(base, { name: board.data.name, nodes: history.nodes.map(serializeNode),
        edges: history.edges.map(edge => ({ id: edge.id, source: edge.source, target: edge.target })), version });
      setVersion(result.data.version); history.markSaved(); toast.success('Whiteboard disimpan');
    } catch (error) { toast.error(errorText(error)); } finally { setBusy(false); }
  };
  if (board.loading && !board.data) return <Loading />;
  if (board.error) return <ErrorState error={board.error} reload={board.reload} />;
  const drawn = history.nodes.filter(node => node.type === 'drawing').length;
  return <div data-testid="whiteboard-page">
    <WorkspaceHead id="whiteboard" title="Whiteboard" subtitle={`${history.nodes.length - drawn} catatan · ${drawn} goresan · ${history.edges.length} koneksi`}>
      <span data-testid="whiteboard-save-state" className={`pw-save-state ${history.dirty ? 'dirty' : ''}`}>{busy ? 'Menyimpan…' : history.dirty ? 'Belum disimpan' : `Tersimpan · v${version}`}</span>
      <Action id="whiteboard-reload" icon={RefreshCw} secondary disabled={busy || drawing} onClick={() => (!history.dirty || window.confirm('Buang perubahan lokal dan muat versi terbaru?')) && board.reload()}>Muat ulang</Action>
      <Action id="whiteboard-save" icon={Save} busy={busy} disabled={drawing} onClick={save}>Simpan</Action>
    </WorkspaceHead>
    <WhiteboardTools {...{ tool, setTool, ink, setInk, width, setWidth, color, setColor, history, tasks, taskId, setTaskId, add }} busy={busy || drawing} />
    <WhiteboardCanvas {...{ history, tool, ink, width, busy, change, remove, canvasRef, flowRef }}
      onDrawing={setDrawing} open={tid => navigate(`/projects/${p.id}/kanban?task=${tid}`)} />
  </div>;
};